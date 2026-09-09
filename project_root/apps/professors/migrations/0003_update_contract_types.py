from django.db import migrations


# Professor FAETEC I é destinado a professores dos anos iniciais (não se aplica à
# rede FAETEC/DESUP), então os contratos existentes são renomeados para FAETEC II.
RENAMES = [
    ("Professor FAETEC I - 40h", "Professor FAETEC II - 40h"),
    ("Professor FAETEC I - 20h", "Professor FAETEC II - 20h"),
]

# Novos tipos de contrato solicitados pela coordenação DESUP.
# Contratado 20h/40h espelham os limites de horas/turmas do FAETEC II equivalente,
# mas com categoria TERCEIRIZADO. Cedido espelha os limites do Instrutor.
NEW_CONTRACT_TYPES = [
    {
        "nome": "Professor Contratado 20h",
        "categoria": "TERCEIRIZADO",
        "regime_trabalho": "20h",
        "dias_presenca_obrigatorios": 2,
        "max_class_hours": 16,
        "max_total_hours": 20,
        "max_classes": 4,
    },
    {
        "nome": "Professor Contratado 40h",
        "categoria": "TERCEIRIZADO",
        "regime_trabalho": "40h",
        "dias_presenca_obrigatorios": 3,
        "max_class_hours": 32,
        "max_total_hours": 40,
        "max_classes": 6,
    },
    {
        "nome": "Professor Cedido",
        "categoria": "EFETIVO",
        "regime_trabalho": "40h",
        "dias_presenca_obrigatorios": 3,
        "max_class_hours": 20,
        "max_total_hours": 40,
        "max_classes": 4,
    },
]


def forwards(apps, schema_editor):
    ContractType = apps.get_model("professors", "ContractType")

    for old_nome, new_nome in RENAMES:
        ContractType.objects.filter(nome=old_nome).update(nome=new_nome)

    for data in NEW_CONTRACT_TYPES:
        ContractType.objects.get_or_create(nome=data["nome"], defaults=data)


def backwards(apps, schema_editor):
    ContractType = apps.get_model("professors", "ContractType")

    for data in NEW_CONTRACT_TYPES:
        ContractType.objects.filter(nome=data["nome"]).delete()

    for old_nome, new_nome in RENAMES:
        ContractType.objects.filter(nome=new_nome).update(nome=old_nome)


class Migration(migrations.Migration):

    dependencies = [
        ("professors", "0002_professor_email_optional_limite_horas"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
