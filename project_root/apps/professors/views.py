from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from apps.accounts.mixins import PerfilRequiredMixin
from apps.core.busca import filtrar_contem
from apps.core.models import Notificacao, Unidade
from .forms import ProfessorForm, SolicitacaoCadastroProfessorForm
from .models import ContractType, Professor


def _bulk_ch_alocada(professor_ids):
    """
    `Professor.ch_alocada` pra vários professores numa query só, em vez de N.

    ch_alocada é @property (soma de MatrixComponent com dedup por
    "compartilhado"); chamá-la por professor num loop de listagem abre uma
    query por professor — com ~190 professores isso sozinho já estourava os
    30s de timeout do Vercel. Mesma lógica de dedup, calculada em lote.
    """
    from apps.courses.models import MatrixComponent

    componentes = MatrixComponent.objects.filter(
        docente_id__in=professor_ids,
        matriz__is_vigente=True,
    ).values("docente_id", "componente_curricular_id", "compartilhado", "carga_horaria", "pk")

    mapa = {}
    vistos = {}
    for comp in componentes:
        pid = comp["docente_id"]
        vistos.setdefault(pid, set())
        chave = comp["componente_curricular_id"] if comp["compartilhado"] else comp["pk"]
        if chave in vistos[pid]:
            continue
        vistos[pid].add(chave)
        ha_semanal = (comp["carga_horaria"] or 0) / 20.0
        mapa[pid] = mapa.get(pid, 0) + ha_semanal
    return mapa


def _bulk_ch_justificada(professor_ids):
    """
    `Professor.ch_justificada` (via `PendenciaExtra.ch_total_justificada`) pra
    vários professores numa query só, em vez de N + N*3 (cada pendência abria
    3 queries pra somar TCC/extensão/redução aprovados).
    """
    from apps.extra_curricular.models import ParecerChoices, PendenciaExtra
    from apps.extra_curricular.utils import semestre_atual

    pendencias = PendenciaExtra.objects.filter(
        professor_id__in=professor_ids,
        semestre=semestre_atual(),
    ).prefetch_related("orientacoes_tcc", "atividades_extensao", "reducoes_ch")

    mapa = {}
    for p in pendencias:
        if p.status not in PendenciaExtra.STATUS_FINALIZADOS:
            continue
        total = 0.0
        for itens in (p.orientacoes_tcc.all(), p.atividades_extensao.all(), p.reducoes_ch.all()):
            total += sum(
                float(item.ch_aprovada) for item in itens
                if item.parecer_desup == ParecerChoices.APROVADO
            )
        mapa[p.professor_id] = mapa.get(p.professor_id, 0.0) + total
    return mapa


def _perfil_desup(user):
    """Critério único de "enxerga todas as unidades" usado no app inteiro.

    O grupo "Admin DESUP" continua valendo porque o projeto ainda está migrando
    de Groups para `perfil` (ver `PerfilRequiredMixin`), mas o perfil é a fonte
    principal — decidir só pelo grupo deixava o usuário DESUP sem grupo caindo no
    ramo de unidade, com `unidade_principal=None`.
    """
    return (
        user.is_superuser
        or user.perfil == 'DESUP'
        or user.groups.filter(name='Admin DESUP').exists()
    )


# CORR: `PerfilRequiredMixin` apenas delega ao `super().dispatch()` quando o usuário
# não está autenticado (apps/accounts/mixins.py), ou seja, sozinho ele NÃO barra o
# anônimo: a request chegava no corpo da view e estourava 500 em `AnonymousUser.perfil`
# / `.unidade`. Com o `LoginRequiredMixin` na frente, o anônimo é mandado para o login.
class CoordenadorOnlyMixin(LoginRequiredMixin, PerfilRequiredMixin):
    """CRUD de professores: somente coordenador da unidade."""
    allowed_profiles = ['COORDENADOR_UNIDADE']


class ProfessorEditDeleteMixin(LoginRequiredMixin, PerfilRequiredMixin):
    """DESUP gerencia qualquer docente; unidade, somente os vinculados a ela."""

    allowed_profiles = ['DESUP', 'COORDENADOR_UNIDADE']

    def get_queryset(self):
        user = self.request.user
        queryset = Professor.objects.all()
        if _perfil_desup(user):
            return queryset
        if user.unidade_id:
            return queryset.filter(
                Q(unidades__id=user.unidade_id) | Q(unidade_principal_id=user.unidade_id)
            ).distinct()
        return queryset.none()


