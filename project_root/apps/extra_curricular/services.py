"""
Services — lógica de negócio isolada para Alocação Extracurricular.
"""
from decimal import Decimal
from django.db.models import QuerySet

from apps.professors.models import Professor
from apps.extra_curricular.models import PendenciaExtra


# ──────────────────────────────────────────────────────────────
# CORR-015 — tokens canônicos de filtro da listagem de pendências
# ──────────────────────────────────────────────────────────────
# Fonte da verdade única, consumida pelas três camadas que antes divergiam:
#   1. filtro server-side em PendenciaListView (?status=...);
#   2. os <option value> dos selects em extra_curricular/pendencia_list.html;
#   3. os atributos data-status / data-justificativa das linhas (filtro em JS).
# Antes, o select mandava "Sem registro" e a view comparava com "sem_registro",
# e o data-justificativa vinha vazio — por isso "Sem registro" não retornava nada.

TOKEN_SEM_REGISTRO = "sem_registro"

_STATUS_TOKENS = {
    "RASCUNHO": "rascunho",
    "ENVIADO": "pendente",
    "PENDENTE": "pendente",
    "APROVADO": "finalizado",
    # CORR-023: parcial é um estado final próprio — misturá-lo com "finalizado"
    # esconderia da DESUP justamente as pendências que tiveram item indeferido.
    "PARCIAL": "parcial",
    "INDEFERIDO": "indeferido",
}

_JUSTIFICATIVA_TOKENS = {
    "tcc": "tcc",
    "ext": "extensao",
    "red": "reducao",
}


def status_token(row: dict) -> str:
    """Token canônico do status de uma linha de `get_pendencias_data`."""
    if not row.get("pendencia"):
        return TOKEN_SEM_REGISTRO
    return _STATUS_TOKENS.get(row.get("status_item") or "", TOKEN_SEM_REGISTRO)


def justificativa_token(row: dict) -> str:
    """Token canônico do tipo de justificativa de uma linha de `get_pendencias_data`."""
    return _JUSTIFICATIVA_TOKENS.get(row.get("item_tipo") or "", TOKEN_SEM_REGISTRO)


# ──────────────────────────────────────────────────────────────
# Cálculos de carga horária
# ──────────────────────────────────────────────────────────────

def calcular_ch_tcc(num_orientandos: int) -> Decimal:
    """
    0,5h por orientando, limitado a 4h (8 orientandos máx.).

    Piso em 0: quantidade negativa não existe como pedido real (vem de um `n`
    manipulado na querystring da API de prévia) e não pode virar CH negativa —
    isso apareceria na tela como prévia e, pior, abateria o total do docente.
    """
    return Decimal(min(max(num_orientandos, 0) * 0.5, 4.0)).quantize(Decimal("0.1"))


def calcular_ch_extensao(num_estudantes: int) -> Decimal:
    """
    0,5h por estudante, sem limite (mas com piso em 0 — ver `calcular_ch_tcc`).
    """
    return Decimal(max(num_estudantes, 0) * 0.5).quantize(Decimal("0.1"))


def sincronizar_status_pendencia(pendencia: PendenciaExtra) -> str:
    """
    Atualiza o status agregado da pendência com base nos pareceres dos itens.

    Regras (CORR-023 — aprovação parcial):
      - rascunho nunca é promovido (nem a APROVADO, nem a INDEFERIDO)
      - sem itens => mantém o status atual
      - ainda há item PENDENTE => ENVIADO (análise em curso)
      - todos os itens aprovados        => APROVADO
      - todos os itens indeferidos      => INDEFERIDO
      - misto (aprovado + indeferido)   => PARCIAL

    Antes, `any(INDEFERIDO)` derrubava a pendência inteira para INDEFERIDO. Como
    `ch_total_justificada` zera fora dos status finalizados, um único item
    indeferido apagava TODA a CH que a DESUP já tinha aprovado nos outros itens.
    O `PARCIAL` separa "a análise terminou com resultado misto" de "nada foi
    deferido": o que foi aprovado conta, o indeferido apenas não entra na soma.
    """
    from apps.extra_curricular.models import (
        AtividadeExtensionista,
        OrientacaoTCC,
        ParecerChoices,
        ReducaoCargaHoraria,
    )

    # Rascunho é estado anterior ao trâmite: a unidade ainda não informou o SEI
    # nem enviou nada à DESUP. Promover daqui (o ramo `all(APROVADO)` vinha antes
    # da proteção de rascunho) furava a regra "SEI obrigatório para enviar" —
    # bastava a DESUP emitir parecer nos itens para a pendência virar APROVADO
    # sem nunca ter sido enviada.
    if pendencia.status == PendenciaExtra.StatusChoices.RASCUNHO:
        return pendencia.status

    itens = []
    itens.extend(list(OrientacaoTCC.objects.filter(pendencia=pendencia).values_list("parecer_desup", flat=True)))
    itens.extend(list(AtividadeExtensionista.objects.filter(pendencia=pendencia).values_list("parecer_desup", flat=True)))
    itens.extend(list(ReducaoCargaHoraria.objects.filter(pendencia=pendencia).values_list("parecer_desup", flat=True)))

    tem_aprovado = any(status == ParecerChoices.APROVADO for status in itens)
    tem_indeferido = any(status == ParecerChoices.INDEFERIDO for status in itens)
    # Qualquer item ainda sem decisão mantém a pendência em análise — nem PARCIAL
    # nem INDEFERIDO, senão a unidade veria "finalizado" antes da hora.
    falta_decidir = any(
        status not in (ParecerChoices.APROVADO, ParecerChoices.INDEFERIDO)
        for status in itens
    )

    if not itens:
        novo_status = pendencia.status
    elif falta_decidir:
        novo_status = PendenciaExtra.StatusChoices.ENVIADO
    elif tem_aprovado and tem_indeferido:
        novo_status = PendenciaExtra.StatusChoices.PARCIAL
    elif tem_aprovado:
        novo_status = PendenciaExtra.StatusChoices.APROVADO
    else:
        novo_status = PendenciaExtra.StatusChoices.INDEFERIDO

    if pendencia.status != novo_status:
        pendencia.status = novo_status
        pendencia.save(update_fields=["status", "data_atualizacao"])

    return pendencia.status


