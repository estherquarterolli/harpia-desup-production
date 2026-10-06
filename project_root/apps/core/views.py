import logging
from django import forms
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from apps.accounts.mixins import PerfilRequiredMixin

logger = logging.getLogger(__name__)


def _contexto_atalhos_dashboard(user):
    """Monta os atalhos pessoais usando apenas destinos permitidos ao perfil."""
    from apps.core.atalhos import catalogo_atalhos_para, resolver_atalho

    catalogo = catalogo_atalhos_para(user)
    atalhos_salvos = list(user.atalhos.all())
    atalhos_user = []
    for atalho in atalhos_salvos:
        if atalho.chave not in catalogo:
            continue
        resolvido = resolver_atalho(atalho.chave)
        if resolvido:
            atalhos_user.append({'id': atalho.id, **resolvido})

    usadas = {atalho.chave for atalho in atalhos_salvos}
    return {
        'atalhos_user': atalhos_user,
        'atalhos_disponiveis': [
            {'chave': chave, 'label': dados['label']}
            for chave, dados in catalogo.items()
            if chave not in usadas
        ],
    }


def _dashboard_atalhos_url_name(user):
    """Dashboard de retorno após adicionar/remover um atalho."""
    eh_desup = (
        getattr(user, 'is_superuser', False)
        or getattr(user, 'perfil', None) == 'DESUP'
        or user.groups.filter(name='Admin DESUP').exists()
    )
    return 'dashboard_desup' if eh_desup else 'dashboard_unidade'


def custom_500(request):
    return render(
        request,
        '500.html',
        {'request_id': getattr(request, '_harpia_request_id', '')},
        status=500,
    )


def _safe_redirect_url(request, default='/'):
    """Retorna o next_url somente se for um caminho seguro (mesmo host)."""
    next_url = request.POST.get('next', request.META.get('HTTP_REFERER', default))
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return default
    return next_url

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get(self, request, *args, **kwargs):
        from apps.accounts.views import get_dashboard_url_for_user
        url = get_dashboard_url_for_user(request.user)
        # Se a URL de redirecionamento for diferente do caminho atual, redireciona
        if url != request.path:
            return redirect(url)
        return super().get(request, *args, **kwargs)

class DashboardDesupView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    template_name = 'dashboard/desup.html'
    allowed_profiles = ['DESUP']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.professors.models import Professor
        from apps.professors.views import _bulk_ch_alocada, _bulk_ch_justificada
        from apps.courses.models import MatrixComponent
        from apps.core.models import Unidade

        ctx['total_professores'] = Professor.objects.count()
        unidades_ativas = list(Unidade.objects.filter(status=True).order_by('nome'))
        ctx['total_unidades'] = len(unidades_ativas)

        # A versÃ£o anterior fazia uma consulta por unidade e mais consultas de
        # carga para cada professor. Em bases reais isso virava centenas de
        # idas ao banco antes de o dashboard aparecer. Agora as cargas e os
        # vÃ­nculos sÃ£o buscados em lote e a conformidade Ã© calculada em memÃ³ria.
        professores_ativos = list(
            Professor.objects.filter(status=Professor.StatusChoices.ATIVO)
            .select_related('tipo_contrato', 'unidade_principal')
            .prefetch_related('unidades')
        )
        professor_ids = [prof.pk for prof in professores_ativos]
        ch_alocada = _bulk_ch_alocada(professor_ids)
        ch_justificada = _bulk_ch_justificada(professor_ids)
        unidades_nao_conformes_ids = set()
        unidades_ativas_ids = {unidade.pk for unidade in unidades_ativas}

        for prof in professores_ativos:
            total = ch_alocada.get(prof.pk, 0) + ch_justificada.get(prof.pk, 0.0)
            meta = prof.ch_total
            percentual = min((total / meta) * 100, 100.0) if meta else 0.0
            if percentual >= 100:
                continue
            ids = {unidade.pk for unidade in prof.unidades.all()}
            if prof.unidade_principal_id:
                ids.add(prof.unidade_principal_id)
            unidades_nao_conformes_ids.update(ids & unidades_ativas_ids)

        nao_conformes = [
            {'id': unidade.id, 'nome': unidade.nome}
            for unidade in unidades_ativas
            if unidade.id in unidades_nao_conformes_ids
        ]
        conformes = ctx['total_unidades'] - len(nao_conformes)

        ctx['unidades_nao_conformes'] = nao_conformes
        ctx['unidades_conformes_count'] = conformes
        if ctx['total_unidades']:
            pct = round((conformes / ctx['total_unidades']) * 100)
            ctx['conformidade'] = f'{pct}%'
        else:
            ctx['conformidade'] = '0%'

        # Professores para a tabela de consulta
        componentes_vigentes = MatrixComponent.objects.filter(
            matriz__is_vigente=True,
        ).select_related('componente_curricular')
        professores_qs = Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related(
            'unidades',
            Prefetch(
                'componentes_matriz',
                queryset=componentes_vigentes,
                to_attr='componentes_vigentes',
            ),
        ).order_by('rh_nome')
        ctx['unidades'] = unidades_ativas

        # Estrutura esperada pelo partial _professor_table.html
        from django.core.paginator import Paginator
        page_obj = Paginator(professores_qs, 20).get_page(1)
        ctx['alocacoes_dashboard'] = [
            {
                'prof': prof,
                'units': prof.unidades_exibicao,
                'subjects': sorted({
                    componente.nome_disciplina
                    for componente in prof.componentes_vigentes
                    if componente.nome_disciplina
                }),
                'ha': prof.ha,
            }
            for prof in page_obj.object_list
        ]
        ctx['dashboard_page_obj'] = page_obj

        ctx.update(_contexto_atalhos_dashboard(self.request.user))
        return ctx


