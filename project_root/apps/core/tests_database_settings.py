from django.test import SimpleTestCase

from config.settings.database_options import configure_for_transaction_pooler


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
