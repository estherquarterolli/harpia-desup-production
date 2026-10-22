import logging
from decimal import Decimal
from django import forms
from django.db.models import Count, Q
from django.db.models import Exists, OuterRef
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.http import HttpResponseRedirect
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
        from apps.professors.views import (
            _bulk_ch_alocada,
            _bulk_ch_justificada,
            enriquecer_professores_com_carga,
        )
        from apps.core.models import Unidade
        from apps.core.priority1 import obter_resumo_prioridade1

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
        professores_qs = Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related(
            'unidades', 'ocupacoes_diretivas', 'readaptacoes',
        ).order_by('rh_nome')
        ctx['unidades'] = unidades_ativas
        ctx['resumo_p1'] = obter_resumo_prioridade1()

        # Estrutura esperada pelo partial _professor_table.html
        from django.core.paginator import Paginator
        page_obj = Paginator(professores_qs, 20).get_page(1)
        professores_pagina = enriquecer_professores_com_carga(page_obj.object_list)['professores']
        ctx['alocacoes_dashboard'] = [
            {
                'prof': prof,
                'units': prof.unidades_exibicao,
                'ch': prof.carga_total_efetiva,
            }
            for prof in professores_pagina
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

    def get(self, request, pk):
        # A remoção só acontece por POST; abrir o endereço direto volta ao painel
        # em vez de mostrar erro.
        return redirect(_dashboard_atalhos_url_name(request.user))

    def post(self, request, pk):
        from apps.core.models import AtalhoDashboard
        # Escopo no servidor: só apaga atalho do próprio usuário. Se ele não existe
        # mais (outra aba, duplo clique) ou é de outro usuário, a resposta é a mesma,
        # sem 404 e sem revelar se o id existe.
        removidos, _ = AtalhoDashboard.objects.filter(pk=pk, user=request.user).delete()
        if removidos:
            messages.success(request, 'Atalho(s) removido(s).')
        else:
            messages.info(request, 'Este atalho já havia sido removido.')
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
        from apps.professors.views import enriquecer_professores_com_carga

        qs = Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related(
            'unidades', 'ocupacoes_diretivas', 'readaptacoes',
        ).order_by('rh_nome')

        q = self.request.GET.get('q', '')
        if q:
            from apps.core.busca import filtrar_contem
            qs = filtrar_contem(
                qs,
                q,
                ['rh_nome', 'desup_nome', 'id_funcional', 'rh_matricula', 'area_atuacao'],
            )
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
        professores_pagina = enriquecer_professores_com_carga(page_obj.object_list)['professores']
        ctx['alocacoes_dashboard'] = [
            {
                'prof': prof,
                'units': prof.unidades_exibicao,
                'ch': prof.carga_total_efetiva,
            }
            for prof in professores_pagina
        ]
        ctx['dashboard_page_obj'] = page_obj
        return ctx


class DashboardUnidadeView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    template_name = 'dashboard/unidade.html'
    allowed_profiles = ['COORDENADOR_UNIDADE']

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        from apps.core.busca import filtrar_contem
        from apps.professors.models import Professor
        from apps.professors.views import enriquecer_professores_com_carga

        ctx = super().get_context_data(**kwargs)
        ctx.update(_contexto_atalhos_dashboard(self.request.user))

        unidade = self.request.user.unidade
        qs = Professor.objects.none()
        if unidade:
            qs = Professor.objects.select_related(
                'tipo_contrato', 'unidade_principal',
            ).prefetch_related(
                'unidades', 'ocupacoes_diretivas', 'readaptacoes',
            ).filter(
                Q(unidade_principal_id=unidade.pk) | Q(unidades__id=unidade.pk)
            ).distinct().order_by('rh_nome', 'pk')
            q = self.request.GET.get('q', '').strip()
            if q:
                qs = filtrar_contem(
                    qs, q, ['rh_nome', 'desup_nome', 'id_funcional', 'rh_matricula'],
                )
        else:
            q = ''

        paginator = Paginator(qs, 20)
        page_obj = paginator.get_page(self.request.GET.get('page'))
        dados = enriquecer_professores_com_carga(page_obj.object_list, unidade)
        from apps.professors.views import detalhar_alocacoes_professores
        detalhar_alocacoes_professores(dados['professores'], self.request.user)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx.update({
            'professores_unidade': dados['professores'],
            'colunas_cursos': dados['colunas_cursos'],
            'page_obj': page_obj,
            'paginator': paginator,
            'is_paginated': page_obj.has_other_pages(),
            'querystring': params.urlencode(),
            'filtro_q': q,
            'total_professores_unidade': paginator.count,
        })
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

    def get_queryset(self):
        from apps.core.busca import filtrar_contem

        qs = Unidade.objects.annotate(
            qtd_cursos=Count('course_units', filter=Q(course_units__ativo=True), distinct=True)
        ).order_by('nome')
        status = self.request.GET.get('status', '')
        if status == 'ativa':
            qs = qs.filter(status=True)
        elif status == 'inativa':
            qs = qs.filter(status=False)
        return filtrar_contem(qs, self.request.GET.get('q', '').strip(), ['nome', 'sigla'])

    def get_context_data(self, **kwargs):
        from apps.courses.models import CourseUnit

        ctx = super().get_context_data(**kwargs)
        total = Unidade.objects.aggregate(
            total=Count('pk'),
            ativas=Count('pk', filter=Q(status=True)),
            inativas=Count('pk', filter=Q(status=False)),
        )
        ctx['kpis'] = [
            {'rotulo': 'Unidades', 'valor': total['total'], 'tom': 'azul', 'icone': 'ph-buildings'},
            {'rotulo': 'Ativas', 'valor': total['ativas'], 'tom': 'verde', 'icone': 'ph-check-circle'},
            {'rotulo': 'Inativas', 'valor': total['inativas'], 'tom': 'ambar', 'icone': 'ph-prohibit'},
            {'rotulo': 'Cursos ativos', 'valor': CourseUnit.objects.filter(ativo=True).count(), 'tom': 'cinza', 'icone': 'ph-graduation-cap'},
        ]
        ctx['filtro_q'] = self.request.GET.get('q', '').strip()
        ctx['filtro_status'] = self.request.GET.get('status', '')
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        return ctx

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


# ---------------------------------------------------------------------------
# Prioridade 1 - governança exclusiva da DESUP
# ---------------------------------------------------------------------------

class DesupPrioridade1Mixin(LoginRequiredMixin, PerfilRequiredMixin):
    allowed_profiles = ['DESUP']


class RetornoOrigemMixin:
    """Volta para a tela de origem (ex.: unidade filtrada) após salvar em modal."""

    def _retorno_seguro(self):
        destino = self.request.POST.get('next') or self.request.GET.get('next')
        if destino and url_has_allowed_host_and_scheme(
            destino, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure(),
        ):
            return destino
        return ''

    def get_success_url(self):
        return self._retorno_seguro() or super().get_success_url()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['retorno'] = self._retorno_seguro()
        if ctx['retorno']:
            ctx['cancel_url'] = ctx['retorno']
        return ctx


class EquipeDiretivaDesupView(DesupPrioridade1Mixin, TemplateView):
    template_name = 'core/prioridade1/equipe_diretiva.html'

    def get_context_data(self, **kwargs):
        from django.utils import timezone
        from .forms import OcupacaoEquipeDiretivaForm, TipoCargoDiretivoForm
        from .models import OcupacaoEquipeDiretiva, TipoCargoDiretivo, Unidade

        ctx = super().get_context_data(**kwargs)
        unidade_id = self.request.GET.get('unidade_id', '')
        hoje = timezone.localdate()
        cargos = list(
            TipoCargoDiretivo.objects.annotate(
                tem_ocupacoes=Exists(
                    OcupacaoEquipeDiretiva.objects.filter(cargo_id=OuterRef('pk'))
                )
            ).order_by('ordem', 'nome')
        )
        unidade_selecionada = None
        if unidade_id.isdigit():
            unidade_selecionada = Unidade.objects.filter(pk=unidade_id, status=True).first()

        composicao = []
        historico = []
        reducao_total = Decimal('0.00')
        if unidade_selecionada:
            historico = list(
                OcupacaoEquipeDiretiva.objects.filter(unidade=unidade_selecionada)
                .select_related('cargo', 'professor', 'curso', 'curso__curso')
                .order_by('-data_inicio')[:200]
            )
            por_cargo = {}
            for ocupacao in historico:
                if ocupacao.vigente:
                    por_cargo.setdefault(ocupacao.cargo_id, []).append(ocupacao)
                    reducao_total += ocupacao.carga_reducao_horas
            for cargo in cargos:
                ocupantes = por_cargo.get(cargo.pk, [])
                item = {
                    'cargo': cargo,
                    'ocupantes': ocupantes,
                    'pode_adicionar': cargo.ativo and (
                        not ocupantes or cargo.permite_multiplos
                    ),
                }
                if item['pode_adicionar']:
                    item['form'] = OcupacaoEquipeDiretivaForm(
                        unidade=unidade_selecionada,
                        cargo=cargo,
                        auto_id=f'id_ocup{cargo.pk}_%s',
                        initial={'data_inicio': hoje},
                    )
                composicao.append(item)
            # Ativos primeiro; inativos só aparecem para consulta/reativação.
            composicao.sort(key=lambda item: not item['cargo'].ativo)

        ctx.update({
            'cargos_forms': [
                (cargo, TipoCargoDiretivoForm(instance=cargo, auto_id=f'id_cargo{cargo.pk}_%s'))
                for cargo in cargos
            ],
            'form_novo_cargo': TipoCargoDiretivoForm(auto_id='id_novocargo_%s'),
            'unidade_selecionada': unidade_selecionada,
            'composicao': composicao,
            'historico': historico,
            'reducao_total': reducao_total,
            'unidades': Unidade.objects.filter(status=True).order_by('nome'),
            'filtro_unidade': unidade_id,
            'retorno': (
                f"{reverse_lazy('core:equipe_diretiva_desup')}?unidade_id={unidade_selecionada.pk}"
                if unidade_selecionada
                else reverse_lazy('core:equipe_diretiva_desup')
            ),
        })
        return ctx


class TipoCargoDiretivoCreateView(DesupPrioridade1Mixin, RetornoOrigemMixin, CreateView):
    from .forms import TipoCargoDiretivoForm
    from .models import TipoCargoDiretivo

    model = TipoCargoDiretivo
    form_class = TipoCargoDiretivoForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:equipe_diretiva_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Novo tipo de cargo', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request, 'CARGO_DIRETIVO_CRIADO', f'Cargo {self.object.pk}: {self.object.nome}.',
        )
        messages.success(self.request, 'Tipo de cargo criado com sucesso.')
        return response


