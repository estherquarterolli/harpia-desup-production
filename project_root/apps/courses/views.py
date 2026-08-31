from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.html import format_html, format_html_join
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.accounts.mixins import PerfilRequiredMixin
from apps.core.models import Unidade

from .forms import ClassGroupForm, CurriculumMatrixForm, MatrixComponentForm, MatrixComponentFormSet, CurricularComponentForm, CurricularComponentImportForm
from .models import ClassGroup, Course, CourseUnit, CurriculumMatrix, MatrixComponent, CurricularComponent


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_status_consolidado(matrix):
    """
    Retorna o pior status dos componentes da matriz segundo a hierarquia:
    SEM_PROFESSOR > INCOMPLETO > NAO_OFERECIDA > COMPLETO
    """
    STATUS_ORDER = {
        'SEM_PROFESSOR': 4,
        'INCOMPLETO': 3,
        'NAO_OFERECIDA': 2,
        'COMPLETO': 1,
    }
    statuses = list(matrix.componentes_da_matriz.values_list('status', flat=True))
    if not statuses:
        return None
    return max(statuses, key=lambda s: STATUS_ORDER.get(s, 0))


# ─────────────────────────────────────────────
# Base Mixin
# ─────────────────────────────────────────────

class MatrixBaseView(LoginRequiredMixin, PerfilRequiredMixin):
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']


# ─────────────────────────────────────────────
# Matrix List
# ─────────────────────────────────────────────

