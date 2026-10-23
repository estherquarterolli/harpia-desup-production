from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import (
    Case, Exists, IntegerField, OuterRef, ProtectedError, Q, Value, When,
)
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from apps.accounts.mixins import PerfilRequiredMixin
from apps.core.busca import filtrar_contem
from apps.allocations.services import semestre_atual
from apps.core.models import Notificacao, SolicitacaoProfessorExterno, Unidade
from .forms import ProfessorForm, SolicitacaoCadastroProfessorForm, SolicitacaoCessaoProfessorForm
from .models import ContractType, Professor, filtro_vinculo_empregaticio


ALLOCATION_TABLE_PAGE_SIZE = 20


def _bulk_ch_alocada(professor_ids):
    """
    `Professor.ch_alocada` pra vários professores numa query só, em vez de N.

    ch_alocada é @property (soma de MatrixComponent com dedup por
    "compartilhado"); chamá-la por professor num loop de listagem abre uma
    query por professor — com ~190 professores isso sozinho já estourava os
    30s de timeout do Vercel. Mesma lógica de dedup, calculada em lote.
    """
    from apps.allocations.services import alocacoes_vigentes

    componentes = alocacoes_vigentes().filter(
        docente_id__in=professor_ids,
    ).values(
        "docente_id",
        "componente_matriz__componente_curricular_id",
        "componente_matriz__compartilhado",
        "componente_matriz__carga_horaria",
        "componente_matriz_id",
    )

    mapa = {}
    vistos = {}
    for comp in componentes:
        pid = comp["docente_id"]
        vistos.setdefault(pid, set())
        chave = (
            comp["componente_matriz__componente_curricular_id"]
            if comp["componente_matriz__compartilhado"]
            else comp["componente_matriz_id"]
        )
        if chave in vistos[pid]:
            continue
        vistos[pid].add(chave)
        ha_semanal = (comp["componente_matriz__carga_horaria"] or 0) / 20.0
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
    ).prefetch_related("orientacoes_tcc", "atividades_extensao", "reducoes_ch", "licencas")

    mapa = {}
    for p in pendencias:
        if p.status not in PendenciaExtra.STATUS_FINALIZADOS:
            continue
        total = 0.0
        for itens in (p.orientacoes_tcc.all(), p.atividades_extensao.all(), p.reducoes_ch.all(), p.licencas.all()):
            total += sum(
                float(item.ch_aprovada) for item in itens
                if item.parecer_desup == ParecerChoices.APROVADO
            )
        mapa[p.professor_id] = mapa.get(p.professor_id, 0.0) + total

    # Orientação/supervisão/coordenação de estágio vigentes no semestre também
    # entram no somatório (em qualquer unidade onde o professor atue).
    from apps.core.models import AtividadeEstagioSupervisao
    from django.utils import timezone

    hoje = timezone.localdate()
    estagios = AtividadeEstagioSupervisao.objects.filter(
        professor_id__in=professor_ids,
        semestre=semestre_atual(),
        data_inicio__lte=hoje,
    ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
    for est in estagios:
        mapa[est.professor_id] = mapa.get(est.professor_id, 0.0) + float(est.carga_horaria_semanal)
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


def enriquecer_professores_com_carga(professores, unidade_atual=None):
    """Anexa a cada professor as cargas (alocada, justificada, total, sobra, %) em lote.

    Quando `unidade_atual` é informada, também devolve as colunas por matriz
    vigente da unidade e o `alocacao_map` de cada professor. Usado pela lista de
    professores e pela visão geral do dashboard da unidade (mesmas colunas).
    """
    resultado = {'colunas_cursos': []}
    professores_list = list(professores)
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
        # Redução da equipe diretiva (definida pela DESUP) conta como alocação:
        # sem isso, um diretivo cuja redução zera a meta aparecia "Sem alocação".
        prof.reducao_diretiva = prof.reducao_carga_vigente
        if meta_horas:
            prof.percentual_alocado_total = round(min((prof.soma_horas / meta_horas) * 100, 100.0), 2)
        else:
            prof.percentual_alocado_total = 100.0 if prof.reducao_diretiva else 0.0

    if unidade_atual:
        try:
            from django.db import transaction as db_transaction
            from apps.allocations.services import alocacoes_vigentes
            from apps.courses.models import CurriculumMatrix
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
                resultado['colunas_cursos'] = colunas_cursos

                componentes = alocacoes_vigentes().filter(
                    componente_matriz__matriz__in=matrizes_vigentes,
                    docente__in=professores_list,
                ).select_related(
                    'componente_matriz', 'componente_matriz__componente_curricular',
                    'componente_matriz__matriz',
                )

                alocacao_map_por_prof = {}
                vistos_por_prof = {}
                for linha in componentes:
                    comp = linha.componente_matriz
                    prof_id = linha.docente_id
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
    resultado['professores'] = professores_list
    return resultado


def detalhar_alocacoes_professores(professores, user=None):
    """Anexa `detalhe_alocacao` (linhas de sala + atividades extras) a cada professor.

    Cada linha: unidade, atividade, turma, horas por turno (M/T/N), CH e situação.
    Tudo em lote (sem query por professor). As linhas de sala seguem a mesma
    deduplicação de `_bulk_ch_alocada` para que a soma bata com os totais.
    """
    from apps.allocations.services import alocacoes_vigentes
    from apps.extra_curricular.models import ParecerChoices, PendenciaExtra

    ids = [p.pk for p in professores]
    for prof in professores:
        prof.detalhe_alocacao = []
    por_id = {p.pk: p for p in professores}
    if not ids:
        return professores

    vistos = {}
    linhas = alocacoes_vigentes().filter(docente_id__in=ids).select_related(
        'alocacao_curricular__unidade',
        'componente_matriz__componente_curricular',
        'turma',
    ).order_by('alocacao_curricular__unidade__sigla', 'componente_matriz__periodo')
    for linha in linhas:
        comp = linha.componente_matriz
        chave = comp.componente_curricular_id if comp.compartilhado else comp.pk
        vistos.setdefault(linha.docente_id, set())
        if chave in vistos[linha.docente_id]:
            continue
        vistos[linha.docente_id].add(chave)
        turno = linha.alocacao_curricular.turno
        horas = round(comp.ha_semanal, 1)
        por_id[linha.docente_id].detalhe_alocacao.append({
            'unidade': linha.alocacao_curricular.unidade.sigla,
            'atividade': comp.nome_disciplina or '—',
            'turma': linha.turma.identificador if linha.turma_id else '—',
            'manha': horas if turno == 'M' else None,
            'tarde': horas if turno == 'T' else None,
            'noite': horas if turno == 'N' else None,
            'ch': horas,
            'situacao': 'Alocado',
            'tom': 'verde',
            'grupo': 'curricular',
        })

    # Equipe diretiva: ocupações vigentes (a redução já compõe a CH total).
    from apps.core.models import OcupacaoEquipeDiretiva
    for ocup in OcupacaoEquipeDiretiva.objects.filter(
        professor_id__in=ids,
    ).select_related('unidade', 'cargo', 'curso'):
        if not ocup.vigente:
            continue
        rotulo = ocup.cargo.nome
        if ocup.curso_id:
            rotulo = f'{rotulo} — {ocup.curso}'
        por_id[ocup.professor_id].detalhe_alocacao.append({
            'unidade': ocup.unidade.sigla,
            'atividade': rotulo,
            'turma': '—',
            'manha': None, 'tarde': None, 'noite': None,
            'ch': round(float(ocup.carga_reducao_horas or 0), 1),
            'situacao': 'Vigente',
            'tom': 'verde',
            'grupo': 'diretiva',
        })

    # Atividades extracurriculares do semestre (justificativas e estágio).
    # Rascunho é estado anterior ao trâmite: a unidade ainda não enviou nada à
    # DESUP (nem informou o SEI). Ele continua acessível na aba "Rascunhos" do
    # módulo extracurricular, mas não entra no detalhamento do dashboard - mesma
    # regra das abas de justificativas enviadas e da listagem da DESUP.
    semestre = semestre_atual()
    pendencias = PendenciaExtra.objects.filter(
        professor_id__in=ids, semestre=semestre,
    ).exclude(
        status=PendenciaExtra.StatusChoices.RASCUNHO,
    ).select_related('unidade').prefetch_related(
        'orientacoes_tcc', 'atividades_extensao', 'reducoes_ch', 'licencas',
    )
    tom_parecer = {
        ParecerChoices.APROVADO: 'verde',
        ParecerChoices.INDEFERIDO: 'vermelho',
    }
    for pend in pendencias:
        itens = (
            [(f'Orientação de TCC ({i.num_orientandos} orientando{"s" if i.num_orientandos != 1 else ""})', i)
             for i in pend.orientacoes_tcc.all()]
            + [(f'Atividade extensionista ({i.num_estudantes} estudante{"s" if i.num_estudantes != 1 else ""})', i)
               for i in pend.atividades_extensao.all()]
            + [('Redução de CH', i) for i in pend.reducoes_ch.all()]
            + [('Licença', i) for i in pend.licencas.all()]
        )
        for rotulo, item in itens:
            por_id[pend.professor_id].detalhe_alocacao.append({
                'unidade': pend.unidade.sigla,
                'atividade': rotulo,
                'turma': 'Diversas',
                'manha': None, 'tarde': None, 'noite': None,
                'ch': round(float(item.ch_aprovada), 1),
                'situacao': item.get_parecer_desup_display(),
                'tom': tom_parecer.get(item.parecer_desup, 'ambar'),
                'grupo': 'extracurricular',
            })

    from apps.core.models import AtividadeEstagioSupervisao
    estagios = AtividadeEstagioSupervisao.objects.filter(
        professor_id__in=ids, semestre=semestre,
    ).select_related('unidade')
    if user is not None:
        estagios = AtividadeEstagioSupervisao.objects.for_user(user).filter(
            professor_id__in=ids, semestre=semestre,
        ).select_related('unidade')
    for est in estagios:
        por_id[est.professor_id].detalhe_alocacao.append({
            'unidade': est.unidade.sigla,
            'atividade': est.get_tipo_display(),
            'turma': 'Diversas',
            'manha': None, 'tarde': None, 'noite': None,
            'ch': round(float(est.carga_horaria_semanal), 1),
            'situacao': 'Vigente' if est.vigente else 'Encerrada',
            'tom': 'verde' if est.vigente else 'cinza',
            'grupo': 'extracurricular',
        })

    for prof in professores:
        prof.detalhe_curricular = [l for l in prof.detalhe_alocacao if l['grupo'] == 'curricular']
        prof.detalhe_extracurricular = [l for l in prof.detalhe_alocacao if l['grupo'] == 'extracurricular']
        prof.detalhe_diretiva = [l for l in prof.detalhe_alocacao if l['grupo'] == 'diretiva']
    return professores


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
        ).prefetch_related('cursos', 'unidades', 'ocupacoes_diretivas', 'readaptacoes')
        user = self.request.user

        q = self.request.GET.get('q', '')
        if q:
            qs = filtrar_contem(
                qs, q, ['rh_nome', 'desup_nome', 'id_funcional', 'rh_matricula', 'area_atuacao'],
            )
        carga = self.request.GET.get('ch', '')
        if carga.isdigit():
            carga = int(carga)
            qs = qs.filter(
                Q(
                    carga_diferenciada=True,
                    carga_horaria_personalizada=carga,
                )
                | Q(
                    carga_diferenciada=False,
                    tipo_contrato__max_total_hours=carga,
                )
            )
        elif self.request.GET.get('regime'):
            # Compatibilidade com links/favoritos criados antes da troca de
            # "Regime" por "Carga horária (CH)" na consulta.
            qs = qs.filter(
                tipo_contrato__regime_trabalho__iexact=self.request.GET['regime']
            )
        cargo = self.request.GET.get('cargo') or self.request.GET.get('tipo')
        if cargo and cargo.isdigit():
            qs = qs.filter(tipo_contrato_id=cargo)
        vinculo = self.request.GET.get('vinculo', '')
        if (user.perfil == 'DESUP' or user.is_superuser) and vinculo in dict(Professor.VinculoEmpregaticioChoices.choices):
            qs = qs.filter(filtro_vinculo_empregaticio(vinculo))
        unidade_id = self.request.GET.get('unidade_id')
        if unidade_id:
            qs = qs.filter(
                Q(unidades__id=unidade_id) | Q(unidade_principal_id=unidade_id)
            ).distinct()

        # A base de professores continua compartilhada entre as unidades, mas,
        # na visao de uma unidade, os docentes vinculados a ela precisam aparecer
        # primeiro. O Exists evita duplicar professores que possuem mais de um
        # vinculo no ManyToMany e garante que a prioridade seja aplicada antes
        # da paginacao.
        # Visibilidade por unidade (Prioridade 1.2): o coordenador vê por padrão apenas os
        # professores vinculados à própria unidade; a DESUP mantém a visão global. Professores
        # de outras unidades entram na alocação via busca/solicitação, não por esta listagem.
        if user.perfil == 'COORDENADOR_UNIDADE' and not user.is_superuser:
            if not user.unidade_id:
                return qs.none()
            qs = qs.filter(
                Q(unidade_principal_id=user.unidade_id) | Q(unidades__id=user.unidade_id)
            ).distinct().order_by('rh_nome', 'pk')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['unidades'] = Unidade.objects.filter(status=True).order_by('nome')
        ctx['is_desup'] = user.is_superuser or user.perfil == 'DESUP'
        cargas_contratos = ContractType.objects.permitidos().values_list(
            'max_total_hours', flat=True,
        )
        cargas_personalizadas = Professor.objects.filter(
            carga_diferenciada=True,
            carga_horaria_personalizada__isnull=False,
        ).values_list('carga_horaria_personalizada', flat=True)
        ctx['cargas_horarias'] = sorted(set(cargas_contratos) | set(cargas_personalizadas))
        cargos = [
            (str(pk), nome)
            for pk, nome in ContractType.objects.permitidos().order_by('nome').values_list('pk', 'nome')
        ]
        ctx['cargos'] = cargos
        ctx['vinculos_empregaticios'] = Professor.VinculoEmpregaticioChoices.choices
        ctx['vinculo_atual'] = self.request.GET.get('vinculo', '')
        ctx['tipos'] = cargos  # compatibilidade com integrações e testes existentes
        ctx['total_filtrados'] = ctx['paginator'].count if ctx.get('paginator') else len(ctx['professores'])
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        ctx['filtros_ativos'] = any(
            self.request.GET.get(k)
            for k in ('q', 'ch', 'cargo', 'regime', 'tipo', 'unidade_id', 'vinculo')
        )
        visao_unidade = user.perfil == 'COORDENADOR_UNIDADE' and not user.is_superuser
        if visao_unidade:
            ctx['kpis'] = []
        else:
            from django.db.models import Count, Q

            ctx['total_professores'] = Professor.objects.count()
            totais = Professor.objects.aggregate(
                ativos=Count('pk', filter=Q(status=Professor.StatusChoices.ATIVO)),
                afastados=Count('pk', filter=Q(status=Professor.StatusChoices.AFASTADO)),
            )
            ctx['kpis'] = [
                {'rotulo': 'No sistema', 'valor': ctx['total_professores'], 'tom': 'azul', 'icone': 'ph-chalkboard-teacher'},
                {'rotulo': 'Ativos', 'valor': totais['ativos'], 'tom': 'verde', 'icone': 'ph-check-circle'},
                {'rotulo': 'Afastados', 'valor': totais['afastados'], 'tom': 'ambar', 'icone': 'ph-warning-circle'},
            ]
            if ctx['filtros_ativos']:
                ctx['kpis'].append(
                    {'rotulo': 'Encontrados', 'valor': ctx['total_filtrados'], 'tom': 'cinza', 'icone': 'ph-funnel'}
                )
        ctx['ch_atual'] = self.request.GET.get('ch', '')
        ctx['cargo_atual'] = self.request.GET.get('cargo') or self.request.GET.get('tipo', '')

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
        dados = enriquecer_professores_com_carga(ctx['professores'], unidade_atual)
        ctx['professores'] = dados['professores']
        if unidade_atual:
            ctx['colunas_cursos'] = dados['colunas_cursos']

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
        ).prefetch_related('cursos', 'unidades', 'ocupacoes_diretivas')