class TipoCargoDiretivoUpdateView(DesupPrioridade1Mixin, RetornoOrigemMixin, UpdateView):
    from .forms import TipoCargoDiretivoForm
    from .models import TipoCargoDiretivo

    model = TipoCargoDiretivo
    form_class = TipoCargoDiretivoForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:equipe_diretiva_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Editar tipo de cargo', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from django.utils import timezone
        from .models import OcupacaoEquipeDiretiva
        from .services import registrar_evento_prioridade1
        response = super().form_valid(form)
        if 'carga_reducao_horas' in form.changed_data:
            # Ocupantes vigentes acompanham a nova redução do cargo; o histórico não muda.
            hoje = timezone.localdate()
            OcupacaoEquipeDiretiva.objects.filter(
                cargo=self.object, data_inicio__lte=hoje,
            ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=hoje)).update(
                carga_reducao_horas=self.object.carga_reducao_horas,
            )
        registrar_evento_prioridade1(
            self.request, 'CARGO_DIRETIVO_ATUALIZADO',
            f'Cargo {self.object.pk}: {self.object.nome}; redução semanal {self.object.carga_reducao_horas} h.',
        )
        messages.success(self.request, 'Tipo de cargo atualizado com sucesso.')
        return response


class TipoCargoDiretivoDeleteView(DesupPrioridade1Mixin, View):
    http_method_names = ['post', 'head', 'options']

    def post(self, request, *args, **kwargs):
        from django.db import transaction
        from .models import TipoCargoDiretivo
        from .services import registrar_evento_prioridade1

        cargo = get_object_or_404(TipoCargoDiretivo, pk=kwargs['pk'])
        cargo_id = cargo.pk
        nome_cargo = cargo.nome
        # O cargo pode ser excluído mesmo com ocupantes: as ocupações dele (vigentes e
        # históricas) são removidas junto, na mesma transação, e a quantidade fica na auditoria.
        with transaction.atomic():
            ocupacoes_removidas, _ = cargo.ocupacoes.all().delete()
            cargo.delete()
        detalhe = f'Cargo {cargo_id}: {nome_cargo}.'
        if ocupacoes_removidas:
            detalhe += f' {ocupacoes_removidas} ocupação(ões) removida(s) junto com o cargo.'
        registrar_evento_prioridade1(request, 'CARGO_DIRETIVO_EXCLUIDO', detalhe)
        messages.success(
            request,
            'Cargo excluído com sucesso.' if not ocupacoes_removidas
            else f'Cargo excluído com sucesso, junto com {ocupacoes_removidas} ocupação(ões).',
        )
        destino = request.POST.get('next', '')
        if destino and url_has_allowed_host_and_scheme(
            destino,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return HttpResponseRedirect(destino)
        return HttpResponseRedirect(reverse_lazy('core:equipe_diretiva_desup'))


class OcupacaoEquipeDiretivaCreateView(DesupPrioridade1Mixin, CreateView):
    from .forms import OcupacaoEquipeDiretivaForm
    from .models import OcupacaoEquipeDiretiva

    model = OcupacaoEquipeDiretiva
    form_class = OcupacaoEquipeDiretivaForm
    template_name = 'core/prioridade1/form.html'

    def dispatch(self, request, *args, **kwargs):
        from .models import TipoCargoDiretivo
        self.unidade = get_object_or_404(Unidade, pk=kwargs['unidade_pk'], status=True)
        self.cargo = get_object_or_404(TipoCargoDiretivo, pk=kwargs['cargo_pk'], ativo=True)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'unidade': self.unidade, 'cargo': self.cargo})
        return kwargs

    def get_initial(self):
        from django.utils import timezone
        return {'data_inicio': timezone.localdate()}

    def get_success_url(self):
        return f"{reverse_lazy('core:equipe_diretiva_desup')}?unidade_id={self.unidade.pk}"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'titulo': f'{self.cargo.nome} - {self.unidade.sigla}',
            'cancel_url': self.get_success_url(),
        })
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        form.instance.criado_por = self.request.user
        # A redução pertence ao cargo (definida pela DESUP no cadastro dele).
        form.instance.carga_reducao_horas = self.cargo.carga_reducao_horas
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request,
            'OCUPACAO_DIRETIVA_CRIADA',
            f'Ocupação {self.object.pk}; unidade {self.unidade.pk}; cargo {self.cargo.pk}; '
            f'redução semanal {self.object.carga_reducao_horas} h.',
        )
        messages.success(self.request, 'Cargo preenchido com sucesso.')
        return response