# ──────────────────────────────────────────────────────────────
# Consulta de professores com pendência
# ──────────────────────────────────────────────────────────────

def get_professores_com_pendencia(unidade_id: int, semestre: str, q: str = "") -> QuerySet:
    """
    Retorna os professores da unidade (ou de todas se unidade_id for None) que ainda têm horas pendentes
    (ch_alocada < max_class_hours do contrato).

    A verificação é feita em Python porque ch_alocada é uma @property
    calculada a partir de agregações relacionadas — mas usando `_bulk_ch_alocada`
    (uma query só pra todos os professores) em vez de acessar a property por
    professor, que abria uma query por professor (N+1 — chegava a travar/dar
    timeout no Vercel com o banco remoto).
    """
    professores = Professor.objects.select_related("tipo_contrato")
    if unidade_id:
        professores = professores.filter(unidade_principal_id=unidade_id)

    if q:
        from django.db.models import Q
        professores = professores.filter(
            Q(rh_nome__icontains=q) | Q(desup_nome__icontains=q)
        )

    professores = list(professores)
    ch_map = _bulk_ch_alocada([p.pk for p in professores])

    pendentes = []
    for prof in professores:
        meta = prof.tipo_contrato.max_class_hours if prof.tipo_contrato else 20
        if ch_map.get(prof.pk, 0) < meta:
            pendentes.append(prof.pk)
    return Professor.objects.filter(pk__in=pendentes).select_related("tipo_contrato")


def _bulk_ch_alocada(professor_ids):
    """
    Calcula `Professor.ch_alocada` (CH alocada, componentes compartilhados
    contam uma única vez) pra vários professores numa query só, em vez de N.

    Mesma lógica de dedup da property (`apps/professors/models.py`), só que
    em lote — evita reabrir a query por professor, que é o que causava os
    timeouts nas telas de professores/extracurricular no Vercel.
    """
    from apps.courses.models import MatrixComponent

    # ha_semanal é @property (carga_horaria / 20.0), não dá pra pedir direto no
    # .values() — busca o campo real (carga_horaria) e calcula igual à property.
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


