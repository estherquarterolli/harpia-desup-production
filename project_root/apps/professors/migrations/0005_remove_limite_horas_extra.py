from django.db import migrations


def drop_limite_horas_extra(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute('ALTER TABLE professors_professor DROP COLUMN IF EXISTS limite_horas_extra;')
    elif schema_editor.connection.vendor == "sqlite":
        cursor = schema_editor.connection.cursor()
        cursor.execute("PRAGMA table_info(professors_professor)")
        cols = [r[1] for r in cursor.fetchall()]
        if "limite_horas_extra" in cols:
            schema_editor.execute("ALTER TABLE professors_professor DROP COLUMN limite_horas_extra")


class Migration(migrations.Migration):

    dependencies = [
        ("professors", "0004_remove_instrutor_contract_type"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name="professor",
                    name="limite_horas_extra",
                ),
            ],
            database_operations=[
                migrations.RunPython(drop_limite_horas_extra, migrations.RunPython.noop),
            ],
        ),
    ]
