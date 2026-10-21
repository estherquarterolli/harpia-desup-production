from django.db import migrations, models


def add_column_if_missing(apps, schema_editor):
    # O script SQL de importação já pode ter criado a coluna no Supabase.
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "ALTER TABLE harpiadb_professores_professor "
            "ADD COLUMN IF NOT EXISTS locais_lotacao TEXT NOT NULL DEFAULT ''"
        )
    elif schema_editor.connection.vendor == "sqlite":
        cursor = schema_editor.connection.cursor()
        cursor.execute("PRAGMA table_info(harpiadb_professores_professor)")
        cols = [r[1] for r in cursor.fetchall()]
        if "locais_lotacao" not in cols:
            schema_editor.execute("ALTER TABLE harpiadb_professores_professor ADD COLUMN locais_lotacao TEXT NOT NULL DEFAULT ''")


class Migration(migrations.Migration):

    dependencies = [
        ('professors', '0007_professor_multiplas_unidades'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_column_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='professor',
                    name='locais_lotacao',
                    field=models.TextField(
                        blank=True,
                        default='',
                        help_text="Setores de origem que não correspondem a uma unidade do sistema, separados por ' | '.",
                        verbose_name='Locais de lotação (não são unidades)',
                    ),
                ),
            ],
        ),
    ]
