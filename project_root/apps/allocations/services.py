"""Regras de alocação de docentes por turma (Prioridade 2).

Substitui o antigo campo `MatrixComponent.docente`: cada componente passa a ter
uma ou mais linhas `AlocacaoTurmaDocente` (docente ou carência) e uma
`quantidade_turmas` ofertadas.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import AlocacaoCurricular, AlocacaoTurmaDocente, Carencia

SEM_PROFESSOR = 'SEM_PROFESSOR'
NAO_OFERECIDA = 'NAO_OFERECIDA'
NOVA_LINHA = 'novo'
TURNO_PADRAO_ALOCACAO = 'M'
MAX_TURMAS = 20


class AlocacaoError(Exception):
    """Erro de regra de negócio, com o status HTTP a devolver."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def semestre_atual():
    hoje = timezone.localdate()
    return f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"


def alocacoes_vigentes(semestre=None):
    """Linhas com docente definido, do semestre, em matrizes vigentes."""
    return AlocacaoTurmaDocente.objects.filter(
        alocacao_curricular__semestre=semestre or semestre_atual(),
        componente_matriz__matriz__is_vigente=True,
        docente__isnull=False,
    )


def carga_da_linha(componente):
    """HA semanal do componente, gravada em `carga_horaria_contabilizada`."""
    return (Decimal(componente.carga_horaria or 0) / Decimal(20)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def buscar_alocacao_curricular(componente, unidade):
    """Consolidado (curso/unidade/semestre/turno) do componente, se existir."""
    course_unit = _course_unit(componente, unidade)
    if course_unit is None:
        return None
    return AlocacaoCurricular.objects.filter(
        unidade=unidade,
        curso=course_unit,
        semestre=semestre_atual(),
        turno=componente.matriz.turno or TURNO_PADRAO_ALOCACAO,
    ).first()


def obter_alocacao_curricular(componente, unidade):
    """Como `buscar_alocacao_curricular`, mas cria o rascunho quando falta."""
    course_unit = _course_unit(componente, unidade)
    if course_unit is None:
        raise AlocacaoError(
            'O curso desta matriz não está vinculado à unidade. '
            'Cadastre o vínculo em "Cursos na Unidade" antes de alocar.',
            status=400,
        )
    alocacao, _ = AlocacaoCurricular.objects.get_or_create(
        unidade=unidade,
        curso=course_unit,
        semestre=semestre_atual(),
        turno=componente.matriz.turno or TURNO_PADRAO_ALOCACAO,
    )
    return alocacao


def _course_unit(componente, unidade):
    from apps.courses.models import CourseUnit

    if unidade is None or not componente.matriz.curso_id:
        return None
    return CourseUnit.objects.filter(curso_id=componente.matriz.curso_id, unidade=unidade).first()


def _linhas(componente, alocacao):
    return AlocacaoTurmaDocente.objects.filter(
        componente_matriz=componente, alocacao_curricular=alocacao
    ).order_by('pk')


def componente_pendente(componente, linhas):
    """Pendente = oferecido e sem docente definido, ou com carência declarada.

    A quantidade de turmas não exige um docente por turma: o mesmo docente pode dar
    todas as turmas. Faltar professor em uma turma específica é declarado com uma
    linha "Sem professor" (botão "+").
    """
    from apps.courses.models import MatrixComponent

    if componente.status == MatrixComponent.StatusChoices.NAO_OFERECIDA:
        return False
    preenchidas = sum(1 for linha in linhas if linha.docente_id)
    tem_carencia = any(not linha.docente_id for linha in linhas)
    return tem_carencia or preenchidas == 0


def recalcular_status(componente, alocacao):
    """Mantém `MatrixComponent.status` coerente com as linhas da alocação."""
    from apps.courses.models import MatrixComponent

    Status = MatrixComponent.StatusChoices
    linhas = list(_linhas(componente, alocacao))
    if not linhas:
        novo = componente.status if componente.status == Status.NAO_OFERECIDA else Status.SEM_PROFESSOR
    elif all(linha.docente_id for linha in linhas):
        novo = Status.COMPLETO
    else:
        novo = Status.SEM_PROFESSOR
    if novo != componente.status:
        componente.status = novo
        componente.save(update_fields=['status'])
    return novo


def _sincronizar_carencia(linha):
    """Linha sem docente tem carência; ao ganhar docente a carência é resolvida."""
    if linha.docente_id is None:
        carencia, criada = Carencia.objects.get_or_create(alocacao_turma_docente=linha)
        if not criada and carencia.status == Carencia.StatusChoices.RESOLVIDA:
            carencia.status = Carencia.StatusChoices.DECLARADA
            carencia.save(update_fields=['status', 'atualizado_em'])
    else:
        Carencia.objects.filter(alocacao_turma_docente=linha).exclude(
            status=Carencia.StatusChoices.RESOLVIDA
        ).update(status=Carencia.StatusChoices.RESOLVIDA, atualizado_em=timezone.now())


@transaction.atomic
def definir_escolha(componente, unidade, valor, linha_id=None):
    """Aplica a escolha do usuário (docente, "Sem professor" ou "Não oferecido").

    `linha_id`: pk da linha a alterar; `NOVA_LINHA` cria uma linha adicional;
    `None` altera a primeira linha (criando-a se não existir).
    Retorna (mensagem, linha ou None, mudou_estrutura).
    """
    from apps.courses.models import MatrixComponent
    from apps.professors.models import Professor

    Status = MatrixComponent.StatusChoices
    alocacao = obter_alocacao_curricular(componente, unidade)
    linhas = _linhas(componente, alocacao).select_for_update()
    nome = componente.nome_disciplina

    if valor == NAO_OFERECIDA:
        if linha_id == NOVA_LINHA:
            raise AlocacaoError('"Não oferecido" vale para o componente inteiro.', status=400)
        tinha_varias = linhas.count() > 1
        linhas.delete()
        componente.status = Status.NAO_OFERECIDA
        componente.save(update_fields=['status'])
        return f'Componente {nome} marcado como Não oferecido.', None, tinha_varias

    docente = None
    if valor not in (SEM_PROFESSOR, '', None):
        try:
            docente = Professor.objects.get(pk=int(valor))
        except (ValueError, TypeError, Professor.DoesNotExist):
            raise AlocacaoError('Professor não encontrado.', status=404)
        if docente.readaptado_vigente:
            raise AlocacaoError(
                f'{docente.nome} está readaptado e não pode ficar em sala de aula. '
                'Registre a atuação dele no módulo Extracurricular.',
                status=409,
            )
        if linhas.filter(docente=docente).exclude(pk=linha_id if str(linha_id).isdigit() else None).exists():
            raise AlocacaoError(
                f'{docente.nome} já está alocado neste componente. Escolha outro docente.',
                status=409,
            )

    if linha_id == NOVA_LINHA:
        linha = AlocacaoTurmaDocente(
            alocacao_curricular=alocacao,
            componente_matriz=componente,
            carga_horaria_contabilizada=carga_da_linha(componente),
            compartilhado=componente.compartilhado,
        )
    elif linha_id in (None, ''):
        linha = linhas.first() or AlocacaoTurmaDocente(
            alocacao_curricular=alocacao,
            componente_matriz=componente,
            carga_horaria_contabilizada=carga_da_linha(componente),
            compartilhado=componente.compartilhado,
        )
    else:
        try:
            linha = linhas.get(pk=int(linha_id))
        except (ValueError, AlocacaoTurmaDocente.DoesNotExist):
            raise AlocacaoError('Linha de alocação não encontrada.', status=404)

    linha.docente = docente
    linha.carga_horaria_contabilizada = carga_da_linha(componente)
    linha.compartilhado = componente.compartilhado
    linha.save()
    _sincronizar_carencia(linha)

    recalcular_status(componente, alocacao)

    if docente is None:
        mensagem = f'Componente {nome} marcado como Sem professor (carência declarada).'
    else:
        mensagem = f'Docente alocado para {nome} com sucesso!'
    return mensagem, linha, False


@transaction.atomic
def remover_linha(componente, unidade, linha_id):
    """Remove uma linha adicional (a carência associada é removida junto)."""
    alocacao = buscar_alocacao_curricular(componente, unidade)
    if alocacao is None:
        raise AlocacaoError('Linha de alocação não encontrada.', status=404)
    linhas = _linhas(componente, alocacao).select_for_update()
    try:
        linha = linhas.get(pk=int(linha_id))
    except (ValueError, TypeError, AlocacaoTurmaDocente.DoesNotExist):
        raise AlocacaoError('Linha de alocação não encontrada.', status=404)
    linha.delete()
    recalcular_status(componente, alocacao)
    return f'Linha removida de {componente.nome_disciplina}.'


@transaction.atomic
def definir_quantidade_turmas(componente, unidade, quantidade):
    """Valida e grava a quantidade de turmas; devolve (mensagem, quantidade)."""
    texto = str(quantidade or '').strip()
    if not texto.isascii() or not texto.isdigit():
        raise AlocacaoError('Informe apenas números para a quantidade de turmas.', status=400)
    numero = int(texto)
    if not 1 <= numero <= MAX_TURMAS:
        raise AlocacaoError(f'A quantidade de turmas deve estar entre 1 e {MAX_TURMAS}.', status=400)

    componente.quantidade_turmas = numero
    componente.save(update_fields=['quantidade_turmas'])
    alocacao = buscar_alocacao_curricular(componente, unidade)
    if alocacao is not None:
        recalcular_status(componente, alocacao)
    return f'{componente.nome_disciplina}: {numero} turma(s).', numero


def atribuir_docente(componente, professor, unidade=None):
    """Atalho para fixtures e scripts: aloca `professor` no componente.

    Usa a primeira unidade da matriz quando `unidade` não é informada.
    """
    unidade = unidade or componente.matriz.unidades.order_by('pk').first()
    return definir_escolha(componente, unidade, str(professor.pk))
