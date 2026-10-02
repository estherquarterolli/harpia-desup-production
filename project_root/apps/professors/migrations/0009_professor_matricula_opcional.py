from django.db import migrations, models


def matriculas_provisorias_para_nulo(apps, schema_editor):
    Professor = apps.get_model('professors', 'Professor')
    Professor.objects.filter(rh_matricula__startswith='SEM-MATRICULA-').update(rh_matricula=None)
    Professor.objects.filter(rh_matricula='').update(rh_matricula=None)


class Migration(migrations.Migration):

    dependencies = [
        ('professors', '0008_professor_locais_lotacao'),
    ]

    operations = [
        migrations.AlterField(
            model_name='professor',
            name='rh_matricula',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Opcional: nem todo professor possui matrícula.',
                max_length=50,
                null=True,
                unique=True,
                verbose_name='Matrícula RH',
            ),
        ),
        migrations.RunPython(matriculas_provisorias_para_nulo, migrations.RunPython.noop),
    ]
