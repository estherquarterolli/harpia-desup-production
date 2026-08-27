import logging
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from apps.accounts.mixins import PerfilRequiredMixin

logger = logging.getLogger(__name__)


def custom_500(request):
    return render(request, '500.html', status=500)


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
        from apps.core.models import Unidade

        ctx['total_professores'] = Professor.objects.count()
        unidades_ativas = Unidade.objects.filter(status=True)
        ctx['total_unidades'] = unidades_ativas.count()

        nao_conformes = []
        conformes = 0
        for unidade in unidades_ativas:
            profs = Professor.objects.filter(unidade_principal=unidade, status='Ativo')
            if not profs.exists():
                conformes += 1
                continue
            todos_ok = all(p.percentual_alocado >= 100 for p in profs)
            if todos_ok:
                conformes += 1
            else:
                nao_conformes.append({'id': unidade.id, 'nome': unidade.nome})

        ctx['unidades_nao_conformes'] = nao_conformes
        ctx['unidades_conformes_count'] = conformes
        if ctx['total_unidades']:
            pct = round((conformes / ctx['total_unidades']) * 100)
            ctx['conformidade'] = f'{pct}%'
        else:
            ctx['conformidade'] = '0%'

        # Professores para a tabela de consulta
        professores_qs = Professor.objects.select_related('tipo_contrato', 'unidade_principal').order_by('rh_nome')
        ctx['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        ctx['eixo_choices'] = Professor.MateriaChoices.choices

        # Estrutura esperada pelo partial _professor_table.html
        ctx['alocacoes_dashboard'] = [
            {
                'prof': prof,
                'unit': prof.unidade_principal,
                'subjects': prof.get_disciplinas_alocadas(),
                'ha': prof.ha,
            }
            for prof in professores_qs[:50]
        ]
        return ctx


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

        qs = Professor.objects.select_related('tipo_contrato', 'unidade_principal').order_by('rh_nome')

        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(rh_nome__icontains=q)
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id:
            qs = qs.filter(unidade_principal_id=unidade_id)
        eixo = self.request.GET.get('eixo')
        if eixo:
            qs = qs.filter(materia=eixo)
        turno = self.request.GET.get('turno')
        if turno:
            qs = qs.filter(disponibilidades__turno=turno).distinct()

        ctx['alocacoes_dashboard'] = [
            {
                'prof': prof,
                'unit': prof.unidade_principal,
                'subjects': prof.get_disciplinas_alocadas(),
                'ha': prof.ha,
            }
            for prof in qs[:50]
        ]
        return ctx


class DashboardUnidadeView(LoginRequiredMixin, PerfilRequiredMixin, TemplateView):
    template_name = 'dashboard/unidade.html'
    allowed_profiles = ['COORDENADOR_UNIDADE']

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

    def get_queryset(self):
        return CourseUnit.objects.filter(unidade_id=self.kwargs['unidade_pk']).order_by('curso__nome')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unidade'] = self.get_unidade()
        return ctx

class CursoCreateView(CursoBaseView, CreateView):
    model = Course
    fields = ['nome', 'sigla']
    template_name = 'core/curso_form.html'

    def get_success_url(self):
        return reverse_lazy('core:curso_list', kwargs={'unidade_pk': self.kwargs['unidade_pk']})

    def form_valid(self, form):
        curso = form.save(commit=False)
        curso_existente = Course.objects.filter(sigla=curso.sigla).first()
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
        return get_object_or_404(CourseUnit, pk=self.kwargs['pk']).curso

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
from django import forms

_JANELA_FIELD_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:border-[#1e4e8c] outline-none transition bg-white'
_JANELA_SELECT_CSS = 'w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm bg-slate-50 focus:bg-white focus:border-[#1e4e8c] outline-none transition'


class JanelaEntregaCreateForm(forms.ModelForm):
    """Form para criar nova janela — data_inicio e data_fim configuráveis."""
    class Meta:
        model = JanelaEntrega
        fields = ['semestre', 'data_inicio', 'data_fim', 'status', 'unidade']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date', 'class': _JANELA_FIELD_CSS}),
            'data_fim': forms.DateInput(attrs={'type': 'date', 'class': _JANELA_FIELD_CSS}),
            'semestre': forms.TextInput(attrs={'class': _JANELA_FIELD_CSS, 'placeholder': 'Ex: 2026.1'}),
            'status': forms.Select(attrs={'class': _JANELA_SELECT_CSS}),
            'unidade': forms.Select(attrs={'class': _JANELA_SELECT_CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        self.fields['data_inicio'].initial = timezone.now().date()
        self.fields['status'].choices = [
            (JanelaEntrega.StatusChoices.ABERTO, 'Aberto'),
            (JanelaEntrega.StatusChoices.FECHADO, 'Fechado'),
        ]
        self.fields['status'].initial = JanelaEntrega.StatusChoices.ABERTO
        self.fields['unidade'].empty_label = 'Todas as unidades'
        self.fields['unidade'].help_text = ''

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('data_inicio')
        fim = cleaned_data.get('data_fim')
        if inicio and fim and fim < inicio:
            raise forms.ValidationError({'data_fim': 'A data de fim não pode ser anterior à data de início.'})
        return cleaned_data


class JanelaEntregaUpdateForm(forms.ModelForm):
    """Form para editar janela — permite editar data_inicio e status."""
    class Meta:
        model = JanelaEntrega
        fields = ['semestre', 'data_inicio', 'data_fim', 'status', 'unidade']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date', 'class': _JANELA_FIELD_CSS}),
            'data_fim': forms.DateInput(attrs={'type': 'date', 'class': _JANELA_FIELD_CSS}),
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
        inicio = cleaned_data.get('data_inicio')
        fim = cleaned_data.get('data_fim')
        if inicio and fim and fim < inicio:
            raise forms.ValidationError({'data_fim': 'A data de fim não pode ser anterior à data de início.'})
        # Impede que uma janela global seja convertida em janela de unidade específica
        if self.instance.pk and self.instance.unidade is None:
            nova_unidade = cleaned_data.get('unidade')
            if nova_unidade is not None:
                raise forms.ValidationError(
                    'Não é possível vincular uma janela global a uma unidade específica. '
                    'Para fechar apenas para uma unidade, crie uma nova janela com status "Fechado" para aquela unidade.'
                )
        return cleaned_data

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

    def get_queryset(self):
        from django.db.models import Q
        from apps.core.services import fechar_janelas_expiradas
        fechar_janelas_expiradas()
        qs = JanelaEntrega.objects.all()
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
        ctx['filtro_status'] = self.request.GET.get('status', '')
        ctx['filtro_unidade'] = self.request.GET.get('unidade_id', '')
        ctx['selected_status'] = ctx['filtro_status']
        ctx['selected_unidade_id'] = ctx['filtro_unidade']
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


class MarcarNotificacaoLidaView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from apps.core.models import Notificacao
        from django.shortcuts import get_object_or_404
        notificacao = get_object_or_404(Notificacao, pk=pk)
        if _usuario_pode_marcar_notificacao(request.user, notificacao):
            notificacao.lida = True
            notificacao.save()
        redirect_url = notificacao.url_acao or '/'
        return redirect(redirect_url)

    def post(self, request, pk):
        from apps.core.models import Notificacao
        from django.shortcuts import get_object_or_404
        notificacao = get_object_or_404(Notificacao, pk=pk)
        if _usuario_pode_marcar_notificacao(request.user, notificacao):
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

