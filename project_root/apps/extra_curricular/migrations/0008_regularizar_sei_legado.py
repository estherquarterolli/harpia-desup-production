import json

from django.db import migrations, models


SEI_PATTERN = r"^SEI-\d{6}/\d{6}/\d{4}$"


def remover_constraint_externa(apps, schema_editor):
    # Produção recebeu esta CHECK fora das migrations, com registros inválidos
    # preexistentes. Mesmo uma atualização de criado_por (SET_NULL na exclusão
    # de usuário) revalida a linha e falha. Abaixo ela será recriada e validada
    # pelo Django, depois de preservar e regularizar os valores legados.
    if schema_editor.connection.vendor == "postgresql":
        table = schema_editor.quote_name(
            apps.get_model("extra_curricular", "PendenciaExtra")._meta.db_table
        )
        schema_editor.execute(
            f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "chk_sei_formato"'
        )


def preservar_seis_invalidos(apps, schema_editor):
    alias = schema_editor.connection.alias
    PendenciaExtra = apps.get_model("extra_curricular", "PendenciaExtra")
    AuditoriaGlobal = apps.get_model("core", "AuditoriaGlobal")
    invalidas = PendenciaExtra.objects.using(alias).exclude(
        models.Q(sei_numero__isnull=True)
        | models.Q(sei_numero="")
        | models.Q(sei_numero__regex=SEI_PATTERN)
    )
    for dados in list(invalidas.order_by("pk").values(
        "pk", "professor_id", "unidade_id", "semestre", "sei_numero"
    )):
        # Não é possível deduzir o número correto. Guardamos o original antes
        # de marcar o SEI como não informado, sem alterar status ou justificativas.
        AuditoriaGlobal.objects.using(alias).create(
            acao="SEI_LEGADO_INVALIDO",
            detalhes=json.dumps(dados, ensure_ascii=False),
        )
        PendenciaExtra.objects.using(alias).filter(pk=dados["pk"]).update(sei_numero=None)


class Migration(migrations.Migration):
    dependencies = [
        ("extra_curricular", "0007_tcc_sem_limite_orientandos"),
        ("core", "0003_rename_tables_harpiadb_prefix"),
    ]

    operations = [
        migrations.RunPython(remover_constraint_externa, migrations.RunPython.noop),
        # O rollback mantém a regularização e sua auditoria; não restaura SEIs inválidos.
        migrations.RunPython(preservar_seis_invalidos, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="pendenciaextra",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(sei_numero__isnull=True)
                    | models.Q(sei_numero="")
                    | models.Q(sei_numero__regex=SEI_PATTERN)
                ),
                name="chk_sei_formato",
            ),
        ),
    ]
