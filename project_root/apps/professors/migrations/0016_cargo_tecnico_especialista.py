from django.db import migrations


def criar_cargo(apps, schema_editor):
    ContractType = apps.get_model('professors', 'ContractType')
    ContractType.objects.using(schema_editor.connection.alias).get_or_create(
        nome='TÉCNICO ESPECIALISTA',
        defaults=dict(
            categoria='EFETIVO', regime_trabalho='40h', dias_presenca_obrigatorios=3,
            max_class_hours=20, max_total_hours=40, max_classes=8,
        ),
    )


class Migration(migrations.Migration):
    dependencies = [('professors', '0015_vinculo_cedido_secretario_academico')]

    operations = [migrations.RunPython(criar_cargo, migrations.RunPython.noop)]