class OcupacaoEquipeDiretivaUpdateView(DesupPrioridade1Mixin, RetornoOrigemMixin, UpdateView):
    from .forms import ReducaoOcupacaoEquipeDiretivaForm
    from .models import OcupacaoEquipeDiretiva

    model = OcupacaoEquipeDiretiva
    form_class = ReducaoOcupacaoEquipeDiretivaForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:equipe_diretiva_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Ajustar redução da ocupação', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request,
            'REDUCAO_OCUPACAO_DIRETIVA_ATUALIZADA',
            f'Ocupação {self.object.pk}; redução semanal {self.object.carga_reducao_horas} h.',
        )
        messages.success(self.request, 'Carga horária de redução atualizada com sucesso.')
        return response


class SolicitacaoProfessorExternoDesupView(DesupPrioridade1Mixin, TemplateView):
    template_name = 'core/prioridade1/solicitacoes_professor.html'

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        from .models import SolicitacaoProfessorExterno, Unidade

        ctx = super().get_context_data(**kwargs)
        status = self.request.GET.get('status', SolicitacaoProfessorExterno.StatusChoices.PENDENTE)
        unidade_id = self.request.GET.get('unidade_id', '')
        tipo = self.request.GET.get('tipo', '')
        qs = SolicitacaoProfessorExterno.objects.select_related(
            'professor', 'unidade_solicitante', 'unidade_origem', 'solicitado_por', 'decidido_por'
        )
        if status in SolicitacaoProfessorExterno.StatusChoices.values:
            qs = qs.filter(status=status)
        if tipo in SolicitacaoProfessorExterno.TipoChoices.values:
            qs = qs.filter(tipo=tipo)
        if unidade_id.isdigit():
            qs = qs.filter(unidade_solicitante_id=unidade_id)
        totais = dict(
            SolicitacaoProfessorExterno.objects.values_list('status').annotate(n=Count('pk'))
        )
        Status = SolicitacaoProfessorExterno.StatusChoices
        ctx.update({
            'kpis': [
                {'rotulo': 'Pendentes', 'valor': totais.get(Status.PENDENTE, 0), 'tom': 'ambar', 'icone': 'ph-clock'},
                {'rotulo': 'Aprovadas', 'valor': totais.get(Status.APROVADA, 0), 'tom': 'verde', 'icone': 'ph-check-circle'},
                {'rotulo': 'Recusadas', 'valor': totais.get(Status.RECUSADA, 0), 'tom': 'vermelho', 'icone': 'ph-x-circle'},
            ],
            'solicitacoes': Paginator(qs, 25).get_page(self.request.GET.get('page')),
            'unidades': Unidade.objects.filter(status=True).order_by('nome'),
            'status_choices': SolicitacaoProfessorExterno.StatusChoices.choices,
            'tipo_choices': SolicitacaoProfessorExterno.TipoChoices.choices,
            'filtro_status': status,
            'filtro_tipo': tipo,
            'filtro_unidade': unidade_id,
        })
        return ctx