class CurriculumMatrixListView(MatrixBaseView, ListView):
    model = CurriculumMatrix
    template_name = 'courses/matrix_list.html'
    context_object_name = 'matrices'

    def _get_queryset_base(self):
        return CurriculumMatrix.objects.select_related(
            'curso',
        ).prefetch_related(
            'unidades',
        ).order_by('curso__nome')

    def _apply_filters(self, qs):
        """Aplica filtros vindos de GET params."""
        user = self.request.user

        # Escopo por perfil (Regra de Negócio — escopo por unidade)
        if not (user.perfil == 'DESUP' or user.is_superuser):
            if user.unidade:
                qs = qs.filter(unidades=user.unidade)
            else:
                qs = qs.none()
            # Rascunhos são visíveis somente para a DESUP até a publicação —
            # a unidade nunca enxerga matrizes em rascunho (nem forçando ?status=rascunho).
            qs = qs.exclude(is_rascunho=True)

        # Filtro de unidade (Admin DESUP pode selecionar)
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id and (user.perfil == 'DESUP' or user.is_superuser):
            qs = qs.filter(unidades__id=unidade_id)

        # Filtro de curso
        curso_id = self.request.GET.get('curso_id')
        if curso_id:
            qs = qs.filter(curso_id=curso_id)

        # Filtro de Status
        status = self.request.GET.get('status', '')
        if status == 'vigente':
            qs = qs.filter(is_vigente=True, is_rascunho=False)
        elif status == 'rascunho':
            qs = qs.filter(is_rascunho=True)
        elif status == 'historico':
            qs = qs.filter(is_vigente=False, is_rascunho=False)

        return qs

    def get_queryset(self):
        return self._apply_filters(self._get_queryset_base())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Sum, Count
        
        ctx['pode_editar'] = True
        ctx['is_desup'] = self.request.user.perfil == 'DESUP' or self.request.user.is_superuser
        ctx['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        ctx['semestres'] = [f'{i}º Semestre' for i in range(1, 9)]
        
        unidade_id = self.request.GET.get('unidade_id')
        cursos_qs = Course.objects.all()
        if unidade_id:
            cursos_qs = cursos_qs.filter(course_units__unidade_id=unidade_id)
        elif not (self.request.user.perfil == 'DESUP' or self.request.user.is_superuser):
            cursos_qs = cursos_qs.filter(course_units__unidade_id=self.request.user.unidade_id)
            if not unidade_id and self.request.user.unidade_id:
                unidade_id = str(self.request.user.unidade_id)

        ctx['cursos'] = cursos_qs.distinct().order_by('nome')
        ctx['unidade_selecionada_id'] = unidade_id

        # Annotate matrices with total components and total hours for display
        matrices = ctx.get('matrices', self.get_queryset())
        matrices = matrices.annotate(
            qtd_componentes=Count('componentes_da_matriz'),
            ch_total=Sum('componentes_da_matriz__carga_horaria')
        )
        ctx['matrices'] = matrices

        return ctx


class CurriculumMatrixListPartialView(CurriculumMatrixListView):
    """
    View parcial chamada pelo HTMX ao alterar filtros.
    Retorna apenas o fragmento da tabela (_table_body.html).
    """
    template_name = 'courses/matrix/partials/_table_body.html'

    def get(self, request, *args, **kwargs):
        # Verifica se é realmente uma requisição HTMX (segurança)
        if not request.headers.get('HX-Request'):
            return redirect('courses:matrix_list')
        return super().get(request, *args, **kwargs)


# ─────────────────────────────────────────────
# Matrix Form (Create / Update)
# ─────────────────────────────────────────────

class CurriculumMatrixFormsetMixin:
    formset_prefix = 'componentes'

    def get_component_formset(self):
        kwargs = {
            'instance': self.object,
            'prefix': self.formset_prefix,
        }
        if self.request.method in ('POST', 'PUT'):
            kwargs['data'] = self.request.POST
        return MatrixComponentFormSet(**kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['component_formset'] = kwargs.get('component_formset') or self.get_component_formset()
        unidade = getattr(self.request.user, 'unidade', None)
        if self.request.user.perfil == 'DESUP':
            uid = self.request.GET.get('unidade_id') or self.request.POST.get('unidade')
            if uid:
                unidade = Unidade.objects.filter(pk=uid).first()
        ctx['pode_editar'] = (
            self.request.user.is_superuser
            or self.request.user.perfil == 'DESUP'
            or self.request.user.perfil == 'COORDENADOR_UNIDADE'
        )
        ctx['is_desup'] = self.request.user.perfil == 'DESUP' or self.request.user.is_superuser
        if unidade:
            from .models import CurricularComponent
            ctx['disciplinas_unidade'] = CurricularComponent.objects.filter(
                vinculos_matriz__matriz__unidades=unidade
            ).distinct().order_by('nome')

        # Adicionar o mapeamento de componentes em JSON
        from .models import CurricularComponent
        import json
        mapping = {c.id: {"codigo": c.codigo, "carga_horaria": c.carga_horaria_padrao} for c in CurricularComponent.objects.all()}
        ctx['component_codes_json'] = json.dumps(mapping)

        return ctx

    def form_valid(self, form):
        self.object = form.save(commit=False)
        component_formset = self.get_component_formset()

        if not component_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, component_formset=component_formset)
            )

        # Salvar Rascunho vs Salvar e Publicar
        salvar_rascunho = self.request.POST.get('salvar_rascunho') == 'true'
        if salvar_rascunho:
            self.object.is_rascunho = True
            self.object.is_vigente = False
        else:
            self.object.is_rascunho = False
            self.object.is_vigente = True
            # CORR-011: sem auto-arquivamento. Publicar/duplicar uma matriz NÃO arquiva mais
            # as demais do mesmo curso — matrizes de turnos diferentes coexistem como vigentes.
            # O arquivamento passa a ser manual (CORR-012) ou em massa na virada de semestre.

        self.object.save()
        form.save_m2m()
        component_formset.instance = self.object
        component_formset.save()
        messages.success(self.request, 'Matriz salva com sucesso.')
        return redirect(self.get_success_url())