class ProfessorListView(LoginRequiredMixin, ListView):
    model = Professor
    template_name = 'professors/professor_list.html'
    context_object_name = 'professores'
    # As colunas de carga horária exigem cálculos em lote. Um lote menor reduz
    # DOM, memória e tempo de resposta sem perder a busca sobre a base inteira.
    paginate_by = 20

    def get_queryset(self):
        qs = Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related('cursos', 'unidades')
        user = self.request.user

        q = self.request.GET.get('q', '')
        if q:
            qs = filtrar_contem(
                qs, q, ['rh_nome', 'desup_nome', 'id_funcional', 'rh_matricula'],
            )
        regime = self.request.GET.get('regime')
        if regime:
            qs = qs.filter(tipo_contrato__regime_trabalho__iexact=regime)
        tipo = self.request.GET.get('tipo')
        if tipo and tipo.isdigit():
            qs = qs.filter(tipo_contrato_id=tipo)
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id:
            qs = qs.filter(
                Q(unidades__id=unidade_id) | Q(unidade_principal_id=unidade_id)
            ).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        ctx['is_desup'] = user.is_superuser or user.perfil == 'DESUP'
        ctx['regimes'] = sorted(
            set(ContractType.objects.permitidos().exclude(regime_trabalho='').values_list('regime_trabalho', flat=True))
        )
        ctx['tipos'] = [(str(pk), nome) for pk, nome in ContractType.objects.permitidos().order_by('nome').values_list('pk', 'nome')]
        ctx['total_professores'] = Professor.objects.count()
        ctx['total_filtrados'] = ctx['paginator'].count if ctx.get('paginator') else len(ctx['professores'])
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        ctx['filtros_ativos'] = any(
            self.request.GET.get(k) for k in ('q', 'regime', 'tipo', 'unidade_id')
        )
        ctx['regime_atual'] = self.request.GET.get('regime', '')
        ctx['tipo_atual'] = self.request.GET.get('tipo', '')

        # Coordenador não pode mais CRIAR (CRUD parcial) mas pode visualizar e editar
        ctx['pode_crud'] = (
            user.is_superuser or user.perfil == 'COORDENADOR_UNIDADE' or user.perfil == 'DESUP'
        )
        ctx['pode_criar'] = (user.is_superuser or user.perfil == 'DESUP')
        ctx['pode_solicitar_cadastro'] = (
            user.perfil == 'COORDENADOR_UNIDADE' and not user.is_superuser
        )

        unidade_atual = None
        if user.perfil == 'COORDENADOR_UNIDADE' and user.unidade:
            unidade_atual = user.unidade
            ctx['unidade_atual'] = unidade_atual
        elif user.perfil == 'DESUP' and self.request.GET.get('unidade_id'):
            unidade_atual = Unidade.objects.filter(
                pk=self.request.GET.get('unidade_id')
            ).first()
            ctx['unidade_atual'] = unidade_atual

        # ch_alocada/ch_justificada são @property calculadas por query — chamá-las
        # por professor (inclusive indiretamente, via ch_nao_alocada/percentual_alocado
        # no template) multiplicava por N professores. Calculado em lote uma vez só
        # e exposto como atributo simples (_total) que o template usa no lugar da
        # property crua.
        professores_list = list(ctx['professores'])
        professor_ids = [p.pk for p in professores_list]
        ch_alocada_map = _bulk_ch_alocada(professor_ids)
        ch_justificada_map = _bulk_ch_justificada(professor_ids)
        for prof in professores_list:
            prof.alocacao_map = {}
            ch_alocada_total = ch_alocada_map.get(prof.pk, 0)
            ch_justificada_total = ch_justificada_map.get(prof.pk, 0.0)
            prof.ch_alocada_total = ch_alocada_total
            prof.ch_justificada_total = ch_justificada_total
            prof.soma_horas = ch_alocada_total + ch_justificada_total
            # "Não alocado" é a sobra de horas EM SALA (max_class_hours do
            # contrato — ex.: 20h de um contrato de 40h), não do total do
            # contrato (ch_total/max_total_hours). Usar ch_total aqui inflava
            # o saldo (ex.: professor 40h com 6h em sala aparecia com 34h de
            # sobra em vez de 14h) — mesma meta já usada em
            # extra_curricular/services.py (get_pendencias_data).
            meta_horas = prof.meta_horas_sala
            prof.ch_nao_alocada_total = max(meta_horas - prof.soma_horas, 0)
            prof.percentual_alocado_total = (
                round(min((prof.soma_horas / meta_horas) * 100, 100.0), 2)
                if meta_horas else 0.0
            )
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
                        # soma_horas/ch_*_total já vêm calculados em lote acima;
                        # este bloco só adiciona o detalhamento por matriz (alocacao_map).
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Erro ao montar contexto de professores")

        return ctx
