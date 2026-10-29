from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_merge_20261028_2048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='excecaocargaunidade',
            name='data_fim',
            field=models.DateField(blank=True, null=True, verbose_name='Fim da vigência'),
        ),
    ]
