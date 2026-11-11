from django.db import migrations


CODIGO_COORDENACAO_CURSO = 'COORDENACAO_DE_CURSO'


def configurar_multiplos_coordenadores(apps, schema_editor):
    TipoCargoDiretivo = apps.get_model('core', 'TipoCargoDiretivo')
    TipoCargoDiretivo.objects.exclude(
        codigo=CODIGO_COORDENACAO_CURSO,
    ).update(permite_multiplos=False)
    TipoCargoDiretivo.objects.filter(
        codigo=CODIGO_COORDENACAO_CURSO,
    ).update(permite_multiplos=True, exige_curso=True)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0016_solicitacao_suporte'),
    ]

    operations = [
        migrations.RunPython(
            configurar_multiplos_coordenadores,
            migrations.RunPython.noop,
        ),
    ]
