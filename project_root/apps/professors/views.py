from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, View

from apps.accounts.mixins import PerfilRequiredMixin
from apps.core.models import Unidade
from .forms import ProfessorForm
from .models import Professor


class CoordenadorOnlyMixin(PerfilRequiredMixin):
    """CRUD de professores: somente coordenador da unidade."""
    allowed_profiles = ['COORDENADOR_UNIDADE']


class ProfessorListView(LoginRequiredMixin, ListView):
    model = Professor
    template_name = 'professors/professor_list.html'
    context_object_name = 'professores'

    def get_queryset(self):
        qs = Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related('cursos')
        user = self.request.user
        if not (user.is_superuser or user.perfil == 'DESUP'):
            if user.unidade:
                qs = qs.filter(unidade_principal=user.unidade)
            else:
                qs = qs.none()

        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(rh_nome__icontains=q)
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id:
            qs = qs.filter(unidade_principal_id=unidade_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        ctx['is_desup'] = user.is_superuser or user.perfil == 'DESUP'
        
        # Coordenador não pode mais CRIAR (CRUD parcial) mas pode visualizar e editar
        ctx['pode_crud'] = (
            user.is_superuser or user.perfil == 'COORDENADOR_UNIDADE' or user.perfil == 'DESUP'
        )
        ctx['pode_criar'] = (user.is_superuser or user.perfil == 'DESUP')

        unidade_atual = None
        if user.perfil == 'COORDENADOR_UNIDADE' and user.unidade:
            unidade_atual = user.unidade
            ctx['unidade_atual'] = unidade_atual
        elif user.perfil == 'DESUP' and self.request.GET.get('unidade_id'):
            unidade_atual = Unidade.objects.filter(
                pk=self.request.GET.get('unidade_id')
            ).first()
            ctx['unidade_atual'] = unidade_atual

        # Garantir que os atributos dinâmicos existam mesmo sem unidade selecionada
        professores_list = list(ctx['professores'])
        for prof in professores_list:
            prof.alocacao_map = {}
            prof.soma_horas = 0
        ctx['professores'] = professores_list

        if unidade_atual:
            try:
                from django.db import transaction as db_transaction
                from apps.courses.models import CurriculumMatrix, MatrixComponent
                with db_transaction.atomic():
                    matrizes_vigentes = CurriculumMatrix.objects.filter(
                        unidades=unidade_atual,
                        is_vigente=True,
                    ).select_related('curso').order_by('curso__sigla', 'turno')

                    colunas_cursos = []
                    for matriz in matrizes_vigentes:
                        turno_display = matriz.get_turno_display() or 'N/A'
                        colunas_cursos.append({
                            'id': matriz.id,
                            'nome': f'{matriz.curso.sigla} - {turno_display}',
                        })
                    ctx['colunas_cursos'] = colunas_cursos

                    componentes = MatrixComponent.objects.filter(
                        matriz__in=matrizes_vigentes,
                        docente__in=professores_list,
                    ).select_related('componente_curricular', 'matriz')

                    alocacao_map_por_prof = {}
                    vistos_por_prof = {}
                    for comp in componentes:
                        prof_id = comp.docente_id
                        if prof_id not in alocacao_map_por_prof:
                            alocacao_map_por_prof[prof_id] = {}
                            vistos_por_prof[prof_id] = set()
                        chave = (
                            comp.componente_curricular_id
                            if comp.compartilhado
                            else f'{comp.matriz_id}-{comp.pk}'
                        )
                        if chave in vistos_por_prof[prof_id]:
                            continue
                        vistos_por_prof[prof_id].add(chave)
                        alocacao_map_por_prof[prof_id][comp.matriz_id] = (
                            alocacao_map_por_prof[prof_id].get(comp.matriz_id, 0) + comp.ha_semanal
                        )

                    for prof in professores_list:
                        prof.alocacao_map = alocacao_map_por_prof.get(prof.id, {})
                        try:
                            prof.soma_horas = prof.ch_alocada + prof.ch_justificada
                        except Exception:
                            prof.soma_horas = 0
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Erro ao montar contexto de professores")

        return ctx
class DesupOnlyMixin(PerfilRequiredMixin):
    allowed_profiles = ['DESUP']

class ProfessorCreateView(DesupOnlyMixin, CreateView):
    model = Professor
    form_class = ProfessorForm
    template_name = 'professors/professor_form.html'
    success_url = reverse_lazy('professors:professor_list')
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        if user.perfil == 'COORDENADOR_UNIDADE' and user.unidade:
            form.instance.unidade_principal = user.unidade
        messages.success(self.request, 'Professor cadastrado com sucesso.')
        return super().form_valid(form)


class ProfessorUpdateView(CoordenadorOnlyMixin, UpdateView):
    model = Professor
    form_class = ProfessorForm
    template_name = 'professors/professor_form.html'
    success_url = reverse_lazy('professors:professor_list')

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Professor.objects.all()
        return Professor.objects.filter(unidade_principal=user.unidade)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Professor atualizado com sucesso.')
        return super().form_valid(form)


class ProfessorDeleteView(CoordenadorOnlyMixin, DeleteView):
    model = Professor
    template_name = 'professors/professor_confirm_delete.html'
    success_url = reverse_lazy('professors:professor_list')

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Professor.objects.all()
        return Professor.objects.filter(unidade_principal=user.unidade)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, 'Professor excluído com sucesso.')
        return super().delete(request, *args, **kwargs)


