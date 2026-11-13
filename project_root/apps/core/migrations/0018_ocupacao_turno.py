from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0017_multiplos_somente_coordenacao_curso')]

    operations = [
        migrations.AddField(
            model_name='ocupacaoequipediretiva',
            name='turno',
            field=models.CharField(
                blank=True, default='', max_length=1,
                choices=[('M', 'Manhã'), ('T', 'Tarde'), ('N', 'Noite')],
                verbose_name='Turno do curso',
            ),
        ),
    ]