class CurriculumMatrixCreateView(CurriculumMatrixFormsetMixin, MatrixBaseView, CreateView):
    model = CurriculumMatrix
    form_class = CurriculumMatrixForm
    template_name = 'courses/matrix_form.html'
    success_url = reverse_lazy('courses:matrix_list')

    def dispatch(self, request, *args, **kwargs):
        # Quem cuida do anônimo é o LoginRequiredMixin, e ele só age dentro do
        # super().dispatch() — ler `perfil` antes disso estoura AttributeError em
        # AnonymousUser (500 em vez do redirecionamento para o login).
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not (request.user.is_superuser or request.user.perfil == 'DESUP'):
            messages.error(request, 'Somente a DESUP pode cadastrar nova matriz.')
            return redirect('courses:matrix_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Pré-selecionar unidade e curso se vieram na querystring
        unidade_id = self.request.GET.get('unidade_id')
        curso_id = self.request.GET.get('curso_id')
        if unidade_id:
            initial['unidade'] = unidade_id
        if curso_id:
            initial['curso'] = curso_id
        return initial


class CurriculumMatrixUpdateView(CurriculumMatrixFormsetMixin, MatrixBaseView, UpdateView):
    model = CurriculumMatrix
    form_class = CurriculumMatrixForm
    template_name = 'courses/matrix_form.html'
    success_url = reverse_lazy('courses:matrix_list')

    def dispatch(self, request, *args, **kwargs):
        # Anônimo é problema do LoginRequiredMixin (dentro do super().dispatch()):
        # tocar em `perfil` antes disso quebra com AnonymousUser.
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        # Somente a DESUP (ou super admin) pode editar matriz — a unidade não edita.
        if not (request.user.is_superuser or request.user.perfil == 'DESUP'):
            messages.error(request, 'Somente a DESUP pode editar matrizes.')
            return redirect('courses:matrix_list')

        obj = self.get_object()

        # Regra principal: APENAS matrizes em rascunho podem ser editadas
        if not obj.is_rascunho:
            messages.error(request, 'Somente matrizes com status Rascunho podem ser editadas.')
            return redirect('courses:matrix_list')

        return super().dispatch(request, *args, **kwargs)


from django.views.generic import DetailView

class CurriculumMatrixDetailView(MatrixBaseView, DetailView):
    model = CurriculumMatrix
    template_name = 'courses/matrix/detail.html'
    context_object_name = 'matrix'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['componentes'] = self.object.componentes_da_matriz.select_related('componente_curricular').all()
        ctx['is_desup'] = self.request.user.perfil == 'DESUP' or self.request.user.is_superuser
        return ctx

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.perfil == 'DESUP':
            return qs
        if user.unidade:
            # Unidade vê só as suas matrizes já publicadas; rascunho é exclusivo da DESUP.
            return qs.filter(unidades=user.unidade).exclude(is_rascunho=True)
        return qs.none()


# ─────────────────────────────────────────────
# CORR-012: Arquivar / Reativar matriz (ação manual, DESUP-only)
# ─────────────────────────────────────────────

class _MatrixDesupActionView(MatrixBaseView, View):
    """Base das ações de status de matriz — só DESUP/superuser, via POST."""

    def dispatch(self, request, *args, **kwargs):
        # Rota de escrita: sem sessão, o LoginRequiredMixin (dentro do super().dispatch())
        # manda para o login. Checar `perfil` antes disso estouraria em AnonymousUser.
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not (request.user.is_superuser or request.user.perfil == 'DESUP'):
            messages.error(request, 'Somente a DESUP pode alterar o status de matrizes.')
            return redirect('courses:matrix_list')
        return super().dispatch(request, *args, **kwargs)

    def _redirect_back(self, request):
        return redirect(request.META.get('HTTP_REFERER') or 'courses:matrix_list')


class ArquivarMatrizView(_MatrixDesupActionView):
    """Arquiva uma matriz vigente → Histórico (não toca nas demais do curso)."""

    def post(self, request, pk):
        from apps.accounts.views import registrar_auditoria
        matriz = get_object_or_404(CurriculumMatrix, pk=pk)
        if matriz.is_rascunho:
            messages.error(request, 'Rascunhos não podem ser arquivados.')
            return self._redirect_back(request)
        if not matriz.is_vigente:
            messages.info(request, 'Esta matriz já está no histórico.')
            return self._redirect_back(request)
        matriz.is_vigente = False
        matriz.is_rascunho = False
        matriz.save(update_fields=['is_vigente', 'is_rascunho'])
        sigla = matriz.curso.sigla if matriz.curso_id else '?'
        registrar_auditoria(
            request, acao='MATRIZ_ARQUIVADA', usuario=request.user,
            detalhes=f'Matriz #{matriz.pk} "{matriz.nome}" ({sigla}) arquivada.',
        )
        messages.success(request, f'Matriz "{matriz.nome or matriz.pk}" arquivada.')
        return self._redirect_back(request)


class ReativarMatrizView(_MatrixDesupActionView):
    """Reativa uma matriz arquivada → Vigente. Não arquiva as demais do curso (CORR-011)."""

    def post(self, request, pk):
        from apps.accounts.views import registrar_auditoria
        matriz = get_object_or_404(CurriculumMatrix, pk=pk)
        if matriz.is_rascunho:
            messages.error(request, 'Rascunhos não são reativados por aqui — use o fluxo de publicação.')
            return self._redirect_back(request)
        if matriz.is_vigente:
            messages.info(request, 'Esta matriz já está vigente.')
            return self._redirect_back(request)
        matriz.is_vigente = True
        matriz.is_rascunho = False
        matriz.save(update_fields=['is_vigente', 'is_rascunho'])
        sigla = matriz.curso.sigla if matriz.curso_id else '?'
        registrar_auditoria(
            request, acao='MATRIZ_REATIVADA', usuario=request.user,
            detalhes=f'Matriz #{matriz.pk} "{matriz.nome}" ({sigla}) reativada.',
        )
        messages.success(request, f'Matriz "{matriz.nome or matriz.pk}" reativada.')
        return self._redirect_back(request)


# ─────────────────────────────────────────────
# HTMX: Adicionar nova linha ao formset
# ─────────────────────────────────────────────

class MatrixAddFormsetRowView(LoginRequiredMixin, View):
    """
    Retorna um fragmento HTML com uma nova linha vazia do formset.
    Chamada via HTMX (hx-get) ao clicar em "Adicionar Componente".
    Não salva nada — apenas renderiza o template de linha com o form vazio.
    """

    def get(self, request, *args, **kwargs):
        if not request.headers.get('HX-Request'):
            return HttpResponse(status=400)

        prefix = request.GET.get('prefix', 'componentes')
        row_index = int(request.GET.get('row_index', 0))

        # Cria um form vazio com o prefix e índice corretos
        form_row = MatrixComponentForm(prefix=f'{prefix}-{row_index}')

        return render(request, 'courses/matrix/partials/_formset_row.html', {
            'form_row': form_row,
            'row_index': row_index,
        })


class LoadCoursesByUnitView(LoginRequiredMixin, View):
    """
    Retorna JSON de cursos filtrados pela unidade.
    Chamada via fetch/HTMX com parâmetro unidade_id.
    """
    def get(self, request, *args, **kwargs):
        unidade_id = request.GET.get('unidade_id') or request.GET.get('unidade')
        use_global_courses = request.GET.get('global') == '1'
        if use_global_courses:
            cursos_qs = Course.objects.all()
            if unidade_id:
                cursos_qs = cursos_qs.filter(course_units__unidade_id=unidade_id)
            cursos = [
                {
                    'id': c.id,
                    'sigla': c.sigla,
                    'nome': c.nome,
                    'unidade': '',
                }
                for c in cursos_qs.distinct().order_by('nome')
            ]
        elif unidade_id:
            cursos_qs = Course.objects.filter(
                course_units__unidade_id=unidade_id,
                course_units__ativo=True,
            ).distinct().order_by('nome')
            cursos = [
                {
                    'id': c.id,
                    'sigla': c.sigla,
                    'nome': c.nome,
                    'unidade': '',
                }
                for c in cursos_qs
            ]
        else:
            cursos_qs = Course.objects.filter(
                course_units__ativo=True,
            ).distinct().order_by('nome')
            cursos = [
                {
                    'id': c.id,
                    'sigla': c.sigla,
                    'nome': c.nome,
                    'unidade': '',
                }
                for c in cursos_qs
            ]
        
        # Se HTMX, retorna options HTML; se fetch JSON, retorna JSON
        if request.headers.get('HX-Request'):
            # O Django 6.0 removeu `format_html()` sem argumentos. O rótulo fixo entra
            # como argumento (em vez de mark_safe) e a lista sai por format_html_join,
            # que escapa sigla/nome do curso — nada de HTML cru vindo do banco.
            opcoes = format_html('<option value="">{}</option>', 'Todos os Cursos')
            opcoes += format_html_join(
                '',
                '<option value="{}">{} - {}</option>',
                ((c['id'], c['sigla'], c['nome']) for c in cursos),
            )
            return HttpResponse(opcoes)
        
        from django.http import JsonResponse
        return JsonResponse(cursos, safe=False)


class LoadMatricesForDuplicateView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """
    Retorna options de matrizes filtradas para o campo de duplicacao.
    """
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get(self, request, *args, **kwargs):
        unidade_id = request.GET.get('unidade_id') or request.GET.get('unidade')
        curso_id = request.GET.get('curso_id') or request.GET.get('curso')
        qs = CurriculumMatrix.objects.select_related('curso').prefetch_related('unidades')
        # Escopo por unidade para COORDENADOR_UNIDADE
        if not (request.user.perfil == 'DESUP' or request.user.is_superuser):
            if request.user.unidade:
                qs = qs.filter(unidades=request.user.unidade)
            else:
                qs = qs.none()
            # CORR-008: rascunho é exclusivo da DESUP até a publicação. Sem isto o
            # <select> ofereceria à unidade uma matriz que ela não lista nem abre.
            qs = qs.exclude(is_rascunho=True)
        if unidade_id and (request.user.perfil == 'DESUP' or request.user.is_superuser):
            qs = qs.filter(unidades__id=unidade_id)
        if curso_id:
            qs = qs.filter(curso_id=curso_id)
        qs = qs.order_by('curso__nome', 'nome').distinct()

        def _linhas():
            for matriz in qs:
                unidade_siglas = ', '.join(u.sigla for u in matriz.unidades.all())
                yield (
                    matriz.pk,
                    matriz.curso.sigla if matriz.curso_id else '?',
                    matriz.nome or 'Matriz',
                    unidade_siglas or 'Global',
                )

        # `format_html()` sem argumentos deixou de existir no Django 6.0; o rótulo fixo
        # vira argumento e as linhas saem por format_html_join, que escapa nome de
        # curso/matriz vindo do banco.
        opcoes = format_html('<option value="">{}</option>', 'Nao duplicar (criar em branco)')
        opcoes += format_html_join('', '<option value="{}">{} - {} ({})</option>', _linhas())
        return HttpResponse(opcoes)


_ALLOWED_FORMSET_PREFIXES = {'componentes'}


class ImportPreviousMatrixView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """
    Busca a última matriz do curso selecionado e retorna as linhas do formset pré-preenchidas.
    Chamada via HTMX.
    """
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get(self, request, *args, **kwargs):
        curso_id = request.GET.get('curso_id')
        prefix = request.GET.get('prefix', 'componentes')

        # Rejeita prefixos fora da lista permitida para evitar XSS refletido
        if prefix not in _ALLOWED_FORMSET_PREFIXES:
            prefix = 'componentes'

        if not curso_id:
            return HttpResponse('')

        # Escopo por unidade para COORDENADOR_UNIDADE
        qs_matriz = CurriculumMatrix.objects.filter(curso_id=curso_id)
        if not (request.user.perfil == 'DESUP' or request.user.is_superuser):
            if request.user.unidade:
                qs_matriz = qs_matriz.filter(unidades=request.user.unidade)
            else:
                qs_matriz = qs_matriz.none()

        ultima_matriz = qs_matriz.order_by('-id').first()
        if not ultima_matriz:
            return HttpResponse('<div class="p-4 text-sm text-amber-600 bg-amber-50 rounded-xl text-center">Nenhuma matriz anterior encontrada para este curso.</div>')

        componentes = ultima_matriz.componentes_da_matriz.all()

        if not componentes.exists():
            return HttpResponse('<div class="p-4 text-sm text-amber-600 bg-amber-50 rounded-xl text-center">A matriz anterior deste curso não possui componentes.</div>')

        html = ''
        from django.template.loader import render_to_string

        for i, comp in enumerate(componentes):
            initial_data = {
                'componente_curricular': comp.componente_curricular_id,
                'periodo': comp.periodo,
                'codigo': comp.codigo,
                'carga_horaria': comp.carga_horaria,
                'creditos': comp.creditos,
                'carga_horaria_semanal': comp.carga_horaria_semanal,
                'status': comp.status,
                'observacoes': comp.observacoes,
            }
            form_row = MatrixComponentForm(prefix=f'{prefix}-{i}', initial=initial_data)

            html += render_to_string('courses/matrix/partials/_formset_row.html', {
                'form_row': form_row,
                'row_index': i,
            })

        # prefix já foi validado contra a allowlist acima, seguro para uso aqui
        total_forms_id = f'id_{prefix}-TOTAL_FORMS'
        html += format_html(
            '<script>document.getElementById({}).value = {};</script>',
            total_forms_id,
            componentes.count(),
        )

        return HttpResponse(html)


# ─────────────────────────────────────────────
# ClassGroup
# ─────────────────────────────────────────────

class ClassGroupListView(MatrixBaseView, ListView):
    model = ClassGroup
    template_name = 'courses/classgroup_list.html'
    context_object_name = 'classgroups'


class ClassGroupCreateView(MatrixBaseView, CreateView):
    model = ClassGroup
    form_class = ClassGroupForm
    template_name = 'courses/classgroup_form.html'
    success_url = reverse_lazy('courses:classgroup_list')


# ─────────────────────────────────────────────
# Popup: Verificar e Copiar Matriz Existente
# ─────────────────────────────────────────────

class BuscarMatrizExistenteView(LoginRequiredMixin, View):
    """Verifica se já existe uma matriz para o curso selecionado."""
    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        curso_id = request.GET.get('curso_id')
        if not curso_id:
            return JsonResponse({'existe': False})

        qs = CurriculumMatrix.objects.filter(curso_id=curso_id)
        # CORR-008: o endpoint devolve id e nome da matriz — sem escopo, qualquer
        # logado descobriria matrizes de outras unidades e rascunhos ainda não
        # publicados. Mesmo recorte da listagem (_apply_filters).
        if not (request.user.perfil == 'DESUP' or request.user.is_superuser):
            if request.user.unidade:
                qs = qs.filter(unidades=request.user.unidade)
            else:
                qs = qs.none()
            qs = qs.exclude(is_rascunho=True)

        matriz = qs.order_by('-id').first()
        if matriz:
            return JsonResponse({
                'existe': True,
                'matriz_id': matriz.pk,
                'nome': str(matriz),
            })
        return JsonResponse({'existe': False})


class DadosMatrizCopiarView(LoginRequiredMixin, PerfilRequiredMixin, View):
    """Retorna JSON com os componentes de uma matriz para pré-preencher o formset."""
    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get(self, request, pk, *args, **kwargs):
        from django.http import JsonResponse
        qs = CurriculumMatrix.objects.all()
        # Restringe COORDENADOR_UNIDADE à sua própria unidade
        if not (request.user.perfil == 'DESUP' or request.user.is_superuser):
            if request.user.unidade:
                qs = qs.filter(unidades=request.user.unidade)
            else:
                return JsonResponse({'componentes': []}, status=403)
            # CORR-008: sem isto a unidade lê a composição de um rascunho cujo
            # detalhe (CurriculumMatrixDetailView) já devolve 404 para ela.
            qs = qs.exclude(is_rascunho=True)
        try:
            matriz = qs.get(pk=pk)
        except CurriculumMatrix.DoesNotExist:
            return JsonResponse({'componentes': []}, status=404)
        
        componentes = []
        for comp in matriz.componentes_da_matriz.select_related('componente_curricular').all():
            cc = comp.componente_curricular
            componentes.append({
                'componente_curricular': cc.id if cc else '',
                'componente_curricular_nome': cc.nome if cc else '',
                'codigo': comp.codigo,
                'periodo': comp.periodo,
                'carga_horaria': comp.carga_horaria,
                'creditos': comp.creditos,
                'carga_horaria_semanal': str(comp.carga_horaria_semanal),
            })
        return JsonResponse({'componentes': componentes})


class BuscarComponenteView(LoginRequiredMixin, View):
    """
    Retorna JSON com componentes curriculares filtrados por texto.
    Usado pelo autocomplete no formulário de matriz.
    """
    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        q = request.GET.get('q', '').strip()
        if len(q) < 2:
            return JsonResponse({'resultados': []})

        from django.db.models import Q
        qs = CurricularComponent.objects.filter(
            Q(nome__icontains=q) | Q(codigo__icontains=q)
        ).order_by('nome')[:30]

        resultados = [
            {
                'id': c.id,
                'nome': c.nome,
                'codigo': c.codigo,
                'carga_horaria': c.carga_horaria_padrao,
                'creditos': c.creditos,
                'label': f"{c.codigo + ' — ' if c.codigo else ''}{c.nome} ({c.carga_horaria_padrao}h)",
            }
            for c in qs
        ]
        return JsonResponse({'resultados': resultados})



# ─────────────────────────────────────────────
# Componentes Curriculares (DESUP)
# ─────────────────────────────────────────────

class DesupOnlyMixin(LoginRequiredMixin, PerfilRequiredMixin):
    """Acesso restrito a usuários com perfil DESUP ou superusuario."""
    allowed_profiles = ['DESUP']

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and
                (request.user.is_superuser or request.user.perfil == 'DESUP')):
            messages.error(request, 'Acesso restrito à equipe DESUP.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class CurricularComponentListView(DesupOnlyMixin, ListView):
    model = CurricularComponent
    template_name = 'courses/component_list.html'
    context_object_name = 'componentes'

    def get_queryset(self):
        qs = CurricularComponent.objects.order_by('nome')
        q = self.request.GET.get('q', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(nome__icontains=q) |
                Q(codigo__icontains=q)
            )
        return qs


class CurricularComponentImportView(DesupOnlyMixin, View):
    """Importa Componentes Curriculares de uma planilha Excel ou do Google Sheets.

    Regra do cliente: casa pelo código.
      - Código novo -> cria direto.
      - Código já existente -> não mexe sozinho; pede confirmação numa
        segunda tela (mostrando valor atual x valor da planilha) antes de
        sobrescrever.
    """
    template_name = 'courses/component_import.html'
    SESSION_KEY = 'component_import_rows'

    def get(self, request):
        request.session.pop(self.SESSION_KEY, None)
        return render(request, self.template_name, {'form': CurricularComponentImportForm()})

    def post(self, request):
        from .import_services import (
            SpreadsheetImportError,
            apply_import,
            parse_google_sheets_url,
            parse_uploaded_spreadsheet,
            preview_import,
        )

        if request.POST.get('confirm_step') == '1':
            rows = request.session.get(self.SESSION_KEY)
            if rows is None:
                messages.error(request, 'A confirmação expirou — envie a planilha de novo.')
                return redirect('courses:component_import')

            previews = preview_import(rows)
            replace_codigos = set(request.POST.getlist('replace'))
            summary = apply_import(previews, replace_codigos)
            request.session.pop(self.SESSION_KEY, None)
            self._flash_summary(request, summary)
            return render(request, self.template_name, {'form': CurricularComponentImportForm(), 'summary': summary})

        form = CurricularComponentImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        try:
            if form.cleaned_data.get('arquivo'):
                rows = parse_uploaded_spreadsheet(form.cleaned_data['arquivo'])
            else:
                rows = parse_google_sheets_url(form.cleaned_data['google_sheets_url'])
        except SpreadsheetImportError as e:
            form.add_error(None, str(e))
            return render(request, self.template_name, {'form': form})

        if not rows:
            messages.warning(request, 'Nenhuma linha de dados encontrada na planilha.')
            return render(request, self.template_name, {'form': CurricularComponentImportForm()})

        previews = preview_import(rows)
        duplicates = [p for p in previews if p.status == 'duplicate']

        if not duplicates:
            # nada pra confirmar — aplica direto (só 'new' e possíveis 'error')
            summary = apply_import(previews, replace_codigos=set())
            self._flash_summary(request, summary)
            return render(request, self.template_name, {'form': CurricularComponentImportForm(), 'summary': summary})

        # existe pelo menos um código repetido — pede confirmação antes de tocar no banco
        request.session[self.SESSION_KEY] = rows
        novos = [p for p in previews if p.status == 'new']
        erros = [p for p in previews if p.status == 'error']
        return render(request, self.template_name, {
            'form': CurricularComponentImportForm(),
            'preview_duplicates': duplicates,
            'preview_novos_count': len(novos),
            'preview_erros_count': len(erros),
        })

    @staticmethod
    def _flash_summary(request, summary):
        if summary.added:
            messages.success(request, f'{len(summary.added)} componente(s) curricular(es) criado(s).')
        if summary.replaced:
            messages.success(request, f'{len(summary.replaced)} componente(s) substituído(s) pelos dados da planilha.')
        if summary.skipped:
            messages.info(request, f'{len(summary.skipped)} linha(s) mantida(s) como estavam (não marcadas para substituição).')
        if summary.errors:
            messages.warning(request, f'{len(summary.errors)} linha(s) com erro — veja o detalhamento abaixo.')


class CurricularComponentCreateView(DesupOnlyMixin, CreateView):
    model = CurricularComponent
    form_class = CurricularComponentForm
    template_name = 'courses/component_form.html'
    success_url = reverse_lazy('courses:component_list')

    def form_valid(self, form):
        from django.db import IntegrityError
        try:
            response = super().form_valid(form)
            messages.success(self.request, 'Componente curricular criado com sucesso.')
            return response
        except IntegrityError:
            form.add_error('nome', 'Já existe um componente curricular com este nome.')
            return self.form_invalid(form)


class CurricularComponentUpdateView(DesupOnlyMixin, UpdateView):
    model = CurricularComponent
    form_class = CurricularComponentForm
    template_name = 'courses/component_form.html'
    success_url = reverse_lazy('courses:component_list')

    def form_valid(self, form):
        from django.db import IntegrityError
        try:
            response = super().form_valid(form)
            messages.success(self.request, 'Componente curricular atualizado com sucesso.')
            return response
        except IntegrityError:
            form.add_error('nome', 'Já existe um componente curricular com este nome.')
            return self.form_invalid(form)


class CurricularComponentDeleteView(DesupOnlyMixin, DeleteView):
    model = CurricularComponent
    template_name = 'courses/component_confirm_delete.html'
    success_url = reverse_lazy('courses:component_list')

    def form_valid(self, form):
        # `ProtectedError` mora em django.db.models (django.db.models.deletion) e nunca
        # foi exportado por django.db — o import errado estourava ImportError antes do
        # try, quebrando TODA exclusão de disciplina, inclusive as legítimas.
        from django.db.models import ProtectedError
        try:
            nome = self.object.nome
            response = super().form_valid(form)
            messages.success(self.request, f'Componente "{nome}" excluído com sucesso.')
            return response
        except ProtectedError:
            messages.error(
                self.request,
                'Não é possível excluir este componente pois ele está vinculado a uma ou mais matrizes.',
            )
            return redirect('courses:component_list')

