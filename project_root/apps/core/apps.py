from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def set_database_session_settings(sender, connection, **kwargs):
    if connection.vendor == 'mysql':
        cursor = connection.cursor()
        cursor.execute("SET SESSION sql_mode='STRICT_TRANS_TABLES'")
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")


class CoreConfig(AppConfig):
    name = 'apps.core'
