from django.db import migrations, models
from django.db.models.functions import Trim, Upper


CONSTRAINT_NAME = 'harpia_matriz_turno_valido'
VALID_TURNOS = ['M', 'T', 'N']


def normalize_turnos(apps, schema_editor):
    CurriculumMatrix = apps.get_model('courses', 'CurriculumMatrix')
    CurriculumMatrix.objects.exclude(turno__isnull=True).update(
        turno=Upper(Trim('turno')),
    )
    CurriculumMatrix.objects.filter(turno='').update(turno=None)

    invalidos = list(
        CurriculumMatrix.objects.exclude(turno__isnull=True)
        .exclude(turno__in=VALID_TURNOS)
        .values_list('turno', flat=True)
        .distinct()
    )
    if invalidos:
        raise RuntimeError(
            'Existem turnos inválidos em harpiadb_cursos_matriz_curricular: '
            + ', '.join(sorted(str(valor) for valor in invalidos))
        )


def _constraint():
    return models.CheckConstraint(
        condition=models.Q(turno__isnull=True) | models.Q(turno__in=VALID_TURNOS),
        name=CONSTRAINT_NAME,
    )


def add_constraint_if_missing(apps, schema_editor):
    CurriculumMatrix = apps.get_model('courses', 'CurriculumMatrix')
    table_name = CurriculumMatrix._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)
    if CONSTRAINT_NAME not in constraints:
        schema_editor.add_constraint(CurriculumMatrix, _constraint())


def remove_constraint_if_present(apps, schema_editor):
    CurriculumMatrix = apps.get_model('courses', 'CurriculumMatrix')
    table_name = CurriculumMatrix._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)
    if CONSTRAINT_NAME in constraints:
        schema_editor.remove_constraint(CurriculumMatrix, _constraint())


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0007_matrixcomponent_disciplina_temporaria'),
    ]

    operations = [
        migrations.RunPython(normalize_turnos, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_constraint_if_missing, remove_constraint_if_present),
            ],
            state_operations=[
                migrations.AddConstraint(
                    model_name='curriculummatrix',
                    constraint=_constraint(),
                ),
            ],
        ),
    ]
