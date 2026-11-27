from django.db import transaction
from django.db.models import Q


@transaction.atomic
def excluir_professor(professor):
    """Exclui o docente preservando o histórico dos cadastros aprovados.

    A FK continua protegida no modelo para cessões e pedidos não concluídos.
    Se qualquer outro vínculo impedir a exclusão, a desvinculação dos pedidos
    também é revertida. A exclusão do professor mantém a auditoria dos signals.
    """
    from apps.core.models import SolicitacaoProfessorExterno
    from .models import Professor

    professor = Professor.objects.select_for_update().get(pk=professor.pk)
    pedidos = SolicitacaoProfessorExterno.objects.select_for_update().filter(
        professor=professor,
        tipo=SolicitacaoProfessorExterno.TipoChoices.CADASTRO,
        status=SolicitacaoProfessorExterno.StatusChoices.APROVADA,
    ).order_by('pk')
    identificadores = {
        'professor_nome': professor.nome,
        'professor_id_funcional': professor.id_funcional,
        'professor_rh_matricula': professor.rh_matricula or '',
    }
    for pedido in pedidos:
        dados = {'professor_id': None}
        dados.update({
            campo: valor for campo, valor in identificadores.items()
            if not (getattr(pedido, campo) or '').strip()
        })
        # O histórico mantém os dados originais. Não emitir eventos diferidos de
        # edição que poderiam sobreviver em memória ao rollback de uma exclusão.
        SolicitacaoProfessorExterno.objects.filter(pk=pedido.pk).update(**dados)
    return professor.delete()


def motivo_exclusao_bloqueada(erro):
    """Descreve os vínculos que realmente provocaram o ProtectedError."""
    motivos = set()
    for objeto in erro.protected_objects:
        if objeto._meta.label_lower == 'allocations.alocacaoturmadocente':
            motivos.add('alocações em componentes curriculares')
        elif objeto._meta.label_lower == 'core.solicitacaoprofessorexterno':
            motivos.add(
                'solicitações de cessão' if objeto.tipo == 'CESSAO'
                else 'solicitações de cadastro ainda vinculadas'
            )
        else:
            motivos.add(str(objeto._meta.verbose_name_plural).lower())
    return ', '.join(sorted(motivos)) or 'outros registros do sistema'


MENSAGEM_CARGA_RAT_INCOMPLETA = (
    'Este professor não está com a carga horária completa para cumprir '
    'Regime Adicional de Trabalho (RAT).'
)
MENSAGEM_ID_RAT_OBRIGATORIO = 'O professor deve ter um ID funcional cadastrado para solicitar RAT.'


def obter_cargas_rat(professores):
    """Mesmo critério da listagem: meta de sala reduzida e horas do semestre.

    Pedidos de RAT não compõem nenhuma das somas de carga regular.
    """
    professores = list(professores)
    ids = [professor.pk for professor in professores]
    alocadas = _bulk_ch_alocada(ids)
    justificadas = _bulk_ch_justificada(ids)
    resultado = {}
    for professor in professores:
        meta = professor.meta_horas_sala
        preenchida = alocadas.get(professor.pk, 0) + justificadas.get(professor.pk, 0)
        completa = (
            preenchida >= meta if meta > 0
            else bool(professor.reducao_carga_vigente)
        )
        resultado[str(professor.pk)] = {
            'id_funcional': professor.id_funcional,
            'nome': professor.nome,
            'meta': meta,
            'preenchida': preenchida,
            'completa': completa,
        }
    return resultado


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
        "componente_matriz__carga_horaria_semanal",
        "componente_matriz_id",
        "id",
    )

    mapa = {}
    vistos = {}
    for comp in componentes:
        pid = comp["docente_id"]
        vistos.setdefault(pid, set())
        chave = (
            comp["componente_matriz__componente_curricular_id"]
            if comp["componente_matriz__compartilhado"]
            else ("linha", comp["id"])
        )
        if chave in vistos[pid]:
            continue
        vistos[pid].add(chave)
        from apps.courses.models import ch_semanal_componente
        ha_semanal = ch_semanal_componente(
            comp["componente_matriz__carga_horaria"],
            comp["componente_matriz__carga_horaria_semanal"],
        )
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
        status__in=PendenciaExtra.STATUS_FINALIZADOS,
    ).prefetch_related("orientacoes_tcc", "atividades_extensao", "reducoes_ch", "licencas")

    mapa = {}
    for p in pendencias:
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


