import django.db.models.deletion
from django.db import migrations, models


def migrate_curso_to_course(apps, schema_editor):
    """
    Para cada matriz existente:
    - Copia a FK de CourseUnit.curso (Course) para o novo campo curso_id (direto para Course)
    - Adiciona CourseUnit.unidade ao M2M unidades
    """
    CurriculumMatrix = apps.get_model('courses', 'CurriculumMatrix')
    for matrix in CurriculumMatrix.objects.select_related('curso_unit', 'curso_unit__curso', 'curso_unit__unidade').all():
        if matrix.curso_unit_id:
            course_unit = matrix.curso_unit
            matrix.curso_id = course_unit.curso_id
            matrix.save(update_fields=['curso_id'])
            matrix.unidades.add(course_unit.unidade_id)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('courses', '0002_initial'),
    ]

    operations = [
        # Passo 1: Renomear o campo existente curso (FK para CourseUnit) para curso_unit
        migrations.RenameField(
            model_name='curriculummatrix',
            old_name='curso',
            new_name='curso_unit',
        ),
        # Passo 2: Adicionar novo campo curso (FK para Course, null temporariamente)
        migrations.AddField(
            model_name='curriculummatrix',
            name='curso',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='matrizes',
                to='courses.course',
                verbose_name='Curso',
            ),
        ),
        # Passo 3: Adicionar M2M unidades
        migrations.AddField(
            model_name='curriculummatrix',
            name='unidades',
            field=models.ManyToManyField(
                blank=True,
                related_name='curriculum_matrices',
                to='core.unidade',
                verbose_name='Unidades',
            ),
        ),
        # Passo 4: Migração de dados
        migrations.RunPython(migrate_curso_to_course, reverse_code=migrations.RunPython.noop),
        # Passo 5: Remover o campo curso_unit (antigo FK para CourseUnit)
        migrations.RemoveField(
            model_name='curriculummatrix',
            name='curso_unit',
        ),
    ]
