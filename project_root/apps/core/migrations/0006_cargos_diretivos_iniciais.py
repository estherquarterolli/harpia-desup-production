from django.db import migrations


CARGOS_INICIAIS = (
    ("Diretor(a)", "DIRECAO", False, False, 10),
    ("Vice-Diretor(a)", "VICE_DIRECAO", False, False, 20),
    ("Secretário(a)", "SECRETARIA", False, True, 30),
    ("Coordenação de Curso", "COORDENACAO_DE_CURSO", True, False, 40),
    (
        "Coordenação de Pesquisa e Extensão",
        "COORDENACAO_DE_PESQUISA_E_EXTENSAO",
        False,
        True,
        50,
    ),
    ("Coordenação de Estágio", "COORDENACAO_DE_ESTAGIO", False, True, 60),
)


def criar_cargos_iniciais(apps, schema_editor):
    TipoCargoDiretivo = apps.get_model("core", "TipoCargoDiretivo")
    for nome, codigo, exige_curso, permite_multiplos, ordem in CARGOS_INICIAIS:
        TipoCargoDiretivo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nome": nome,
                "exige_curso": exige_curso,
                "permite_multiplos": permite_multiplos,
                "ativo": True,
                "ordem": ordem,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0005_tipocargodiretivo_excecaocargaunidade_and_more")]

    operations = [
        # O retorno da migração de esquema preserva os registros para não apagar
        # cargos já referenciados por ocupações criadas depois da implantação.
        migrations.RunPython(criar_cargos_iniciais, migrations.RunPython.noop),
    ]
