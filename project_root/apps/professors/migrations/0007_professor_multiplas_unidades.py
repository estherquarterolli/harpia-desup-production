from django.db import migrations, models


def copiar_unidade_principal(apps, schema_editor):
    Professor = apps.get_model('professors', 'Professor')
    for professor in Professor.objects.exclude(unidade_principal_id=None).iterator():
        professor.unidades.add(professor.unidade_principal_id)


def limpar_unidades(apps, schema_editor):
    Professor = apps.get_model('professors', 'Professor')
    for professor in Professor.objects.all().iterator():
        professor.unidades.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('professors', '0006_rename_tables_harpiadb_prefix'),
    ]

    operations = [
        migrations.AddField(
            model_name='professor',
            name='unidades',
            field=models.ManyToManyField(
                blank=True,
                db_table='harpiadb_professores_professor_unidades',
                help_text='Unidades às quais o professor está vinculado.',
                related_name='professores_vinculados',
                to='core.unidade',
                verbose_name='Unidades',
            ),
        ),
        migrations.RunPython(copiar_unidade_principal, limpar_unidades),
        migrations.RemoveField(
            model_name='professor',
            name='materia',
        ),
    ]