class AtalhoAddView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Adiciona atalho pessoal permitido ao perfil (whitelist)."""
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def post(self, request):
        from apps.core.models import AtalhoDashboard
        from apps.core.atalhos import catalogo_atalhos_para
        catalogo = catalogo_atalhos_para(request.user)
        chaves = [c.strip() for c in request.POST.getlist('chave') if c.strip()]
        validas = [c for c in chaves if c in catalogo]
        if not validas:
            messages.error(request, 'Selecione ao menos um atalho válido.')
            return redirect(_dashboard_atalhos_url_name(request.user))
        for chave in validas:
            AtalhoDashboard.objects.get_or_create(user=request.user, chave=chave)
        messages.success(request, 'Atalho(s) salvo(s).')
        return redirect(_dashboard_atalhos_url_name(request.user))


class AtalhoRemoveView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Remove um atalho do próprio usuário."""
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def post(self, request, pk):
        from apps.core.models import AtalhoDashboard
        atalho = get_object_or_404(AtalhoDashboard, pk=pk, user=request.user)
        atalho.delete()
        messages.success(request, 'Atalho(s) removido(s).')
        return redirect(_dashboard_atalhos_url_name(request.user))


class DashboardProfessoresPartialView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    """HTMX partial: retorna apenas a tabela de professores filtrada."""
    template_name = 'dashboard/partials/_professor_table.html'
    allowed_profiles = ['DESUP']

    def get(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            from django.shortcuts import redirect
            return redirect('dashboard_desup')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.professors.models import Professor
        from apps.courses.models import MatrixComponent

        componentes_vigentes = MatrixComponent.objects.filter(
            matriz__is_vigente=True,
        ).select_related('componente_curricular')

        qs = Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related(
            'unidades',
            Prefetch(
                'componentes_matriz',
                queryset=componentes_vigentes,
                to_attr='componentes_vigentes',
            ),
        ).order_by('rh_nome')

        q = self.request.GET.get('q', '')
        if q:
            from apps.core.busca import filtrar_contem
            qs = filtrar_contem(qs, q, ['rh_nome', 'desup_nome'])
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id:
            qs = qs.filter(
                Q(unidades__id=unidade_id) | Q(unidade_principal_id=unidade_id)
            ).distinct()
        turno = self.request.GET.get('turno')
        if turno:
            qs = qs.filter(disponibilidades__turno=turno).distinct()

        from django.core.paginator import Paginator
        page_obj = Paginator(qs, 20).get_page(self.request.GET.get('page'))
        ctx['alocacoes_dashboard'] = [
            {
                'prof': prof,
                'units': prof.unidades_exibicao,
                'subjects': sorted({
                    componente.nome_disciplina
                    for componente in prof.componentes_vigentes
                    if componente.nome_disciplina
                }),
                'ha': prof.ha,
            }
            for prof in page_obj.object_list
        ]
        ctx['dashboard_page_obj'] = page_obj
        return ctx


class DashboardUnidadeView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    template_name = 'dashboard/unidade.html'
    allowed_profiles = ['COORDENADOR_UNIDADE']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_contexto_atalhos_dashboard(self.request.user))
        return ctx

