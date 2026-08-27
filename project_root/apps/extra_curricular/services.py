"""
Services — lógica de negócio isolada para Alocação Extracurricular.
"""
from decimal import Decimal
from django.db.models import QuerySet

from apps.professors.models import Professor
from apps.extra_curricular.models import PendenciaExtra


# ──────────────────────────────────────────────────────────────
# Cálculos de carga horária
# ──────────────────────────────────────────────────────────────

def calcular_ch_tcc(num_orientandos: int) -> Decimal:
    """
    0,5h por orientando, limitado a 4h (8 orientandos máx.).
    """
    return Decimal(min(num_orientandos * 0.5, 4.0)).quantize(Decimal("0.1"))


def calcular_ch_extensao(num_estudantes: int) -> Decimal:
    """
    0,5h por estudante, sem limite.
    """
    return Decimal(num_estudantes * 0.5).quantize(Decimal("0.1"))


def sincronizar_status_pendencia(pendencia: PendenciaExtra) -> str:
    """
    Atualiza o status agregado da pendência com base nos pareceres dos itens.

    Regras:
      - qualquer item rejeitado => REJEITADO
      - todos os itens aprovados e ao menos um item existente => APROVADO
      - caso contrário, quando a pendência já tiver sido enviada => ENVIADO
      - rascunhos permanecem como RASCUNHO
    """
    from apps.extra_curricular.models import (
        AtividadeExtensionista,
        OrientacaoTCC,
        ParecerChoices,
        ReducaoCargaHoraria,
    )

    itens = []
    itens.extend(list(OrientacaoTCC.objects.filter(pendencia=pendencia).values_list("parecer_desup", flat=True)))
    itens.extend(list(AtividadeExtensionista.objects.filter(pendencia=pendencia).values_list("parecer_desup", flat=True)))
    itens.extend(list(ReducaoCargaHoraria.objects.filter(pendencia=pendencia).values_list("parecer_desup", flat=True)))

    novo_status = pendencia.status
    if not itens:
        novo_status = pendencia.status
    elif all(status == ParecerChoices.APROVADO for status in itens):
        novo_status = PendenciaExtra.StatusChoices.APROVADO
    elif pendencia.status != PendenciaExtra.StatusChoices.RASCUNHO:
        novo_status = PendenciaExtra.StatusChoices.ENVIADO

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
    calculada a partir de agregações relacionadas.
    """
    professores = (
        Professor.objects
        .select_related("tipo_contrato")
        .prefetch_related("componentes_matriz")
    )
    if unidade_id:
        professores = professores.filter(unidade_principal_id=unidade_id)

    if q:
        from django.db.models import Q
        professores = professores.filter(
            Q(rh_nome__icontains=q) | Q(desup_nome__icontains=q)
        )

    pendentes = []
    for prof in professores:
        meta = prof.tipo_contrato.max_class_hours if prof.tipo_contrato else 20
        if prof.ch_alocada < meta:
            pendentes.append(prof.pk)
    return Professor.objects.filter(pk__in=pendentes).select_related("tipo_contrato")


def get_pendencias_data(unidade_id: int, semestre: str, q: str = ""):
    """
    Retorna lista de dicts com dados completos para a listagem:
    professores com pendência + seus registros de PendenciaExtra (se existirem).
    Se um professor tiver múltiplas justificativas, elas retornam como linhas separadas.
    """
    professores_pendentes = get_professores_com_pendencia(unidade_id, semestre, q)

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
        ch_alocada = prof.ch_alocada
        ch_pendente = max(meta - ch_alocada, 0)
        pendencia = pendencias_existentes.get(prof.pk)

        if pendencia:
            ch_justificada = pendencia.ch_total_justificada
            ch_faltante = max(ch_pendente - ch_justificada, 0)

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
                        "ch_justificada": item.ch_aprovada,
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
                        "ch_justificada": item.ch_aprovada,
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
                        "ch_justificada": item.ch_aprovada,
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
    return result
