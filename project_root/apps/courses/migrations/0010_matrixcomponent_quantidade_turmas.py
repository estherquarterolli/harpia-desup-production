from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0009_remove_matrixcomponent_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='matrixcomponent',
            name='quantidade_turmas',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='Número de turmas ofertadas do componente (padrão: 1).',
                verbose_name='Quantidade de turmas',
            ),
        ),
    ]