class SolicitacaoProfessorExternoDecidirView(DesupPrioridade1Mixin, View):
    def post(self, request, pk):
        from django.core.exceptions import ValidationError
        from .forms import DecisaoSolicitacaoProfessorForm
        from .services import decidir_solicitacao_professor_externo

        form = DecisaoSolicitacaoProfessorForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Revise a decisão e informe o motivo quando necessário.')
            return redirect('core:solicitacao_professor_list')
        try:
            solicitacao = decidir_solicitacao_professor_externo(
                request=request,
                solicitacao_id=pk,
                decisao=form.cleaned_data['decisao'],
                motivo=form.cleaned_data['motivo_decisao'],
            )
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
        else:
            messages.success(
                request, f'Solicitação {solicitacao.get_status_display().lower()} com sucesso.',
            )
        return redirect('core:solicitacao_professor_list')


class AlertasCargaDesupView(DesupPrioridade1Mixin, TemplateView):
    template_name = 'core/prioridade1/alertas_carga.html'

    def get_context_data(self, **kwargs):
        from django.utils import timezone
        from .models import ExcecaoCargaUnidade, ReadaptacaoProfessor, Unidade
        from .forms import ReadaptacaoProfessorEdicaoForm, ReadaptacaoProfessorForm
        from .priority1 import obter_resumo_prioridade1

        ctx = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        unidade_id = self.request.GET.get('unidade_id', '')
        curso_id = self.request.GET.get('curso_id', '')
        curso_id = curso_id if curso_id.isdigit() else ''
        from apps.courses.models import Course
        cursos_filtro = Course.objects.order_by('sigla')
        if unidade_id.isdigit():
            cursos_filtro = cursos_filtro.filter(course_units__unidade_id=unidade_id).distinct()
        resumo = obter_resumo_prioridade1(
            unidade_id=unidade_id if unidade_id.isdigit() else None,
            semestre=self.request.GET.get('semestre') or None,
            curso_id=curso_id or None,
            turno=self.request.GET.get('turno') or None,
            status=self.request.GET.get('status') or None,
        )
        readaptacoes = ReadaptacaoProfessor.objects.select_related('professor').order_by('-data_inicio')
        excecoes = ExcecaoCargaUnidade.objects.filter(
            status=ExcecaoCargaUnidade.StatusChoices.PENDENTE
        ).select_related('unidade', 'professor', 'solicitado_por')
        if unidade_id.isdigit():
            readaptacoes = readaptacoes.filter(
                Q(professor__unidades__id=unidade_id) | Q(professor__unidade_principal_id=unidade_id)
            ).distinct()
            excecoes = excecoes.filter(unidade_id=unidade_id)
        readaptacoes = list(readaptacoes[:100])
        ctx.update({
            'resumo_p1': resumo,
            # Quantos pontos de atenção têm ocorrências (exibido no resumo recolhido).
            'pontos_atencao': sum(1 for chave in (
                'diretivos_em_sala', 'readaptados_em_sala', 'ensino_medio_superior',
            ) if resumo[chave]),
            'readaptacoes_vigentes': sum(1 for item in readaptacoes if item.vigente),
            'form_readaptacao': ReadaptacaoProfessorForm(auto_id='id_novareadap_%s', initial={'data_inicio': hoje}),
            'readaptacoes_forms': [
                (item, ReadaptacaoProfessorEdicaoForm(instance=item, auto_id=f'id_readap{item.pk}_%s'))
                for item in readaptacoes
            ],
            'readaptacoes': readaptacoes,
            'excecoes_pendentes': excecoes[:100],
            'unidades': Unidade.objects.filter(status=True).order_by('nome'),
            'cursos': cursos_filtro,
            'filtro_unidade': unidade_id,
            'filtro_curso': curso_id,
            'hoje': hoje,
        })
        return ctx


class LimiteCargaUnidadeCreateView(DesupPrioridade1Mixin, RetornoOrigemMixin, CreateView):
    from .forms import LimiteCargaUnidadeForm
    from .models import LimiteCargaUnidade

    model = LimiteCargaUnidade
    form_class = LimiteCargaUnidadeForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:alertas_carga_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Definir teto semanal da unidade', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        self.object = form.save(commit=False)
        self.object.criado_por = self.request.user
        self.object.save()
        registrar_evento_prioridade1(
            self.request, 'LIMITE_CARGA_CRIADO', f'Limite {self.object.pk}; unidade {self.object.unidade_id}.',
        )
        messages.success(self.request, 'Teto semanal da unidade definido com sucesso.')
        return redirect(self.get_success_url())