class ProfessorCreateView(DesupOnlyMixin, CreateView):
    model = Professor
    form_class = ProfessorForm
    template_name = 'professors/professor_form.html'
    success_url = reverse_lazy('professors:professor_list')

    def _solicitacao_origem(self):
        if not hasattr(self, '_solicitacao_origem_cache'):
            solicitacao_id = self.request.GET.get('solicitacao', '')
            self._solicitacao_origem_cache = None
            if solicitacao_id.isdigit():
                self._solicitacao_origem_cache = (
                    SolicitacaoProfessorExterno.objects.filter(
                        pk=solicitacao_id,
                        tipo=SolicitacaoProfessorExterno.TipoChoices.CADASTRO,
                        status=SolicitacaoProfessorExterno.StatusChoices.PENDENTE,
                    )
                    .select_related('unidade_solicitante', 'tipo_contrato_solicitado')
                    .first()
                )
        return self._solicitacao_origem_cache

    def get_initial(self):
        initial = super().get_initial()
        solicitacao = self._solicitacao_origem()
        if solicitacao:
            initial.update({
                'rh_nome': solicitacao.professor_nome,
                'id_funcional': solicitacao.professor_id_funcional,
                'rh_matricula': solicitacao.professor_rh_matricula,
                'tipo_contrato': solicitacao.tipo_contrato_solicitado_id,
                'unidades': [solicitacao.unidade_solicitante_id],
            })
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['solicitacao_origem'] = self._solicitacao_origem()
        return ctx

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
    # alocado é protegido por `AlocacaoTurmaDocente.docente` (on_delete=PROTECT) e o POST
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
    contexto = {
        'titulo': 'Solicitar Cadastro de Professor',
        'subtitulo': 'Solicitar cadastro à DESUP',
        'breadcrumb': 'Solicitar cadastro',
    }

    def get(self, request):
        return render(request, self.template_name, {'form': SolicitacaoCadastroProfessorForm(), **self.contexto})

    def post(self, request):
        form = SolicitacaoCadastroProfessorForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, **self.contexto})

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
        if unidade:
            SolicitacaoProfessorExterno.objects.create(
                tipo=SolicitacaoProfessorExterno.TipoChoices.CADASTRO,
                unidade_solicitante=unidade,
                professor_nome=dados['nome'],
                professor_id_funcional=dados['id_funcional'],
                professor_rh_matricula=dados['rh_matricula'],
                tipo_contrato_solicitado=dados['tipo_contrato'],
                observacao_cadastro=dados['observacao'],
                semestre=semestre_atual(),
                justificativa=mensagem,
                solicitado_por=request.user,
            )
        Notificacao.objects.create(
            destinatario=None,
            unidade_destino=None,
            titulo=f'Solicitação de cadastro de professor - {unidade.sigla if unidade else "Geral"}',
            mensagem=mensagem,
            url_acao=reverse('core:solicitacao_professor_list'),
        )
        messages.success(request, 'Solicitação de cadastro enviada para a DESUP.')
        return redirect('professors:professor_list')


