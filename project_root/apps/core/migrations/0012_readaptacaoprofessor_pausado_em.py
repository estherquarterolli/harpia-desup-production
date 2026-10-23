from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_solicitacaoprofessorexterno_dados_cadastro"),
    ]

    operations = [
        migrations.AddField(
            model_name="readaptacaoprofessor",
            name="pausado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Pausada em"),
        ),
    ]