class LimiteCargaUnidadeUpdateView(DesupPrioridade1Mixin, RetornoOrigemMixin, UpdateView):
    from .forms import LimiteCargaUnidadeForm
    from .models import LimiteCargaUnidade

    model = LimiteCargaUnidade
    form_class = LimiteCargaUnidadeForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:alertas_carga_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Editar teto semanal da unidade', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request, 'LIMITE_CARGA_ATUALIZADO', f'Limite {self.object.pk}; unidade {self.object.unidade_id}.',
        )
        messages.success(self.request, 'Teto semanal da unidade atualizado com sucesso.')
        return response


class ReadaptacaoProfessorCreateView(DesupPrioridade1Mixin, RetornoOrigemMixin, CreateView):
    from .forms import ReadaptacaoProfessorForm
    from .models import ReadaptacaoProfessor

    model = ReadaptacaoProfessor
    form_class = ReadaptacaoProfessorForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:alertas_carga_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Registrar readaptação', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        self.object = form.save(commit=False)
        self.object.criado_por = self.request.user
        self.object.save()
        registrar_evento_prioridade1(
            self.request, 'READAPTACAO_CRIADA', f'Readaptação {self.object.pk}; professor {self.object.professor_id}.',
        )
        messages.success(self.request, 'Readaptação registrada com sucesso.')
        return redirect(self.get_success_url())


class ReadaptacaoProfessorUpdateView(DesupPrioridade1Mixin, RetornoOrigemMixin, UpdateView):
    from .forms import ReadaptacaoProfessorEdicaoForm
    from .models import ReadaptacaoProfessor

    model = ReadaptacaoProfessor
    form_class = ReadaptacaoProfessorEdicaoForm
    template_name = 'core/prioridade1/form.html'
    success_url = reverse_lazy('core:alertas_carga_desup')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({'titulo': 'Editar readaptação', 'cancel_url': self.success_url})
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request, 'READAPTACAO_ATUALIZADA', f'Readaptação {self.object.pk}; professor {self.object.professor_id}.',
        )
        messages.success(self.request, 'Readaptação atualizada com sucesso.')
        return response


class ReadaptacaoProfessorEncerrarView(DesupPrioridade1Mixin, View):
    def post(self, request, pk):
        from django.db import transaction
        from django.utils import timezone
        from .models import ReadaptacaoProfessor
        from .services import registrar_evento_prioridade1

        with transaction.atomic():
            readaptacao = get_object_or_404(ReadaptacaoProfessor.objects.select_for_update(), pk=pk)
            hoje = timezone.localdate()
            if readaptacao.data_fim and readaptacao.data_fim < hoje:
                messages.info(request, 'Esta readaptação já estava encerrada.')
                return redirect('core:alertas_carga_desup')
            readaptacao.data_fim = max(hoje, readaptacao.data_inicio)
            readaptacao.save(update_fields=['data_fim', 'atualizado_em'])
            registrar_evento_prioridade1(
                request, 'READAPTACAO_ENCERRADA', f'Readaptação {readaptacao.pk}.',
            )
        messages.success(request, 'Readaptação encerrada com sucesso.')
        return redirect('core:alertas_carga_desup')


class ExcecaoCargaDecidirView(DesupPrioridade1Mixin, View):
    def post(self, request, pk):
        from django.core.exceptions import ValidationError
        from .forms import DecisaoExcecaoCargaForm
        from .services import decidir_excecao_carga

        form = DecisaoExcecaoCargaForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Revise a decisão e informe o motivo quando necessário.')
            return redirect('core:alertas_carga_desup')
        try:
            excecao = decidir_excecao_carga(
                request=request,
                excecao_id=pk,
                decisao=form.cleaned_data['decisao'],
                motivo=form.cleaned_data['motivo_decisao'],
            )
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
        else:
            messages.success(request, f'Exceção {excecao.get_status_display().lower()} com sucesso.')
        return redirect('core:alertas_carga_desup')


# ---------------------------------------------------------------------------
# Prioridade 1.1 - Equipe Diretiva, Coordenações e Estágio (Módulo da Unidade)
# ---------------------------------------------------------------------------

def _mapa_alocacoes_sala_por_professor(professor_ids):
    """
    Retorna dicionário {professor_id: {'disciplinas': [...], 'horas_sala': Decimal}}
    para todos os professores entre `professor_ids` que possuem alocação vigente
    em sala de aula no semestre atual.
    """
    professor_ids = {pid for pid in professor_ids if pid}
    if not professor_ids:
        return {}

    from apps.allocations.services import alocacoes_vigentes

    linhas = alocacoes_vigentes().filter(
        docente_id__in=professor_ids,
    ).select_related(
        'componente_matriz',
        'componente_matriz__componente_curricular',
    )

    disciplinas_por_prof = {}
    horas_por_prof = {}
    vistos_por_prof = {}

    for linha in linhas:
        pid = linha.docente_id
        comp = linha.componente_matriz
        nome_disc = comp.nome_disciplina
        if nome_disc:
            disciplinas_por_prof.setdefault(pid, set()).add(nome_disc)

        chave = (
            f"catalogo:{comp.componente_curricular_id}"
            if comp.compartilhado and comp.componente_curricular_id
            else f"linha:{comp.pk}"
        )
        vistos = vistos_por_prof.setdefault(pid, set())
        if chave not in vistos:
            vistos.add(chave)
            ha = Decimal(str(comp.ha_semanal or 0))
            horas_por_prof[pid] = horas_por_prof.get(pid, Decimal('0.00')) + ha

    resultado = {}
    for pid in set(disciplinas_por_prof.keys()) | set(horas_por_prof.keys()):
        resultado[pid] = {
            'disciplinas': sorted(disciplinas_por_prof.get(pid, set())),
            'horas_sala': horas_por_prof.get(pid, Decimal('0.00')),
        }
    return resultado