class ProfessorDuplicarView(CoordenadorOnlyMixin, View):
    """Duplica um professor criando uma cópia com o ID funcional alterado."""

    def post(self, request, pk):
        user = request.user
        qs = Professor.objects.all()
        if not user.is_superuser:
            qs = qs.filter(unidade_principal=user.unidade)
        original = get_object_or_404(qs, pk=pk)
        cursos = list(original.cursos.all())
        novo_id_funcional = f"COPIA-{original.id_funcional}"
        nova_matricula = f"COPIA-{original.rh_matricula}"

        original.pk = None
        original.id_funcional = novo_id_funcional
        original.rh_matricula = nova_matricula
        original.rh_nome = f"[Cópia] {original.rh_nome}"
        original.save()
        original.cursos.set(cursos)

        messages.success(
            request,
            'Professor duplicado com sucesso. Edite a cópia para ajustar os dados.',
        )
        return redirect('professors:professor_update', pk=original.pk)


@login_required
def alloc_curricular_view(request):
    user = request.user
    is_admin = user.is_superuser or user.groups.filter(name='Admin DESUP').exists()
    unidades = Unidade.objects.all().order_by('nome') if is_admin else []
    return render(request, 'professors/alloc_curricular.html', {
        'is_admin': is_admin,
        'unidades': unidades,
    })


@login_required
def htmx_tabela_alocacao(request):
    user = request.user
    queryset = Professor.objects.select_related('tipo_contrato', 'unidade_principal')
    is_admin = user.is_superuser or user.groups.filter(name='Admin DESUP').exists()
    if is_admin:
        unidade_id = request.GET.get('unidade')
        if unidade_id:
            queryset = queryset.filter(unidade_principal_id=unidade_id)
    else:
        queryset = queryset.filter(unidade_principal=user.unidade)
    return render(request, 'professors/partials/_linhas_alocacao.html', {'professores': queryset})


class ProfessorCursosPartialView(LoginRequiredMixin, View):
    """HTMX partial para retornar checkboxes de cursos de uma unidade."""

    def get(self, request, *args, **kwargs):
        unidade_id = request.GET.get('unidade_principal')
        if not unidade_id:
            return render(request, 'professors/partials/_cursos_checkboxes.html', {'cursos': []})

        from apps.courses.models import Course
        cursos = Course.objects.filter(
            course_units__unidade_id=unidade_id,
            course_units__ativo=True,
        ).order_by('nome').distinct()
        return render(request, 'professors/partials/_cursos_checkboxes.html', {'cursos': cursos})