def get_pendencias_data(unidade_id: int, semestre: str, q: str = ""):
    """
    Retorna lista de dicts com dados completos para a listagem:
    professores com pendência + seus registros de PendenciaExtra (se existirem).
    Se um professor tiver múltiplas justificativas, elas retornam como linhas separadas.
    """
    professores_pendentes = list(get_professores_com_pendencia(unidade_id, semestre, q))
    ch_alocada_map = _bulk_ch_alocada([p.pk for p in professores_pendentes])

    # Buscar todas as pendências extras deste semestre
    filters = {"semestre": semestre}
    if unidade_id:
        filters["unidade_id"] = unidade_id

    pendencias_qs = PendenciaExtra.objects.filter(**filters).select_related("professor").prefetch_related(
        "orientacoes_tcc",
        "atividades_extensao",
        "reducoes_ch",
    )

    pendencias_existentes = {
        p.professor_id: p
        for p in pendencias_qs
    }

    result = []
    for prof in professores_pendentes:
        meta = prof.tipo_contrato.max_class_hours if prof.tipo_contrato else 20
        ch_alocada = ch_alocada_map.get(prof.pk, 0)
        ch_pendente = max(meta - ch_alocada, 0)
        pendencia = pendencias_existentes.get(prof.pk)

        if pendencia:
            ch_justificada = pendencia.ch_total_justificada
            ch_faltante = max(ch_pendente - ch_justificada, 0)
            # Só conta como CH Justificada (coluna da lista) quando a pendência está
            # de fato APROVADA. Após uma reabertura (status volta a ENVIADO) a CH
            # aprovada anteriormente deixa de contar até ser aprovada novamente.
            # CORR-023: PARCIAL também é estado finalizado — o item aprovado conta.
            conta_justificada = pendencia.status in PendenciaExtra.STATUS_FINALIZADOS

            # Obter itens de justificativa
            tcc_items = list(pendencia.orientacoes_tcc.all())
            ext_items = list(pendencia.atividades_extensao.all())
            red_items = list(pendencia.reducoes_ch.all())

            # Se existirem itens, criar uma linha para cada um
            if tcc_items or ext_items or red_items:
                for item in tcc_items:
                    result.append({
                        "professor": prof,
                        "meta_horas": meta,
                        "ch_alocada": ch_alocada,
                        "ch_pendente": ch_pendente,
                        "ch_justificada": item.ch_aprovada if conta_justificada else 0,
                        "ch_faltante": ch_faltante,
                        "pendencia": pendencia,
                        "justificativa_detalhe": f"Orientação de TCC ({item.num_orientandos} orientando{'s' if item.num_orientandos > 1 else ''})",
                        "status_item": item.parecer_desup,
                        "justificativa_ch": item.ch_aprovada,
                        "justificativa_tipo": "TCC",
                        "sei_numero": pendencia.sei_numero,
                        "item_tipo": "tcc",
                        "item_pk": item.pk,
                        "item_horas_aprovadas": item.horas_aprovadas,
                    })
                for item in ext_items:
                    result.append({
                        "professor": prof,
                        "meta_horas": meta,
                        "ch_alocada": ch_alocada,
                        "ch_pendente": ch_pendente,
                        "ch_justificada": item.ch_aprovada if conta_justificada else 0,
                        "ch_faltante": ch_faltante,
                        "pendencia": pendencia,
                        "justificativa_detalhe": f"Atividade Extensionista ({item.num_estudantes} estudante{'s' if item.num_estudantes > 1 else ''})",
                        "status_item": item.parecer_desup,
                        "justificativa_ch": item.ch_aprovada,
                        "justificativa_tipo": "Extensão",
                        "sei_numero": pendencia.sei_numero,
                        "item_tipo": "ext",
                        "item_pk": item.pk,
                        "item_horas_aprovadas": item.horas_aprovadas,
                    })
                for item in red_items:
                    result.append({
                        "professor": prof,
                        "meta_horas": meta,
                        "ch_alocada": ch_alocada,
                        "ch_pendente": ch_pendente,
                        "ch_justificada": item.ch_aprovada if conta_justificada else 0,
                        "ch_faltante": ch_faltante,
                        "pendencia": pendencia,
                        "justificativa_detalhe": f"Redução de CH ({item.horas_reduzidas}h) - Motivo: {item.motivo_reducao}",
                        "status_item": item.parecer_desup,
                        "justificativa_ch": item.ch_aprovada,
                        "justificativa_tipo": "Redução",
                        "sei_numero": pendencia.sei_numero,
                        "item_tipo": "red",
                        "item_pk": item.pk,
                        "item_horas_aprovadas": item.horas_aprovadas,
                    })
            else:
                # Pendência existe mas não tem nenhum item cadastrado
                result.append({
                    "professor": prof,
                    "meta_horas": meta,
                    "ch_alocada": ch_alocada,
                    "ch_pendente": ch_pendente,
                    "ch_justificada": 0,
                    "ch_faltante": ch_faltante,
                    "pendencia": pendencia,
                    "justificativa_detalhe": None,
                    "status_item": pendencia.status,
                    "justificativa_ch": 0,
                    "justificativa_tipo": "",
                    "sei_numero": pendencia.sei_numero,
                })
        else:
            # Sem registro de pendência
            result.append({
                "professor": prof,
                "meta_horas": meta,
                "ch_alocada": ch_alocada,
                "ch_pendente": ch_pendente,
                "ch_justificada": 0,
                "ch_faltante": ch_pendente,
                "pendencia": None,
                "justificativa_detalhe": None,
                "status_item": "",
                "justificativa_ch": 0,
                "justificativa_tipo": "",
                "sei_numero": "",
            })

    # CORR-015 — anexa os tokens canônicos de filtro em cada linha.
    for row in result:
        row["status_token"] = status_token(row)
        row["justificativa_token"] = justificativa_token(row)

    return result
