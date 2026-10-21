"""Consultas consolidadas da Prioridade 1 para a visão institucional da DESUP."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.allocations.models import AlocacaoTurmaDocente
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


# Quantos itens cada janela de detalhe lista (o total continua nos cartões).
LIMITE_DETALHE = 100


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
        .prefetch_related("orientacoes_tcc", "atividades_extensao", "reducoes_ch", "licencas")
    )
    for pendencia in pendencias:
        for related_name in ("orientacoes_tcc", "atividades_extensao", "reducoes_ch", "licencas"):
            for item in getattr(pendencia, related_name).all():
                if item.parecer_desup == ParecerChoices.APROVADO:
                    totais[pendencia.professor_id] += _decimal(item.ch_aprovada)
    return totais


def obter_resumo_prioridade1(*, unidade_id=None, semestre=None, curso_id=None, turno=None, status=None):
    """Retorna indicadores consolidados, com filtros aplicados no servidor."""
    hoje = timezone.localdate()
    semestre = semestre or f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"

    componentes = MatrixComponent.objects.filter(matriz__is_vigente=True).select_related(
        "matriz", "matriz__curso", "componente_curricular"
    ).prefetch_related(
        "matriz__unidades",
        Prefetch(
            "alocacoes_turma_docente",
            queryset=AlocacaoTurmaDocente.objects.filter(
                alocacao_curricular__semestre=semestre
            ).order_by("pk"),
            to_attr="linhas_semestre",
        ),
    )
    if unidade_id:
        componentes = componentes.filter(matriz__unidades__id=unidade_id)
    # O semestre filtra as linhas de alocação (Prefetch acima), não as matrizes: a matriz
    # vigente vale para o semestre corrente mesmo com `periodo_letivo` de cadastro diferente
    # (a tela de Alocação Curricular também não filtra por esse campo).
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
    detalhe_disciplinas = []

    for componente in componentes:
        docentes_ids = [linha.docente_id for linha in componente.linhas_semestre if linha.docente_id]
        if componente.status != MatrixComponent.StatusChoices.NAO_OFERECIDA and (
            not docentes_ids
            or any(not linha.docente_id for linha in componente.linhas_semestre)
        ):
            componentes_sem_professor += 1
            detalhe_disciplinas.append({
                "nome": componente.nome_disciplina,
                "codigo": componente.codigo,
                "curso": componente.matriz.curso.sigla if componente.matriz.curso_id else "",
                "turno": componente.matriz.get_turno_display() if componente.matriz.turno else "",
                "unidades": ", ".join(sorted(u.sigla for u in componente.matriz.unidades.all())),
                "turmas_sem_docente": sum(1 for linha in componente.linhas_semestre if not linha.docente_id) or (componente.quantidade_turmas or 1),
            })

        chave_base = (
            f"catalogo:{componente.componente_curricular_id}"
            if componente.compartilhado and componente.componente_curricular_id
            else f"linha:{componente.pk}"
        )
        for docente_id in docentes_ids:
            professor_ids.add(docente_id)
            chave_professor = (docente_id, chave_base)
            if chave_professor not in vistos_professor:
                vistos_professor.add(chave_professor)
                cargas_professor[docente_id] += _decimal(componente.ha_semanal)

            for unidade in componente.matriz.unidades.all():
                if unidade_id and unidade.pk != int(unidade_id):
                    continue
                chave_unidade = (unidade.pk, docente_id, chave_base)
                if chave_unidade not in vistos_unidade:
                    vistos_unidade.add(chave_unidade)
                    cargas_unidade[unidade.pk] += _decimal(componente.ha_semanal)

    professores_escopo = Professor.objects.filter(status=Professor.StatusChoices.ATIVO)
    if unidade_id:
        professores_escopo = professores_escopo.filter(
            Q(unidades__id=unidade_id) | Q(unidade_principal_id=unidade_id)
        ).distinct()
    professores = list(
        professores_escopo.select_related("tipo_contrato").prefetch_related("unidades", "ocupacoes_diretivas")
    )
    professores_escopo_ids = {professor.pk for professor in professores}
    extra = _carga_extracurricular_aprovada(professores_escopo_ids, semestre)
    no_limite = 0
    excedidos = 0
    com_sobra = 0
    detalhe_professores = {"sobra": [], "limite": [], "acima": []}
    for professor in professores:
        total = cargas_professor[professor.pk] + extra[professor.pk]
        meta = _decimal(professor.meta_horas_sala)
        grupo = None
        if meta and total > meta:
            excedidos += 1
            grupo = "acima"
        elif meta and total == meta:
            no_limite += 1
            grupo = "limite"
        elif meta and total < meta:
            com_sobra += 1
            grupo = "sobra"
        if grupo:
            detalhe_professores[grupo].append({
                "nome": professor.nome,
                "unidades": ", ".join(u.sigla for u in professor.unidades_exibicao),
                "carga": total,
                "meta": meta,
                "diferenca": abs(meta - total),
            })
    # Maiores desvios primeiro; a tela mostra só os primeiros (ver LIMITE_DETALHE).
    detalhe_professores["sobra"].sort(key=lambda i: i["diferenca"], reverse=True)
    detalhe_professores["acima"].sort(key=lambda i: i["diferenca"], reverse=True)
    detalhe_professores["limite"].sort(key=lambda i: i["nome"])
    detalhe_disciplinas.sort(key=lambda i: (i["curso"], i["nome"]))

    filtro_vigente = Q(data_inicio__lte=hoje) & (Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
    ocupacoes = OcupacaoEquipeDiretiva.objects.filter(filtro_vigente)
    readaptacoes = ReadaptacaoProfessor.objects.filter(filtro_vigente)
    if unidade_id:
        ocupacoes = ocupacoes.filter(unidade_id=unidade_id)
        readaptacoes = readaptacoes.filter(
            Q(professor__unidades__id=unidade_id) | Q(professor__unidade_principal_id=unidade_id)
        ).distinct()

    ocupacoes_em_sala = list(
        ocupacoes.filter(professor_id__in=professor_ids).select_related("professor", "cargo", "unidade")
    )
    readaptacoes_em_sala = list(
        readaptacoes.filter(professor_id__in=professor_ids).select_related("professor")
    )
    medio_no_superior = list(
        Professor.objects.filter(
            pk__in=professor_ids,
            nivel_ensino_origem=Professor.NivelEnsinoOrigemChoices.MEDIO,
        ).prefetch_related("unidades")
    )
    diretivos_em_sala = len({o.professor_id for o in ocupacoes_em_sala})
    readaptados_em_sala = len({r.professor_id for r in readaptacoes_em_sala})
    ensino_medio_superior = len(medio_no_superior)

    def _unicos(itens, montar):
        vistos, lista = set(), []
        for item in itens:
            if item.professor_id in vistos:
                continue
            vistos.add(item.professor_id)
            lista.append(montar(item))
        return sorted(lista, key=lambda i: i["nome"])[:LIMITE_DETALHE]

    detalhe_diretivos = _unicos(ocupacoes_em_sala, lambda o: {
        "nome": o.professor.nome,
        "unidades": o.unidade.sigla,
        "detalhe": o.cargo.nome,
    })
    detalhe_readaptados = _unicos(readaptacoes_em_sala, lambda r: {
        "nome": r.professor.nome,
        "unidades": ", ".join(u.sigla for u in r.professor.unidades_exibicao),
        "detalhe": "Readaptação vigente",
    })
    detalhe_medio = sorted(
        (
            {
                "nome": p.nome,
                "unidades": ", ".join(u.sigla for u in p.unidades_exibicao),
                "detalhe": "Origem no Ensino Médio",
            }
            for p in medio_no_superior
        ),
        key=lambda i: i["nome"],
    )[:LIMITE_DETALHE]

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
        "detalhe_disciplinas": detalhe_disciplinas[:LIMITE_DETALHE],
        "detalhe_sobra": detalhe_professores["sobra"][:LIMITE_DETALHE],
        "detalhe_limite": detalhe_professores["limite"][:LIMITE_DETALHE],
        "detalhe_acima": detalhe_professores["acima"][:LIMITE_DETALHE],
        "limite_detalhe": LIMITE_DETALHE,
        "professores_alocados": len(professor_ids),
        "professores_no_limite": no_limite,
        "professores_excedidos": excedidos,
        "professores_com_sobra": com_sobra,
        "diretivos_em_sala": diretivos_em_sala,
        "detalhe_diretivos": detalhe_diretivos,
        "detalhe_readaptados": detalhe_readaptados,
        "detalhe_medio": detalhe_medio,
        "readaptados_em_sala": readaptados_em_sala,
        "ensino_medio_superior": ensino_medio_superior,
        "solicitacoes_pendentes": solicitacoes_pendentes.count(),
        "excecoes_pendentes": excecoes_pendentes.count(),
        "unidades_no_limite": unidades_no_limite,
        "unidades_no_limite_count": len(unidades_no_limite),
        "cargas_por_unidade": dict(cargas_unidade),
        "adicionais_por_unidade": dict(adicionais),
    }