# --- CRUD de Unidade ---
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from .models import Unidade
from .services import create_window_ticket

class UnidadeBaseView(LoginRequiredMixin, PerfilRequiredMixin):
    allowed_profiles = ['DESUP'] # Apenas DESUP gere unidades

class UnidadeListView(UnidadeBaseView, ListView):
    model = Unidade
    template_name = 'core/unidade_list.html'
    context_object_name = 'unidades'
    paginate_by = 18

class UnidadeCreateView(UnidadeBaseView, CreateView):
    model = Unidade
    fields = ['nome', 'sigla', 'status']
    template_name = 'core/unidade_form.html'
    success_url = reverse_lazy('core:unidade_list')

class UnidadeUpdateView(UnidadeBaseView, UpdateView):
    model = Unidade
    fields = ['nome', 'sigla', 'status']
    template_name = 'core/unidade_form.html'
    success_url = reverse_lazy('core:unidade_list')

# --- CRUD de Cursos (dentro de Unidade) ---
from django.shortcuts import get_object_or_404
from django.views.generic import DeleteView
from apps.courses.models import Course, CourseUnit

class CursoBaseView(LoginRequiredMixin, PerfilRequiredMixin):
    allowed_profiles = ['DESUP']

    def get_unidade(self):
        return get_object_or_404(Unidade, pk=self.kwargs['unidade_pk'])

class CursoListView(CursoBaseView, ListView):
    model = CourseUnit
    template_name = 'core/curso_list.html'
    context_object_name = 'cursos'
    paginate_by = 20

    def get_queryset(self):
        return CourseUnit.objects.filter(unidade_id=self.kwargs['unidade_pk']).order_by('curso__nome')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unidade'] = self.get_unidade()
        return ctx

class CursoOfertaForm(forms.ModelForm):
    """
    CORR-029: cadastrar um curso aqui significa **ofertá-lo nesta unidade**, não
    necessariamente criar um `Course` novo.

    `Course.nome` e `Course.sigla` são `unique` (o curso é global; quem é por
    unidade é o `CourseUnit`). Com a validação de unicidade padrão do ModelForm, o
    formulário rejeitava o mesmo curso numa segunda unidade — e o caminho de
    reaproveitamento que já existia no `form_valid` era inalcançável. Desligamos a
    checagem de unicidade aqui justamente porque repetir nome/sigla é o sinal de
    "é este curso mesmo"; a decisão de reusar ou criar fica no `form_valid`.
    """

    class Meta:
        model = Course
        fields = ['nome', 'sigla']

    def validate_unique(self):
        return


class CursoCreateView(CursoBaseView, CreateView):
    model = Course
    form_class = CursoOfertaForm
    template_name = 'core/curso_form.html'

    def get_success_url(self):
        return reverse_lazy('core:curso_list', kwargs={'unidade_pk': self.kwargs['unidade_pk']})

    def form_valid(self, form):
        curso = form.save(commit=False)
        # Reaproveita o curso já cadastrado (por sigla OU por nome — os dois são
        # `unique`, então bater em qualquer um dos dois significa ser o mesmo curso).
        curso_existente = Course.objects.filter(
            Q(sigla=curso.sigla) | Q(nome=curso.nome)
        ).first()
        if curso_existente:
            curso = curso_existente
        else:
            curso.save()
        CourseUnit.objects.get_or_create(curso=curso, unidade=self.get_unidade())
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unidade'] = self.get_unidade()
        return ctx

