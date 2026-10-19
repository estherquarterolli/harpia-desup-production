from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_cargos_diretivos_iniciais"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tipocargodiretivo",
            name="exige_curso",
            field=models.BooleanField(
                default=False,
                help_text="Ao preencher o cargo, será necessário escolher um curso da unidade.",
                verbose_name="Cargo por curso",
            ),
        ),
        migrations.AlterField(
            model_name="tipocargodiretivo",
            name="permite_multiplos",
            field=models.BooleanField(
                default=False,
                help_text="Marque para permitir mais de um ocupante vigente ao mesmo tempo.",
                verbose_name="Permite mais de um ocupante",
            ),
        ),
        migrations.AlterField(
            model_name="tipocargodiretivo",
            name="ativo",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="Cargos inativos permanecem no histórico, mas não recebem novos ocupantes.",
                verbose_name="Ativo",
            ),
        ),
        migrations.AlterField(
            model_name="ocupacaoequipediretiva",
            name="curso",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ocupacoes_diretivas",
                to="courses.courseunit",
                verbose_name="Curso",
            ),
        ),
    ]
