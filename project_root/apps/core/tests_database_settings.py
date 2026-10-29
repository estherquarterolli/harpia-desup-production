from pathlib import Path

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase

from config.settings.database_options import configure_for_transaction_pooler, resolve_sqlite_database_path


class SQLiteDatabasePathTests(SimpleTestCase):
    def test_caminho_relativo_usa_pasta_do_projeto(self):
        database = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'local.sqlite3'}
        base_dir = Path.cwd() / 'harpia-project'
        result = resolve_sqlite_database_path(database, base_dir)
        self.assertEqual(result['NAME'], str(base_dir / 'local.sqlite3'))

    def test_preserva_caminhos_absolutos_memoria_e_uri(self):
        for name in (str(Path.cwd() / 'harpia.sqlite3'), ':memory:', 'file:memorydb?mode=memory&cache=shared'):
            with self.subTest(name=name):
                database = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': name}
                self.assertEqual(resolve_sqlite_database_path(database, Path.cwd() / 'project')['NAME'], name)

    def test_nao_altera_outros_bancos(self):
        database = {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'harpia'}
        self.assertEqual(resolve_sqlite_database_path(database.copy(), Path.cwd() / 'project'), database)


class DatabaseSchemaCompatibilityTests(TestCase):
    def test_campos_dos_models_existem_e_opcionais_aceitam_null_no_banco(self):
        """Execute também com migrations reais para detectar divergências de schema."""
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))
            for model in apps.get_models(include_auto_created=True):
                if not model._meta.managed or model._meta.proxy:
                    continue
                table = model._meta.db_table
                with self.subTest(table=table):
                    self.assertIn(table, tables)
                if table not in tables:
                    continue
                columns = {
                    col.name: col
                    for col in connection.introspection.get_table_description(cursor, table)
                }
                for field in model._meta.local_fields:
                    with self.subTest(table=table, field=field.name):
                        self.assertIn(field.column, columns)
                        if field.column in columns and field.null:
                            self.assertTrue(columns[field.column].null_ok)


class TransactionPoolerDatabaseSettingsTests(SimpleTestCase):
    def test_desativa_cursores_server_side_no_postgresql(self):
        database = {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'postgres',
            'OPTIONS': {'sslmode': 'require'},
        }

        configured = configure_for_transaction_pooler(database)

        self.assertTrue(configured['DISABLE_SERVER_SIDE_CURSORS'])
        self.assertNotIn('DISABLE_SERVER_SIDE_CURSORS', configured['OPTIONS'])
        self.assertEqual(configured['OPTIONS']['sslmode'], 'require')

    def test_nao_altera_outros_bancos(self):
        database = {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'harpia',
        }

        configured = configure_for_transaction_pooler(database)

        self.assertNotIn('DISABLE_SERVER_SIDE_CURSORS', configured)