class UnidadePrioridade1Mixin(LoginRequiredMixin, PerfilRequiredMixin):
    """Restringe o acesso ao Coordenador de Unidade autenticado com unidade vinculada."""
    allowed_profiles = ['COORDENADOR_UNIDADE']

    def get_unidade(self):
        from django.core.exceptions import PermissionDenied

        unidade = getattr(self.request.user, 'unidade', None)
        if not unidade or not unidade.status:
            raise PermissionDenied('Sua conta não está vinculada a uma unidade ativa.')
        return unidade


class EquipeDiretivaUnidadeView(UnidadePrioridade1Mixin, TemplateView):
    """
    Painel do Coordenador de Unidade para cadastro e atualização dos ocupantes
    da equipe diretiva, coordenações e atividades de estágio e supervisão da
    própria unidade, com alertas visuais de docentes alocados em sala de aula.
    """
    template_name = 'core/prioridade1/equipe_diretiva_unidade.html'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            partial = self.request.GET.get('partial', '')
            if partial == 'historico':
                return ['core/prioridade1/partials/_historico_equipe_unidade.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        from django.utils import timezone
        from apps.allocations.services import semestre_atual
        from apps.core.busca import filtrar_contem
        from .forms import (
            OcupacaoEquipeDiretivaUnidadeForm,
        )
        from .models import (
            OcupacaoEquipeDiretiva,
            TipoCargoDiretivo,
        )

        ctx = super().get_context_data(**kwargs)
        unidade = self.get_unidade()
        hoje = timezone.localdate()
        semestre_corrente = semestre_atual()

        # Todas as consultas filtram estritamente pela unidade do usuário via UnitBoundManager.
        ocupacoes_qs = (
            OcupacaoEquipeDiretiva.objects.for_user(self.request.user)
            .filter(unidade=unidade)
            .select_related('cargo', 'professor', 'curso', 'curso__curso')
            .order_by('-data_inicio', '-pk')
        )
        todas_ocupacoes = list(ocupacoes_qs[:300])

        # Coleta IDs de professores para verificar alocações vigentes em sala de aula.
        prof_ids = {o.professor_id for o in todas_ocupacoes}
        mapa_sala = _mapa_alocacoes_sala_por_professor(prof_ids)

        por_cargo = {}
        reducao_total = Decimal('0.00')
        alertas_em_sala = []
        vistos_alerta = set()

        for ocupacao in todas_ocupacoes:
            info_sala = mapa_sala.get(ocupacao.professor_id)
            ocupacao.em_sala = bool(info_sala)
            ocupacao.disciplinas_sala = info_sala['disciplinas'] if info_sala else []
            ocupacao.horas_sala = info_sala['horas_sala'] if info_sala else Decimal('0.00')

            if ocupacao.vigente:
                por_cargo.setdefault(ocupacao.cargo_id, []).append(ocupacao)
                reducao_total += ocupacao.carga_reducao_horas
                ocupacao.edit_form = OcupacaoEquipeDiretivaUnidadeForm(
                    instance=ocupacao,
                    unidade=unidade,
                    cargo=ocupacao.cargo,
                    auto_id=f'id_editocup{ocupacao.pk}_%s',
                )
                if ocupacao.em_sala:
                    chave_alerta = ('CARGO', ocupacao.pk)
                    if chave_alerta not in vistos_alerta:
                        vistos_alerta.add(chave_alerta)
                        alertas_em_sala.append({
                            'ocupacao_pk': ocupacao.pk,
                            'professor_nome': ocupacao.professor.nome,
                            'funcao_label': (
                                f"{ocupacao.cargo.nome} ({ocupacao.curso.sigla})"
                                if ocupacao.curso_id else ocupacao.cargo.nome
                            ),
                            'disciplinas': ocupacao.disciplinas_sala,
                            'horas_sala': ocupacao.horas_sala,
                            'reducao_horas': ocupacao.carga_reducao_horas,
                        })



        cargos = list(
            TipoCargoDiretivo.objects.filter(
                Q(ativo=True) | Q(pk__in=por_cargo.keys())
            ).order_by('ordem', 'nome')
        )

        composicao = []
        for cargo in cargos:
            ocupantes = por_cargo.get(cargo.pk, [])
            pode_adicionar = cargo.ativo and (not ocupantes or cargo.permite_multiplos)
            item = {
                'cargo': cargo,
                'ocupantes': ocupantes,
                'pode_adicionar': pode_adicionar,
                'tem_alerta_sala': any(o.em_sala for o in ocupantes),
            }
            if pode_adicionar:
                item['form'] = OcupacaoEquipeDiretivaUnidadeForm(
                    unidade=unidade,
                    cargo=cargo,
                    auto_id=f'id_unidocup{cargo.pk}_%s',
                    initial={'data_inicio': hoje},
                )
            composicao.append(item)

        # Filtros do histórico da unidade (busca + situação)
        filtro_q = self.request.GET.get('q', '').strip()
        filtro_situacao = self.request.GET.get('situacao', '').strip()
        historico_qs = ocupacoes_qs
        if filtro_q:
            historico_qs = filtrar_contem(
                historico_qs,
                filtro_q,
                ['professor__rh_nome', 'professor__desup_nome', 'cargo__nome', 'curso__curso__sigla'],
            )
        if filtro_situacao == 'vigente':
            historico_qs = historico_qs.filter(
                data_inicio__lte=hoje,
            ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
        elif filtro_situacao == 'encerrada':
            historico_qs = historico_qs.filter(
                Q(data_inicio__gt=hoje) | Q(data_fim__lt=hoje)
            )

        historico_page_obj = Paginator(historico_qs, 15).get_page(self.request.GET.get('page'))
        for item_hist in historico_page_obj.object_list:
            info_sala = mapa_sala.get(item_hist.professor_id)
            item_hist.em_sala = bool(info_sala)
            item_hist.disciplinas_sala = info_sala['disciplinas'] if info_sala else []
            item_hist.horas_sala = info_sala['horas_sala'] if info_sala else Decimal('0.00')

        ctx.update({
            'unidade': unidade,
            'hoje': hoje,
            'semestre_corrente': semestre_corrente,
            'composicao': composicao,
            'reducao_total': reducao_total,
            'alertas_em_sala': alertas_em_sala,
            'historico': historico_page_obj.object_list,
            'historico_page_obj': historico_page_obj,
            'filtro_q': filtro_q,
            'filtro_situacao': filtro_situacao,
            'retorno': reverse_lazy('core:equipe_diretiva_unidade'),
        })
        return ctx


class OcupacaoEquipeDiretivaUnidadeCreateView(UnidadePrioridade1Mixin, RetornoOrigemMixin, CreateView):
    from .forms import OcupacaoEquipeDiretivaUnidadeForm
    from .models import OcupacaoEquipeDiretiva

    model = OcupacaoEquipeDiretiva
    form_class = OcupacaoEquipeDiretivaUnidadeForm
    template_name = 'core/prioridade1/form_unidade.html'
    success_url = reverse_lazy('core:equipe_diretiva_unidade')

    def _carregar_escopo(self):
        from .models import TipoCargoDiretivo
        if not hasattr(self, 'unidade'):
            self.unidade = self.get_unidade()
            self.cargo = get_object_or_404(TipoCargoDiretivo, pk=self.kwargs['cargo_pk'], ativo=True)

    def get_form_kwargs(self):
        self._carregar_escopo()
        kwargs = super().get_form_kwargs()
        kwargs.update({'unidade': self.unidade, 'cargo': self.cargo})
        return kwargs

    def get_initial(self):
        from django.utils import timezone
        return {'data_inicio': timezone.localdate()}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'titulo': f'Preencher {self.cargo.nome} — {self.unidade.sigla}',
            'subtitulo': 'A carga horária de redução semanal é definida exclusivamente pela DESUP.',
            'cancel_url': self.get_success_url(),
        })
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1

        form.instance.unidade = self.unidade
        form.instance.cargo = self.cargo
        form.instance.criado_por = self.request.user
        # Garantia no servidor: a unidade não define redução; ela vem do cargo (DESUP).
        form.instance.carga_reducao_horas = self.cargo.carga_reducao_horas
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request,
            'OCUPACAO_DIRETIVA_UNIDADE_CRIADA',
            f'Ocupação {self.object.pk}; unidade {self.unidade.pk}; cargo {self.cargo.pk}; '
            f'professor {self.object.professor_id}.',
        )
        messages.success(self.request, 'Ocupante registrado com sucesso na equipe diretiva.')
        return response


