from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations
from django.utils import timezone

TURNO_PADRAO_ALOCACAO = 'M'  # mesmo padrão de apps.allocations.views


def _semestre_atual():
    # Mesma regra de apps.allocations.services.semestre_atual: o consolidado
    # (AlocacaoCurricular) é sempre do semestre corrente.
    hoje = timezone.localdate()
    return f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"


def _unidade_da_matriz(matriz, componente):
    """Escolhe a unidade da matriz sem inventar dados.

    Uma só unidade: usa ela. Várias: prefere a unidade principal do docente
    quando ela pertence à matriz; senão, a de menor id (resultado determinístico).
    """
    unidades = list(matriz.unidades.order_by('pk'))
    if not unidades:
        return None
    if len(unidades) == 1:
        return unidades[0]
    principal_id = componente.docente.unidade_principal_id
    for unidade in unidades:
        if unidade.pk == principal_id:
            return unidade
    return unidades[0]


def copiar_docente_para_alocacao(apps, schema_editor):
    MatrixComponent = apps.get_model('courses', 'MatrixComponent')
    CourseUnit = apps.get_model('courses', 'CourseUnit')
    AlocacaoCurricular = apps.get_model('allocations', 'AlocacaoCurricular')
    AlocacaoTurmaDocente = apps.get_model('allocations', 'AlocacaoTurmaDocente')

    componentes = MatrixComponent.objects.filter(docente__isnull=False).select_related(
        'matriz', 'docente'
    )
    nao_mapeados = []

    for componente in componentes.iterator():
        matriz = componente.matriz
        unidade = _unidade_da_matriz(matriz, componente)
        course_unit = (
            CourseUnit.objects.filter(curso_id=matriz.curso_id, unidade=unidade).first()
            if unidade and matriz.curso_id else None
        )
        if not course_unit:
            nao_mapeados.append(
                f"componente {componente.pk} (matriz {matriz.pk}, docente {componente.docente_id})"
            )
            continue

        alocacao, _ = AlocacaoCurricular.objects.get_or_create(
            unidade=unidade,
            curso=course_unit,
            semestre=_semestre_atual(),
            turno=matriz.turno or TURNO_PADRAO_ALOCACAO,
        )
        carga = (Decimal(componente.carga_horaria or 0) / Decimal(20)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        AlocacaoTurmaDocente.objects.get_or_create(
            alocacao_curricular=alocacao,
            componente_matriz=componente,
            turma=None,
            docente_id=componente.docente_id,
            defaults={
                'carga_horaria_contabilizada': carga,
                'compartilhado': componente.compartilhado,
            },
        )

    if nao_mapeados:
        # Interrompe antes da migration que remove `docente`: nada é perdido.
        raise RuntimeError(
            "Não foi possível inferir a alocação curricular (matriz sem unidade ou sem "
            "vínculo em Cursos na Unidade) para: "
            + "; ".join(nao_mapeados)
            + ". Corrija esses dados e execute a migração novamente."
        )


def restaurar_docente_no_componente(apps, schema_editor):
    MatrixComponent = apps.get_model('courses', 'MatrixComponent')
    AlocacaoTurmaDocente = apps.get_model('allocations', 'AlocacaoTurmaDocente')

    for alocacao in AlocacaoTurmaDocente.objects.filter(docente__isnull=False).order_by('pk'):
        MatrixComponent.objects.filter(
            pk=alocacao.componente_matriz_id, docente__isnull=True
        ).update(docente_id=alocacao.docente_id)
    AlocacaoTurmaDocente.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('allocations', '0004_alocacao_turma_docente_carencia_rat'),
        ('courses', '0009_remove_matrixcomponent_unique_together'),
        ('professors', '0012_professor_area_atuacao'),
    ]

    operations = [
        migrations.RunPython(copiar_docente_para_alocacao, restaurar_docente_no_componente),
    ]