class ProfessorSolicitarCessaoView(CoordenadorOnlyMixin, View):
    """Coordenador pede à DESUP um professor de outra unidade (cessão)."""

    template_name = 'professors/professor_solicitar_cadastro.html'
    contexto = {
        'titulo': 'Solicitar Professor de Outra Unidade',
        'subtitulo': 'Solicitar cessão à DESUP',
        'breadcrumb': 'Solicitar professor',
    }

    def _render(self, request, form):
        return render(request, self.template_name, {'form': form, **self.contexto})

    def get(self, request):
        return self._render(request, SolicitacaoCessaoProfessorForm(unidade=request.user.unidade))

    def post(self, request):
        unidade = request.user.unidade
        form = SolicitacaoCessaoProfessorForm(request.POST, unidade=unidade)
        if not unidade:
            messages.error(request, 'Seu usuário não está vinculado a uma unidade.')
            return self._render(request, form)
        if not form.is_valid():
            return self._render(request, form)

        professor = form.cleaned_data['professor']
        origem = professor.unidade_principal or professor.unidades.exclude(pk=unidade.pk).first()
        if origem is None:
            form.add_error('professor', 'O professor não tem unidade de origem cadastrada.')
            return self._render(request, form)
        semestre = semestre_atual()
        if SolicitacaoProfessorExterno.objects.filter(
            unidade_solicitante=unidade, professor=professor, semestre=semestre,
            status=SolicitacaoProfessorExterno.StatusChoices.PENDENTE,
        ).exists():
            form.add_error('professor', 'Já existe uma solicitação pendente para este professor.')
            return self._render(request, form)

        SolicitacaoProfessorExterno.objects.create(
            tipo=SolicitacaoProfessorExterno.TipoChoices.CESSAO,
            unidade_solicitante=unidade,
            unidade_origem=origem,
            professor=professor,
            semestre=semestre,
            justificativa=form.cleaned_data['justificativa'],
            solicitado_por=request.user,
        )
        Notificacao.objects.create(
            destinatario=None,
            unidade_destino=None,
            titulo=f'Solicitação de professor - {unidade.sigla}',
            mensagem=(
                f'{unidade.sigla} solicitou o professor {professor.nome} (origem: {origem.sigla}).\n\n'
                f'Justificativa: {form.cleaned_data["justificativa"]}\n\n'
                'Abra o cadastro do professor para ajustar as unidades em que ele atua.'
            ),
            url_acao=reverse('professors:professor_update', args=[professor.pk]),
        )
        messages.success(request, 'Solicitação enviada para a DESUP.')
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
    from django.core.paginator import Paginator

    user = request.user
    if not _perfil_desup(user):
        if user.unidade_id:
            from apps.allocations.services import professores_autorizados_unidade_qs
            queryset = professores_autorizados_unidade_qs(user.unidade_id).select_related('tipo_contrato').prefetch_related(
                'unidades', 'ocupacoes_diretivas'
            ).order_by('rh_nome')
        else:
            queryset = Professor.objects.none()
    else:
        queryset = Professor.objects.select_related('tipo_contrato').prefetch_related(
            'unidades', 'ocupacoes_diretivas'
        ).order_by('rh_nome')

    # Esta tela legada era o Ãºltimo ponto que ainda materializava todos os
    # professores antes de calcular suas cargas. Paginar antes dos cÃ¡lculos
    # mantÃ©m o custo constante mesmo quando a base cresce.
    page_obj = Paginator(queryset, ALLOCATION_TABLE_PAGE_SIZE).get_page(
        request.GET.get('page')
    )

    # Mesmo motivo do ProfessorListView: ch_justificada/ch_nao_alocada/
    # percentual_alocado como property por linha vira N+1 (essa tabela carrega
    # sozinha via hx-trigger="load" assim que a página abre).
    professores = list(page_obj.object_list)
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
        if meta_horas:
            prof.percentual_alocado_total = round(min((soma / meta_horas) * 100, 100.0), 2)
        else:
            prof.percentual_alocado_total = 100.0 if prof.reducao_carga_vigente else 0.0

    return render(request, 'professors/partials/_linhas_alocacao.html', {
        'professores': professores,
        'page_obj': page_obj,
        'unidade_id': request.GET.get('unidade', ''),
    })


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
