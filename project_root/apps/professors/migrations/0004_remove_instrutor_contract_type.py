from django.db import migrations


# NOTA: esta migration tentava excluir o tipo de contrato "Instrutor", mas isso
# quebrou o deploy — 9 professores ja cadastrados usam esse tipo e a FK
# Professor.tipo_contrato e on_delete=PROTECT. Decisao: manter "Instrutor" no
# banco por ora. A migration foi neutralizada (no-op) em vez de removida do
# historico, para nao desalinhar os deploys que ja passaram por ela.
class Migration(migrations.Migration):

    dependencies = [
        ("professors", "0003_update_contract_types"),
    ]

    operations = []