class DesupOnlyMixin(LoginRequiredMixin, PerfilRequiredMixin):
    # Mesmo motivo do `CoordenadorOnlyMixin`: sem o `LoginRequiredMixin` o anônimo
    # entrava na view e quebrava em `AnonymousUser.perfil` (500 em vez de login).
    allowed_profiles = ['DESUP']


class ProfessorDetailView(DesupOnlyMixin, DetailView):
    """Conteúdo do modal de detalhes aberto pelo Administrador DESUP."""

    model = Professor
    template_name = 'professors/partials/_professor_detail.html'
    context_object_name = 'professor'

    def get_queryset(self):
        return Professor.objects.select_related(
            'tipo_contrato', 'unidade_principal'
        ).prefetch_related('cursos', 'unidades')

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
        messages.success(self.request, 'Professor cadastrado com sucesso.')
        return super().form_valid(form)


class ProfessorUpdateView(ProfessorEditDeleteMixin, UpdateView):
    model = Professor
    form_class = ProfessorForm
    template_name = 'professors/professor_form.html'
    success_url = reverse_lazy('professors:professor_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Professor atualizado com sucesso.')
        return super().form_valid(form)


class ProfessorDeleteView(ProfessorEditDeleteMixin, DeleteView):
    model = Professor
    template_name = 'professors/professor_confirm_delete.html'
    success_url = reverse_lazy('professors:professor_list')

    # CORR: `DeleteView.delete()` virou código morto no Django 4.0 (a view passou a usar
    # `FormMixin`, e o POST cai em `form_valid()`) — por isso a mensagem de sucesso nunca
    # chegava na tela. Além disso a exclusão precisa tratar `ProtectedError`: o docente
    # alocado é protegido por `MatrixComponent.docente` (on_delete=PROTECT) e o POST
    # estourava 500 em vez de explicar o motivo para o usuário.
    def form_valid(self, form):
        professor = self.object
        try:
            resposta = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                f'Não é possível excluir {professor.nome}: o docente ainda está alocado '
                'em componentes curriculares. Libere as alocações antes de excluir.',
            )
            return redirect(self.get_success_url())

        messages.success(self.request, 'Professor excluído com sucesso.')
        return resposta


def _identificador_unico_de_copia(campo, valor_base):
    """Monta um identificador de cópia que não colide com os já existentes.

    `id_funcional` e `rh_matricula` são `unique` (models.py), então o prefixo fixo
    "COPIA-" quebrava com IntegrityError/500 na segunda duplicação do MESMO professor.
    A primeira cópia continua sendo "COPIA-<valor>" (formato já conhecido pelos
    usuários) e as seguintes ganham um contador: "COPIA-2-<valor>", "COPIA-3-<valor>"…
    O corte por `max_length` evita estourar o tamanho da coluna.
    """
    max_length = Professor._meta.get_field(campo).max_length
    candidato = f'COPIA-{valor_base}'[:max_length]
    contador = 2
    while Professor.objects.filter(**{campo: candidato}).exists():
        candidato = f'COPIA-{contador}-{valor_base}'[:max_length]
        contador += 1
    return candidato


class ProfessorSolicitarCadastroView(CoordenadorOnlyMixin, View):
    """Coordenador pede à DESUP o cadastro de um professor.

    Gera uma Notificacao para a DESUP; o signal de `Notificacao` envia o mesmo
    aviso por e-mail aos administradores DESUP.
    """

    template_name = 'professors/professor_solicitar_cadastro.html'

    def get(self, request):
        return render(request, self.template_name, {'form': SolicitacaoCadastroProfessorForm()})

    def post(self, request):
        form = SolicitacaoCadastroProfessorForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        dados = form.cleaned_data
        unidade = request.user.unidade
        unidade_label = f'{unidade.sigla} - {unidade.nome}' if unidade else 'Sem unidade vinculada'
        solicitante = request.user.get_full_name() or request.user.email
        tipo = dados['tipo_contrato'].nome if dados['tipo_contrato'] else 'Não informado'
        mensagem = (
            f'O coordenador {solicitante} ({request.user.email}) solicitou o cadastro de um professor.\n\n'
            f'Unidade: {unidade_label}\n'
            f'Nome: {dados["nome"]}\n'
            f'ID Funcional: {dados["id_funcional"] or "Não informado"}\n'
            f'Matrícula RH: {dados["rh_matricula"] or "Não informada"}\n'
            f'Tipo de contrato: {tipo}\n'
            f'Observações: {dados["observacao"] or "Sem observações."}'
        )
        Notificacao.objects.create(
            destinatario=None,
            unidade_destino=None,
            titulo=f'Solicitação de cadastro de professor - {unidade.sigla if unidade else "Geral"}',
            mensagem=mensagem,
            url_acao=reverse('professors:professor_create'),
        )
        messages.success(request, 'Solicitação de cadastro enviada para a DESUP.')
        return redirect('professors:professor_list')