class CursoUpdateView(CursoBaseView, UpdateView):
    model = Course
    fields = ['nome', 'sigla']
    template_name = 'core/curso_form.html'

    def get_object(self, queryset=None):
        # CORR-029: o vínculo tem de pertencer à unidade da URL. Sem o filtro, a
        # edição aberta a partir de uma unidade alterava o curso de OUTRA e
        # redirecionava para uma lista onde a alteração nem aparecia. O
        # `CursoDeleteView` já filtrava; aqui tinha ficado de fora.
        return get_object_or_404(
            CourseUnit,
            pk=self.kwargs['pk'],
            unidade_id=self.kwargs['unidade_pk'],
        ).curso

    def get_success_url(self):
        return reverse_lazy('core:curso_list', kwargs={'unidade_pk': self.kwargs['unidade_pk']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unidade'] = self.get_unidade()
        return ctx

class CursoDeleteView(CursoBaseView, DeleteView):
    model = CourseUnit
    template_name = 'core/curso_confirm_delete.html'

    def get_queryset(self):
        return CourseUnit.objects.filter(unidade_id=self.kwargs['unidade_pk'])

    def get_success_url(self):
        return reverse_lazy('core:curso_list', kwargs={'unidade_pk': self.kwargs['unidade_pk']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unidade'] = self.get_unidade()
        return ctx

# --- CRUD de Janela de Entrega ---
from .models import JanelaEntrega
from .forms import JanelaEntregaValidacaoMixin
from django import forms

_JANELA_FIELD_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:border-[#1e4e8c] outline-none transition bg-white'
_JANELA_SELECT_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-[#1e4e8c] outline-none transition'


class JanelaEntregaCreateForm(JanelaEntregaValidacaoMixin, forms.ModelForm):
    """Form para criar nova janela — data_inicio e data_fim configuráveis."""
    class Meta:
        model = JanelaEntrega
        fields = ['semestre', 'data_inicio', 'data_fim', 'status', 'unidade']
        widgets = {
            # flatpickr (classe js-date-ptbr) exibe dd/mm/aaaa fixo, independente do
            # idioma do navegador, e envia o valor em ISO (Y-m-d). format='%Y-%m-%d'
            # garante que o valor inicial ja saia em ISO para o flatpickr interpretar.
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'class': _JANELA_FIELD_CSS + ' js-date-ptbr', 'placeholder': 'dd/mm/aaaa', 'data-min-today': '1'}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'class': _JANELA_FIELD_CSS + ' js-date-ptbr', 'placeholder': 'dd/mm/aaaa', 'data-min-today': '1'}),
            'semestre': forms.TextInput(attrs={'class': _JANELA_FIELD_CSS, 'placeholder': 'Ex: 2026.1'}),
            'status': forms.Select(attrs={'class': _JANELA_SELECT_CSS}),
            'unidade': forms.Select(attrs={'class': _JANELA_SELECT_CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        # localdate(): com now().date() o campo já vinha pré-preenchido com amanhã
        # das 21h à meia-noite (UTC-3), divergindo do "hoje" validado no clean().
        self.fields['data_inicio'].initial = timezone.localdate()
        # Nova janela nasce sempre "Aberta" — nao faz sentido criar ja fechada. Campo
        # travado: disabled ignora o POST e usa este initial, entao nao ha como burlar.
        self.fields['status'].choices = [
            (JanelaEntrega.StatusChoices.ABERTO, 'Aberto'),
        ]
        self.fields['status'].initial = JanelaEntrega.StatusChoices.ABERTO
        self.fields['status'].disabled = True
        self.fields['unidade'].empty_label = 'Todas as unidades'
        self.fields['unidade'].help_text = ''

    def clean(self):
        cleaned_data = super().clean()
        from django.utils import timezone
        # localdate(): now().date() é UTC e, das 21h à meia-noite de Brasília, já
        # apontava para amanhã — a DESUP não conseguia criar janela começando hoje.
        hoje = timezone.localdate()
        inicio = cleaned_data.get('data_inicio')
        fim = cleaned_data.get('data_fim')
        if inicio and inicio < hoje:
            self.add_error('data_inicio', 'A data de início não pode ser anterior ao dia atual.')
        if fim and fim < hoje:
            self.add_error('data_fim', 'A data de fim não pode ser anterior ao dia atual.')
        # Ordem das datas, formato do semestre e sobreposição: regras compartilhadas
        # com o form do admin (apps/core/forms.py) para não divergirem.
        return self._validar_regras_da_janela(cleaned_data)


class JanelaEntregaUpdateForm(JanelaEntregaValidacaoMixin, forms.ModelForm):
    """Form para editar janela — permite editar data_inicio e status."""
    class Meta:
        model = JanelaEntrega
        fields = ['semestre', 'data_inicio', 'data_fim', 'status', 'unidade']
        widgets = {
            # flatpickr (classe js-date-ptbr) exibe dd/mm/aaaa fixo, independente do
            # idioma do navegador, e envia o valor em ISO (Y-m-d). format='%Y-%m-%d'
            # garante que o valor inicial ja saia em ISO para o flatpickr interpretar.
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'class': _JANELA_FIELD_CSS + ' js-date-ptbr', 'placeholder': 'dd/mm/aaaa', 'data-min-today': '1'}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'class': _JANELA_FIELD_CSS + ' js-date-ptbr', 'placeholder': 'dd/mm/aaaa', 'data-min-today': '1'}),
            'semestre': forms.TextInput(attrs={'class': _JANELA_FIELD_CSS, 'placeholder': 'Ex: 2026.1'}),
            'status': forms.Select(attrs={'class': _JANELA_SELECT_CSS}),
            'unidade': forms.Select(attrs={'class': _JANELA_SELECT_CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            (choice[0], choice[1])
            for choice in JanelaEntrega.StatusChoices.choices
            if choice[0] != JanelaEntrega.StatusChoices.REABERTO
        ]
        if self.instance and self.instance.status == JanelaEntrega.StatusChoices.REABERTO:
            self.initial['status'] = JanelaEntrega.StatusChoices.ABERTO

        self.fields['unidade'].empty_label = 'Todas as unidades'
        self.fields['unidade'].help_text = ''

    def clean(self):
        cleaned_data = super().clean()
        from django.utils import timezone
        # localdate(): ver comentário no form de criação — now().date() é UTC.
        hoje = timezone.localdate()
        inicio = cleaned_data.get('data_inicio')
        fim = cleaned_data.get('data_fim')
        # Só barra data passada nos campos que o usuário efetivamente alterou; assim,
        # editar (p.ex. o status) de uma janela já em andamento — cujo início/fim já
        # ficou no passado — não é bloqueado. Ao escolher uma data nova, ela deve ser
        # de hoje em diante. (self.instance ainda tem os valores originais do banco.)
        if inicio and inicio < hoje and inicio != self.instance.data_inicio:
            self.add_error('data_inicio', 'A data de início não pode ser anterior ao dia atual.')
        if fim and fim < hoje and fim != self.instance.data_fim:
            self.add_error('data_fim', 'A data de fim não pode ser anterior ao dia atual.')
        # Impede que uma janela global seja convertida em janela de unidade específica
        if self.instance.pk and self.instance.unidade is None:
            nova_unidade = cleaned_data.get('unidade')
            if nova_unidade is not None:
                raise forms.ValidationError(
                    'Não é possível vincular uma janela global a uma unidade específica. '
                    'Para fechar apenas para uma unidade, crie uma nova janela com status "Fechado" '
                    'cobrindo o período em que a unidade deve ficar bloqueada — o fechamento por '
                    'unidade só vale enquanto a janela Fechado estiver vigente.'
                )
        # Ordem das datas, formato do semestre e sobreposição: regras compartilhadas
        # com o form do admin (apps/core/forms.py) para não divergirem.
        return self._validar_regras_da_janela(cleaned_data)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.instance.pk and instance.status == JanelaEntrega.StatusChoices.ABERTO:
            instance.status = JanelaEntrega.StatusChoices.REABERTO
        if commit:
            instance.save()
        return instance


class JanelaEntregaBaseView(LoginRequiredMixin, PerfilRequiredMixin):
    allowed_profiles = ['DESUP'] # Apenas DESUP gere entregas

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not (request.user.is_superuser or request.user.perfil == 'DESUP'):
            messages.error(request, 'A área de janelas de entrega é restrita à DESUP.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

class JanelaEntregaListView(JanelaEntregaBaseView, ListView):
    model = JanelaEntrega
    template_name = 'core/janela_list.html'
    context_object_name = 'janelas'
    paginate_by = 20

    def get_queryset(self):
        from django.db.models import Q
        from apps.core.services import fechar_janelas_expiradas
        fechar_janelas_expiradas()
        qs = JanelaEntrega.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            from apps.core.busca import filtrar_contem

            qs = filtrar_contem(
                qs,
                q,
                ['semestre', 'status', 'unidade__nome', 'unidade__sigla'],
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id:
            if unidade_id == 'global':
                qs = qs.filter(unidade__isnull=True)
            else:
                # Inclui janelas da unidade E janelas globais (todas as unidades)
                qs = qs.filter(Q(unidade_id=unidade_id) | Q(unidade__isnull=True))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.core.models import Unidade
        ctx['status_choices'] = JanelaEntrega.StatusChoices.choices
        ctx['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        ctx['filtro_q'] = self.request.GET.get('q', '')
        ctx['filtro_status'] = self.request.GET.get('status', '')
        ctx['filtro_unidade'] = self.request.GET.get('unidade_id', '')
        ctx['selected_status'] = ctx['filtro_status']
        ctx['selected_unidade_id'] = ctx['filtro_unidade']
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        return ctx

class JanelaEntregaCreateView(JanelaEntregaBaseView, CreateView):
    model = JanelaEntrega
    form_class = JanelaEntregaCreateForm
    template_name = 'core/janela_form.html'
    success_url = reverse_lazy('core:janela_list')

class JanelaEntregaUpdateView(JanelaEntregaBaseView, UpdateView):
    model = JanelaEntrega
    form_class = JanelaEntregaUpdateForm
    template_name = 'core/janela_form.html'
    success_url = reverse_lazy('core:janela_list')

class JanelaEntregaDeleteView(JanelaEntregaBaseView, DeleteView):
    model = JanelaEntrega
    template_name = 'core/janela_confirm_delete.html'
    success_url = reverse_lazy('core:janela_list')

# --- Notificações ---
from django.views import View
from django.http import HttpResponse


def _usuario_pode_marcar_notificacao(user, notificacao):
    """Retorna True se o usuário pode marcar a notificação como lida."""
    if user.is_superuser or user.perfil == 'DESUP':
        return True
    if notificacao.destinatario == user:
        return True
    if user.perfil == 'COORDENADOR_UNIDADE':
        if notificacao.unidade_destino and notificacao.unidade_destino == user.unidade:
            return True
    return False


def _get_notificacao_do_usuario(request, pk):
    """
    SEC-001: devolve a notificação SOMENTE se o usuário puder vê-la; caso
    contrário, 404 (e não 403 — 403 confirmaria que a notificação existe).

    Antes, a view carregava a notificação sem escopo nenhum e redirecionava para
    `notificacao.url_acao` FORA do `if` de permissão. Como o `url_acao` da
    notificação de reset de senha carrega o token de aprovação, qualquer usuário
    logado lia o token de qualquer outra pessoa só iterando o `pk` e olhando o
    header `Location` do 302.
    """
    from apps.core.models import Notificacao
    from django.shortcuts import get_object_or_404

    notificacao = get_object_or_404(Notificacao, pk=pk)
    if not _usuario_pode_marcar_notificacao(request.user, notificacao):
        logger.warning(
            "Acesso negado a notificação alheia (usuário %s, notificação %s).",
            request.user.pk, pk,
        )
        raise Http404("Notificação não encontrada.")
    return notificacao


def _url_acao_segura(notificacao, request):
    """Só redireciona para caminho interno — `url_acao` nunca deve levar para fora."""
    destino = notificacao.url_acao or '/'
    if not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return '/'
    return destino


class MarcarNotificacaoLidaView(LoginRequiredMixin, View):
    def get(self, request, pk):
        notificacao = _get_notificacao_do_usuario(request, pk)
        notificacao.lida = True
        notificacao.save()
        return redirect(_url_acao_segura(notificacao, request))

    def post(self, request, pk):
        notificacao = _get_notificacao_do_usuario(request, pk)
        notificacao.lida = True
        notificacao.save()

        # Requisição HTMX → retorna resposta vazia para o elemento ser removido via hx-swap="delete"
        if request.headers.get('HX-Request'):
            response = HttpResponse('')
            # Atualizar badge de contagem de notificações
            from apps.core.models import Notificacao as Notif
            from django.db.models import Q
            user = request.user
            base_qs = Notif.objects.filter(lida=False)
            if user.is_superuser or user.perfil == 'DESUP':
                count = base_qs.filter(
                    Q(destinatario=user) | Q(destinatario__isnull=True, unidade_destino__isnull=True)
                ).distinct().count()
            elif user.perfil == 'COORDENADOR_UNIDADE' and user.unidade:
                count = base_qs.filter(
                    Q(destinatario=user) | Q(unidade_destino=user.unidade)
                ).distinct().count()
            else:
                count = base_qs.filter(destinatario=user).count()
            response['HX-Trigger'] = f'{{"notifCountUpdate": {count}}}'
            return response

        next_url = _safe_redirect_url(request)
        return redirect(next_url)


class SolicitarChamadoAlteracaoView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ['COORDENADOR_UNIDADE']

    def post(self, request):
        area_label = request.POST.get('area_label', 'Alterações')
        action_label = request.POST.get('action_label', 'alterar dados')
        target_label = request.POST.get('target_label', '').strip()
        details = request.POST.get('details', '').strip()
        next_url = _safe_redirect_url(request)

        if not request.user.unidade:
            from django.contrib import messages

            messages.error(request, 'Sua conta não está vinculada a uma unidade.')
            return redirect(next_url)

        create_window_ticket(
            request=request,
            area_label=area_label,
            action_label=action_label,
            target_label=target_label,
            details=details,
            unidade=request.user.unidade,
            next_url=next_url,
        )

        from django.contrib import messages

        messages.success(
            request,
            f'Chamado encaminhado para a DESUP sobre {action_label.lower()}.',
        )
        return redirect(next_url)

class ExportarLogsView(LoginRequiredMixin, PerfilRequiredMixin, View):
    allowed_profiles = ['DESUP']

    def get(self, request):
        import csv
        from django.http import HttpResponse
        from apps.core.models import AuditoriaGlobal

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="auditoria_sistema.csv"'

        writer = csv.writer(response, delimiter=';')
        writer.writerow(['ID', 'Data/Hora', 'Usuario (E-mail)', 'Acao', 'Detalhes', 'IP', 'User-Agent'])

        logs = AuditoriaGlobal.objects.all().select_related('usuario').order_by('-criado_em')
        for log in logs:
            data_str = log.criado_em.strftime('%d/%m/%Y %H:%M:%S')
            email_str = log.email or (log.usuario.email if log.usuario else '')
            writer.writerow([
                log.pk,
                data_str,
                email_str,
                log.acao,
                log.detalhes,
                log.ip or '',
                log.user_agent or ''
            ])
        
        return response

