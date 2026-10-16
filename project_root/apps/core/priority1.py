"""Consultas consolidadas da Prioridade 1 para a visão institucional da DESUP."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.courses.models import MatrixComponent
from apps.extra_curricular.models import PendenciaExtra, ParecerChoices
from apps.professors.models import Professor

from .models import (
    ExcecaoCargaUnidade,
    LimiteCargaUnidade,
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
    SolicitacaoProfessorExterno,
    Unidade,
)


def _decimal(value):
    return Decimal(str(value or 0))


def _carga_extracurricular_aprovada(professor_ids, semestre):
    totais = defaultdict(Decimal)
    pendencias = (
        PendenciaExtra.objects.filter(
            professor_id__in=professor_ids,
            semestre=semestre,
            status__in=PendenciaExtra.STATUS_FINALIZADOS,
        )
        .prefetch_related("orientacoes_tcc", "atividades_extensao", "reducoes_ch")
    )
    for pendencia in pendencias:
        for related_name in ("orientacoes_tcc", "atividades_extensao", "reducoes_ch"):
            for item in getattr(pendencia, related_name).all():
                if item.parecer_desup == ParecerChoices.APROVADO:
                    totais[pendencia.professor_id] += _decimal(item.ch_aprovada)
    return totais


def obter_resumo_prioridade1(*, unidade_id=None, semestre=None, curso_id=None, turno=None, status=None):
    """Retorna indicadores consolidados, com filtros aplicados no servidor."""
    hoje = timezone.localdate()
    semestre = semestre or f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"

    componentes = MatrixComponent.objects.filter(matriz__is_vigente=True).select_related(
        "matriz", "matriz__curso", "docente", "docente__tipo_contrato", "componente_curricular"
    ).prefetch_related("matriz__unidades")
    if unidade_id:
        componentes = componentes.filter(matriz__unidades__id=unidade_id)
    if semestre:
        componentes = componentes.filter(
            Q(matriz__periodo_letivo=semestre) | Q(matriz__periodo_letivo__isnull=True) | Q(matriz__periodo_letivo="")
        )
    if str(curso_id or '').isdigit():
        componentes = componentes.filter(matriz__curso_id=curso_id)
    if turno in {'M', 'T', 'N'}:
        componentes = componentes.filter(matriz__turno=turno)
    if status in MatrixComponent.StatusChoices.values:
        componentes = componentes.filter(status=status)
    componentes = list(componentes.distinct())

    cargas_professor = defaultdict(Decimal)
    cargas_unidade = defaultdict(Decimal)
    vistos_professor = set()
    vistos_unidade = set()
    professor_ids = set()
    componentes_sem_professor = 0

    for componente in componentes:
        if not componente.docente_id:
            if componente.status != MatrixComponent.StatusChoices.NAO_OFERECIDA:
                componentes_sem_professor += 1
            continue

        professor_ids.add(componente.docente_id)
        chave_base = (
            f"catalogo:{componente.componente_curricular_id}"
            if componente.compartilhado and componente.componente_curricular_id
            else f"linha:{componente.pk}"
        )
        chave_professor = (componente.docente_id, chave_base)
        if chave_professor not in vistos_professor:
            vistos_professor.add(chave_professor)
            cargas_professor[componente.docente_id] += _decimal(componente.ha_semanal)

        for unidade in componente.matriz.unidades.all():
            if unidade_id and unidade.pk != int(unidade_id):
                continue
            chave_unidade = (unidade.pk, componente.docente_id, chave_base)
            if chave_unidade not in vistos_unidade:
                vistos_unidade.add(chave_unidade)
                cargas_unidade[unidade.pk] += _decimal(componente.ha_semanal)

    professores_escopo = Professor.objects.filter(status=Professor.StatusChoices.ATIVO)
    if unidade_id:
        professores_escopo = professores_escopo.filter(
            Q(unidades__id=unidade_id) | Q(unidade_principal_id=unidade_id)
        ).distinct()
    professores = list(
        professores_escopo.select_related("tipo_contrato").prefetch_related("unidades")
    )
    professores_escopo_ids = {professor.pk for professor in professores}
    extra = _carga_extracurricular_aprovada(professores_escopo_ids, semestre)
    no_limite = 0
    excedidos = 0
    com_sobra = 0
    for professor in professores:
        total = cargas_professor[professor.pk] + extra[professor.pk]
        meta = _decimal(professor.meta_horas_sala)
        if meta and total > meta:
            excedidos += 1
        elif meta and total == meta:
            no_limite += 1
        elif meta and total < meta:
            com_sobra += 1

    filtro_vigente = Q(data_inicio__lte=hoje) & (Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
    ocupacoes = OcupacaoEquipeDiretiva.objects.filter(filtro_vigente)
    readaptacoes = ReadaptacaoProfessor.objects.filter(filtro_vigente)
    if unidade_id:
        ocupacoes = ocupacoes.filter(unidade_id=unidade_id)
        readaptacoes = readaptacoes.filter(
            Q(professor__unidades__id=unidade_id) | Q(professor__unidade_principal_id=unidade_id)
        ).distinct()

    diretivos_em_sala = ocupacoes.filter(professor_id__in=professor_ids).values("professor_id").distinct().count()
    readaptados_em_sala = readaptacoes.filter(professor_id__in=professor_ids).values("professor_id").distinct().count()
    ensino_medio_superior = Professor.objects.filter(
        pk__in=professor_ids,
        nivel_ensino_origem=Professor.NivelEnsinoOrigemChoices.MEDIO,
    ).count()

    limites = LimiteCargaUnidade.objects.filter(filtro_vigente).select_related("unidade")
    if unidade_id:
        limites = limites.filter(unidade_id=unidade_id)
    excecoes = ExcecaoCargaUnidade.objects.filter(
        status=ExcecaoCargaUnidade.StatusChoices.APROVADA,
        data_inicio__lte=hoje,
        data_fim__gte=hoje,
    )
    if unidade_id:
        excecoes = excecoes.filter(unidade_id=unidade_id)
    adicionais = defaultdict(Decimal)
    for unidade, horas in excecoes.values_list("unidade_id", "horas_adicionais"):
        adicionais[unidade] += _decimal(horas)

    unidades_no_limite = []
    for limite in limites:
        carga = cargas_unidade[limite.unidade_id]
        teto = _decimal(limite.limite_horas_semanais) + adicionais[limite.unidade_id]
        if carga >= teto:
            unidades_no_limite.append(
                {
                    "id": limite.unidade_id,
                    "sigla": limite.unidade.sigla,
                    "nome": limite.unidade.nome,
                    "carga": carga,
                    "limite": teto,
                    "excedida": carga > teto,
                }
            )

    solicitacoes_pendentes = SolicitacaoProfessorExterno.objects.filter(
        status=SolicitacaoProfessorExterno.StatusChoices.PENDENTE
    )
    excecoes_pendentes = ExcecaoCargaUnidade.objects.filter(
        status=ExcecaoCargaUnidade.StatusChoices.PENDENTE
    )
    if unidade_id:
        solicitacoes_pendentes = solicitacoes_pendentes.filter(unidade_solicitante_id=unidade_id)
        excecoes_pendentes = excecoes_pendentes.filter(unidade_id=unidade_id)

    unidades_escopo = Unidade.objects.filter(status=True)
    if unidade_id:
        unidades_escopo = unidades_escopo.filter(pk=unidade_id)

    return {
        "semestre": semestre,
        "total_unidades_escopo": unidades_escopo.count(),
        "total_componentes": len(componentes),
        "componentes_sem_professor": componentes_sem_professor,
        "professores_alocados": len(professor_ids),
        "professores_no_limite": no_limite,
        "professores_excedidos": excedidos,
        "professores_com_sobra": com_sobra,
        "diretivos_em_sala": diretivos_em_sala,
        "readaptados_em_sala": readaptados_em_sala,
        "ensino_medio_superior": ensino_medio_superior,
        "solicitacoes_pendentes": solicitacoes_pendentes.count(),
        "excecoes_pendentes": excecoes_pendentes.count(),
        "unidades_no_limite": unidades_no_limite,
        "unidades_no_limite_count": len(unidades_no_limite),
    }
