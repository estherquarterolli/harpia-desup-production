from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("professors", "0004_remove_instrutor_contract_type"),
    ]

    # SeparateDatabaseAndState: o estado do Django (usado por makemigrations,
    # serializers, admin etc.) esquece o campo normalmente, mas a operacao real
    # no banco usa SQL com IF EXISTS. Isso e necessario porque esse banco do
    # Supabase nao foi criado 100% via `manage.py migrate` (foi montado por um
    # script de migracao a parte), entao o histórico de migrations do Django
    # diz que a coluna existe, mas na pratica ela nunca foi criada — um
    # RemoveField comum falha com "column does not exist".
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="professor",
                    name="limite_horas_extra",
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE professors_professor DROP COLUMN IF EXISTS limite_horas_extra;',
                    reverse_sql=(
                        'ALTER TABLE professors_professor '
                        'ADD COLUMN IF NOT EXISTS limite_horas_extra numeric(5,1) NULL;'
                    ),
                ),
            ],
        ),
    ]
