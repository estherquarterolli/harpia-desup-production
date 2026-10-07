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
