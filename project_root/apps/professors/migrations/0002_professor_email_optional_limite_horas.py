from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('professors', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='professor',
            name='rh_email',
            field=models.EmailField(blank=True, null=True, verbose_name='E-mail (RH)'),
        ),
        migrations.AddField(
            model_name='professor',
            name='limite_horas_extra',
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                help_text='Máximo de horas extracurriculares permitidas. Se vazio, usa o limite total do contrato.',
                max_digits=5,
                null=True,
                verbose_name='Limite de Horas Extracurriculares',
            ),
        ),
    ]
