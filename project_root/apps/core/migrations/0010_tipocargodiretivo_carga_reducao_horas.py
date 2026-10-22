import django.core.validators
from decimal import Decimal
from django.db import migrations, models
from django.db.models import Max


def copiar_reducao_existente(apps, schema_editor):
    """Cargos já em uso herdam a maior redução registrada em suas ocupações."""
    TipoCargoDiretivo = apps.get_model('core', 'TipoCargoDiretivo')
    OcupacaoEquipeDiretiva = apps.get_model('core', 'OcupacaoEquipeDiretiva')
    maiores = OcupacaoEquipeDiretiva.objects.values('cargo_id').annotate(m=Max('carga_reducao_horas'))
    for item in maiores:
        TipoCargoDiretivo.objects.filter(pk=item['cargo_id']).update(carga_reducao_horas=item['m'] or Decimal('0.00'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_atividadeestagiosupervisao'),
    ]

    operations = [
        migrations.AddField(
            model_name='tipocargodiretivo',
            name='carga_reducao_horas',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('0.00'), max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00')),
                            django.core.validators.MaxValueValidator(Decimal('168.00'))],
                help_text='Horas semanais de redução de carga que o cargo garante a quem o ocupa. Definida pela DESUP.',
                verbose_name='Carga horária de redução semanal',
            ),
        ),
        migrations.RunPython(copiar_reducao_existente, migrations.RunPython.noop),
    ]
