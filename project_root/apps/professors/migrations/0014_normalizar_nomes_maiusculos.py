from django.db import migrations


def normalizar_nomes(apps, schema_editor):
    Professor = apps.get_model('professors', 'Professor')
    registros = Professor.objects.using(schema_editor.connection.alias)
    # Python preserva acentos em todos os bancos, inclusive SQLite, cujo UPPER
    # padrão só converte ASCII. Atualiza exclusivamente os campos de nome.
    ultimo_pk = 0
    while True:
        lote = list(registros.filter(pk__gt=ultimo_pk).order_by('pk').only(
            'pk', 'rh_nome', 'desup_nome',
        )[:500])
        if not lote:
            break
        alterados = []
        for professor in lote:
            mudou = False
            for campo in ('rh_nome', 'desup_nome'):
                original = getattr(professor, campo)
                nome = original.upper() if original is not None else None
                if nome is not None and len(nome) > 255:
                    raise ValueError(f'Nome excede 255 caracteres após normalização: professor {professor.pk}.')
                if nome != original:
                    setattr(professor, campo, nome)
                    mudou = True
            if mudou:
                alterados.append(professor)
        registros.bulk_update(alterados, ['rh_nome', 'desup_nome'], batch_size=500)
        ultimo_pk = lote[-1].pk


class Migration(migrations.Migration):
    dependencies = [('professors', '0013_professor_setor_origem_and_more')]

    # A capitalização anterior não é recuperável; o rollback mantém os nomes.
    operations = [migrations.RunPython(normalizar_nomes, migrations.RunPython.noop)]
