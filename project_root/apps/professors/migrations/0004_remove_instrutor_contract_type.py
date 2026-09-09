from django.db import migrations


# "Instrutor" foi retirado da lista de tipos de contrato a pedido da DESUP.
# Exclusão definitiva: se algum Professor ainda estiver vinculado a esse tipo,
# a FK com on_delete=PROTECT impede a exclusão e esta migration falha (o que é
# intencional — sinaliza que é preciso migrar esses professores antes).
INSTRUTOR = {
    "nome": "Instrutor",
    "categoria": "EFETIVO",
    "regime_trabalho": "40h",
    "dias_presenca_obrigatorios": 3,
    "max_class_hours": 20,
    "max_total_hours": 40,
    "max_classes": 4,
}


def forwards(apps, schema_editor):
    ContractType = apps.get_model("professors", "ContractType")
    ContractType.objects.filter(nome=INSTRUTOR["nome"]).delete()


def backwards(apps, schema_editor):
    ContractType = apps.get_model("professors", "ContractType")
    ContractType.objects.get_or_create(nome=INSTRUTOR["nome"], defaults=INSTRUTOR)


class Migration(migrations.Migration):

    dependencies = [
        ("professors", "0003_update_contract_types"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