class OcupacaoEquipeDiretivaUnidadeUpdateView(UnidadePrioridade1Mixin, RetornoOrigemMixin, UpdateView):
    from .forms import OcupacaoEquipeDiretivaUnidadeForm
    from .models import OcupacaoEquipeDiretiva

    model = OcupacaoEquipeDiretiva
    form_class = OcupacaoEquipeDiretivaUnidadeForm
    template_name = 'core/prioridade1/form_unidade.html'
    success_url = reverse_lazy('core:equipe_diretiva_unidade')

    def get_queryset(self):
        from .models import OcupacaoEquipeDiretiva
        unidade = self.get_unidade()
        return (
            OcupacaoEquipeDiretiva.objects.for_user(self.request.user)
            .filter(unidade=unidade)
            .select_related('cargo', 'unidade', 'professor', 'curso')
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'unidade': self.object.unidade, 'cargo': self.object.cargo})
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'titulo': f'Atualizar {self.object.cargo.nome} — {self.object.unidade.sigla}',
            'subtitulo': (
                f'Redução semanal definida pela DESUP: '
                f'{self.object.carga_reducao_horas:.2f} h (somente leitura).'
            ),
            'reducao_somente_leitura': self.object.carga_reducao_horas,
            'cancel_url': self.get_success_url(),
        })
        return ctx

    def form_valid(self, form):
        from .models import OcupacaoEquipeDiretiva
        from .services import registrar_evento_prioridade1

        original = OcupacaoEquipeDiretiva.objects.only('unidade_id', 'cargo_id', 'carga_reducao_horas').get(
            pk=self.object.pk
        )
        form.instance.unidade_id = original.unidade_id
        form.instance.cargo_id = original.cargo_id
        form.instance.carga_reducao_horas = original.carga_reducao_horas
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request,
            'OCUPACAO_DIRETIVA_UNIDADE_ATUALIZADA',
            f'Ocupação {self.object.pk}; unidade {self.object.unidade_id}; cargo {self.object.cargo_id}.',
        )
        messages.success(self.request, 'Ocupação da equipe diretiva atualizada com sucesso.')
        return response


class OcupacaoEquipeDiretivaUnidadeEncerrarView(UnidadePrioridade1Mixin, View):
    http_method_names = ['post', 'head', 'options']

    def post(self, request, pk):
        from django.db import transaction
        from django.utils import timezone
        from .models import OcupacaoEquipeDiretiva
        from .services import registrar_evento_prioridade1

        unidade = self.get_unidade()
        with transaction.atomic():
            ocupacao = get_object_or_404(
                OcupacaoEquipeDiretiva.objects.for_user(request.user)
                .filter(unidade=unidade)
                .select_for_update(),
                pk=pk,
            )
            hoje = timezone.localdate()
            if ocupacao.data_fim and ocupacao.data_fim < hoje:
                messages.info(request, 'Esta ocupação já estava encerrada.')
                return redirect('core:equipe_diretiva_unidade')
            ocupacao.data_fim = max(hoje, ocupacao.data_inicio)
            ocupacao.save(update_fields=['data_fim', 'atualizado_em'])
            registrar_evento_prioridade1(
                request,
                'OCUPACAO_DIRETIVA_UNIDADE_ENCERRADA',
                f'Ocupação {ocupacao.pk}; unidade {unidade.pk}; fim {ocupacao.data_fim}.',
            )
        messages.success(request, 'Ocupação encerrada com sucesso.')
        return redirect('core:equipe_diretiva_unidade')


