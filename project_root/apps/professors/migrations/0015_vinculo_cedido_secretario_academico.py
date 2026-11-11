from django.db import migrations, models


def criar_cargo(apps, schema_editor):
    ContractType = apps.get_model('professors', 'ContractType')
    ContractType.objects.using(schema_editor.connection.alias).get_or_create(
        nome='SECRETÁRIO ACADÊMICO',
        defaults=dict(
            categoria='EFETIVO', regime_trabalho='40h', dias_presenca_obrigatorios=3,
            max_class_hours=20, max_total_hours=40, max_classes=8,
        ),
    )


class Migration(migrations.Migration):
    dependencies = [('professors', '0014_normalizar_nomes_maiusculos')]

    operations = [
        migrations.AlterField(
            model_name='professor',
            name='vinculo_empregaticio',
            field=models.CharField(blank=True, choices=[('EFETIVO', 'Efetivo'), ('CONTR TEMPORARIO', 'Contrato temporário'), ('CARGO COMISSAO', 'Cargo em comissão'), ('REQUISICAO INTERNA', 'Requisição interna'), ('CEDIDO', 'Cedido')], default='', help_text='Vínculo individual do professor, independente do cargo.', max_length=30, verbose_name='Vínculo empregatício'),
        ),
        migrations.RunPython(criar_cargo, migrations.RunPython.noop),
    ]
