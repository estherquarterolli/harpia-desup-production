from pathlib import Path


def resolve_sqlite_database_path(database, base_dir):
    """Keep a relative SQLite URL tied to the project, regardless of cwd."""
    if database.get('ENGINE') == 'django.db.backends.sqlite3':
        name = str(database.get('NAME') or '')
        if name and name != ':memory:' and not name.startswith('file:'):
            path = Path(name)
            if not path.is_absolute():
                database['NAME'] = str(Path(base_dir) / path)
    return database


def configure_for_transaction_pooler(database):
    """Make PostgreSQL connections safe behind transaction-mode poolers.

    Django's QuerySet.iterator() uses named, server-side cursors by default.
    Transaction poolers such as Supabase/PgBouncer may send the next fetch to a
    different database connection, where that cursor doesn't exist, resulting
    in psycopg2.errors.InvalidCursorName.

    This setting belongs at the database alias root (not inside ``OPTIONS``).
    Other database backends are returned unchanged.
    """
    if database.get('ENGINE') == 'django.db.backends.postgresql':
        database['DISABLE_SERVER_SIDE_CURSORS'] = True
    return database