class ProfessorDuplicarView(CoordenadorOnlyMixin, View):
    """Duplica um professor criando uma cópia com o ID funcional alterado."""

    def post(self, request, pk):
        user = request.user
        qs = Professor.objects.all()
        if not user.is_superuser:
            qs = qs.filter(
                Q(unidades=user.unidade) | Q(unidade_principal=user.unidade)
            ).distinct()
        original = get_object_or_404(qs, pk=pk)
        cursos = list(original.cursos.all())
        unidades = list(original.unidades.all())
        novo_id_funcional = _identificador_unico_de_copia('id_funcional', original.id_funcional)
        nova_matricula = (
            _identificador_unico_de_copia('rh_matricula', original.rh_matricula)
            if original.rh_matricula else None
        )

        original.pk = None
        original.id_funcional = novo_id_funcional
        original.rh_matricula = nova_matricula
        original.rh_nome = f"[Cópia] {original.rh_nome}"
        original.save()
        original.cursos.set(cursos)
        original.unidades.set(unidades)

        messages.success(
            request,
            'Professor duplicado com sucesso. Edite a cópia para ajustar os dados.',
        )
        return redirect('professors:professor_update', pk=original.pk)


@login_required
def alloc_curricular_view(request):
    user = request.user
    is_admin = _perfil_desup(user)
    unidades = Unidade.objects.all().order_by('nome') if is_admin else []
    return render(request, 'professors/alloc_curricular.html', {
        'is_admin': is_admin,
        'unidades': unidades,
    })


@login_required
def htmx_tabela_alocacao(request):
    queryset = Professor.objects.select_related('tipo_contrato').prefetch_related('unidades')

    # Mesmo motivo do ProfessorListView: ch_justificada/ch_nao_alocada/
    # percentual_alocado como property por linha vira N+1 (essa tabela carrega
    # sozinha via hx-trigger="load" assim que a página abre).
    professores = list(queryset)
    professor_ids = [p.pk for p in professores]
    ch_alocada_map = _bulk_ch_alocada(professor_ids)
    ch_justificada_map = _bulk_ch_justificada(professor_ids)
    for prof in professores:
        ch_alocada_total = ch_alocada_map.get(prof.pk, 0)
        ch_justificada_total = ch_justificada_map.get(prof.pk, 0.0)
        prof.ch_justificada_total = ch_justificada_total
        soma = ch_alocada_total + ch_justificada_total
        # Mesma correção do ProfessorListView: "não alocado" e "% alocado"
        # são relativos à meta de horas EM SALA (max_class_hours), não ao
        # total do contrato (ch_total/max_total_hours).
        meta_horas = prof.meta_horas_sala
        prof.ch_nao_alocada_total = max(meta_horas - soma, 0)
        prof.percentual_alocado_total = (
            round(min((soma / meta_horas) * 100, 100.0), 2)
            if meta_horas else 0.0
        )

    return render(request, 'professors/partials/_linhas_alocacao.html', {'professores': professores})


class ProfessorCursosPartialView(LoginRequiredMixin, View):
    """HTMX partial para retornar cursos das unidades selecionadas."""

    def get(self, request, *args, **kwargs):
        unidade_ids = [pk for pk in request.GET.getlist('unidades') if str(pk).isdigit()]
        selecionados = set(request.GET.getlist('cursos'))
        if not unidade_ids:
            return render(request, 'professors/partials/_cursos_checkboxes.html', {
                'cursos': [], 'selecionados': selecionados,
            })

        from apps.courses.models import Course
        cursos = Course.objects.filter(
            course_units__unidade_id__in=unidade_ids,
            course_units__ativo=True,
        ).order_by('nome').distinct()
        return render(request, 'professors/partials/_cursos_checkboxes.html', {
            'cursos': cursos,
            'selecionados': selecionados,
        })