class AtividadeEstagioSupervisaoCreateView(UnidadePrioridade1Mixin, RetornoOrigemMixin, CreateView):
    from .forms import AtividadeEstagioSupervisaoUnidadeForm
    from .models import AtividadeEstagioSupervisao

    model = AtividadeEstagioSupervisao
    form_class = AtividadeEstagioSupervisaoUnidadeForm
    template_name = 'core/prioridade1/form_unidade.html'
    success_url = reverse_lazy('extra_curricular:supervisao_estagio')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['unidade'] = self.get_unidade()
        return kwargs

    def get_initial(self):
        from django.utils import timezone
        from apps.allocations.services import semestre_atual
        return {
            'data_inicio': timezone.localdate(),
            'semestre': semestre_atual(),
            'num_estudantes': 1,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        unidade = self.get_unidade()
        ctx.update({
            'titulo': f'Registrar atividade de estágio/supervisão — {unidade.sigla}',
            'subtitulo': 'Registre atividades de coordenação, supervisão ou orientação de estágio da sua unidade.',
            'cancel_url': self.get_success_url(),
        })
        return ctx

    def form_valid(self, form):
        from .services import registrar_evento_prioridade1

        unidade = self.get_unidade()
        form.instance.unidade = unidade
        form.instance.criado_por = self.request.user
        form.instance.carga_reducao_horas = Decimal('0.00')
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request,
            'ATIVIDADE_ESTAGIO_UNIDADE_CRIADA',
            f'Atividade estágio {self.object.pk}; unidade {unidade.pk}; '
            f'tipo {self.object.tipo}; professor {self.object.professor_id}.',
        )
        messages.success(self.request, 'Atividade de estágio e supervisão registrada com sucesso.')
        return response


class AtividadeEstagioSupervisaoUpdateView(UnidadePrioridade1Mixin, RetornoOrigemMixin, UpdateView):
    from .forms import AtividadeEstagioSupervisaoUnidadeForm
    from .models import AtividadeEstagioSupervisao

    model = AtividadeEstagioSupervisao
    form_class = AtividadeEstagioSupervisaoUnidadeForm
    template_name = 'core/prioridade1/form_unidade.html'
    success_url = reverse_lazy('extra_curricular:supervisao_estagio')

    def get_queryset(self):
        from .models import AtividadeEstagioSupervisao
        unidade = self.get_unidade()
        return (
            AtividadeEstagioSupervisao.objects.for_user(self.request.user)
            .filter(unidade=unidade)
            .select_related('unidade', 'professor', 'curso')
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['unidade'] = self.object.unidade
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'titulo': f'Atualizar {self.object.get_tipo_display()} — {self.object.unidade.sigla}',
            'subtitulo': (
                f'Redução semanal definida pela DESUP: '
                f'{self.object.carga_reducao_horas:.2f} h (somente leitura).'
            ),
            'reducao_somente_leitura': self.object.carga_reducao_horas,
            'cancel_url': self.get_success_url(),
        })
        return ctx

    def form_valid(self, form):
        from .models import AtividadeEstagioSupervisao
        from .services import registrar_evento_prioridade1

        original = AtividadeEstagioSupervisao.objects.only('unidade_id', 'carga_reducao_horas').get(
            pk=self.object.pk
        )
        form.instance.unidade_id = original.unidade_id
        form.instance.carga_reducao_horas = original.carga_reducao_horas
        response = super().form_valid(form)
        registrar_evento_prioridade1(
            self.request,
            'ATIVIDADE_ESTAGIO_UNIDADE_ATUALIZADA',
            f'Atividade estágio {self.object.pk}; unidade {self.object.unidade_id}; tipo {self.object.tipo}.',
        )
        messages.success(self.request, 'Atividade de estágio e supervisão atualizada com sucesso.')
        return response


class AtividadeEstagioSupervisaoEncerrarView(UnidadePrioridade1Mixin, View):
    http_method_names = ['post', 'head', 'options']

    def post(self, request, pk):
        from django.db import transaction
        from django.utils import timezone
        from .models import AtividadeEstagioSupervisao
        from .services import registrar_evento_prioridade1

        unidade = self.get_unidade()
        with transaction.atomic():
            atividade = get_object_or_404(
                AtividadeEstagioSupervisao.objects.for_user(request.user)
                .filter(unidade=unidade)
                .select_for_update(),
                pk=pk,
            )
            hoje = timezone.localdate()
            if atividade.data_fim and atividade.data_fim < hoje:
                messages.info(request, 'Esta atividade de estágio/supervisão já estava encerrada.')
                return redirect('extra_curricular:supervisao_estagio')
            atividade.data_fim = max(hoje, atividade.data_inicio)
            atividade.save(update_fields=['data_fim', 'atualizado_em'])
            registrar_evento_prioridade1(
                request,
                'ATIVIDADE_ESTAGIO_UNIDADE_ENCERRADA',
                f'Atividade estágio {atividade.pk}; unidade {unidade.pk}; fim {atividade.data_fim}.',
            )
        messages.success(request, 'Atividade de estágio e supervisão encerrada com sucesso.')
        return redirect('extra_curricular:supervisao_estagio')

