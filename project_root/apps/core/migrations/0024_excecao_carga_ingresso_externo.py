from django.db import migrations, models


MOTIVOS_INGRESSO_EXTERNO = (
    "Professor cadastrado já como RAT.",
    "RAT definido pela DESUP na edição do professor.",
)


def marcar_rats_de_ingresso_existentes(apps, schema_editor):
    ExcecaoCargaUnidade = apps.get_model('core', 'ExcecaoCargaUnidade')
    ExcecaoCargaUnidade.objects.using(schema_editor.connection.alias).filter(
        motivo_decisao__in=MOTIVOS_INGRESSO_EXTERNO,
    ).update(ingresso_externo=True)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0023_preferencias_comunicacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='excecaocargaunidade',
            name='ingresso_externo',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    'Indica que as horas do RAT são toda a carga autorizada do professor '
                    'externo no ensino superior, e não horas adicionais.'
                ),
                verbose_name='RAT de ingresso externo',
            ),
        ),
        migrations.RunPython(marcar_rats_de_ingresso_existentes, migrations.RunPython.noop),
    ]
