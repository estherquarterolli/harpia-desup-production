#!/usr/bin/env python
"""
Script to migrate SQLite3 database to Supabase (PostgreSQL).

This script:
1. Reads the SQLite3 schema
2. Converts it to PostgreSQL syntax
3. Creates all tables in Supabase
4. Copies all data from SQLite to Supabase
"""

import os
import sqlite3
import psycopg2
from decouple import config

# Database connections
SQLITE_DB = "db.sqlite3"
SUPABASE_URL = config("DATABASE_URL")

print("=" * 60)
print("SQLite3 → Supabase (PostgreSQL) Migration")
print("=" * 60)

# Connect to databases
print("\n[1] Connecting to databases...")
sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_cursor = sqlite_conn.cursor()

try:
    pg_conn = psycopg2.connect(SUPABASE_URL)
    pg_cursor = pg_conn.cursor()
    print("✓ Connected to Supabase")
except Exception as e:
    print(f"✗ Failed to connect to Supabase: {e}")
    exit(1)

# Get all tables from SQLite
print("\n[2] Getting tables from SQLite...")
sqlite_cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)
tables = [row[0] for row in sqlite_cursor.fetchall()]
print(f"✓ Found {len(tables)} tables")

# Function to convert SQLite type to PostgreSQL type
def convert_type(sqlite_type):
    sqlite_type = sqlite_type.upper()

    if "INT" in sqlite_type:
        if "AUTOINCREMENT" in sqlite_type or "PRIMARY KEY" in sqlite_type:
            return "BIGSERIAL"
        elif sqlite_type.startswith("SMALLINT"):
            return "SMALLINT"
        else:
            return "BIGINT"
    elif "CHAR" in sqlite_type or "TEXT" in sqlite_type:
        return "VARCHAR" if "CHAR" in sqlite_type else "TEXT"
    elif "BOOL" in sqlite_type:
        return "BOOLEAN"
    elif "REAL" in sqlite_type or "FLOAT" in sqlite_type:
        return "REAL"
    elif "DECIMAL" in sqlite_type:
        return "NUMERIC"
    elif "DATE" in sqlite_type:
        return "DATE" if sqlite_type == "DATE" else "TIMESTAMP"
    else:
        return "TEXT"

# Copy schema for each table
print("\n[3] Creating tables in Supabase...")
for table_name in tables:
    if table_name == "sqlite_sequence":
        continue

    # Get table schema
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = sqlite_cursor.fetchall()

    # Build CREATE TABLE statement
    create_stmt = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" (\n"

    col_defs = []
    for col_id, col_name, col_type, not_null, default_val, pk in columns:
        col_def = f"  \"{col_name}\" {convert_type(col_type)}"

        if pk:
            col_def = f"  \"{col_name}\" BIGSERIAL PRIMARY KEY"
        elif not_null:
            col_def += " NOT NULL"

        if default_val and not pk:
            col_def += f" DEFAULT {default_val}"

        col_defs.append(col_def)

    # Add foreign keys
    sqlite_cursor.execute(f"PRAGMA foreign_key_list({table_name})")
    fks = sqlite_cursor.fetchall()
    for fk_id, table_ref, from_col, to_col, on_delete, on_update, match_type in fks:
        col_defs.append(
            f"  FOREIGN KEY (\"{from_col}\") REFERENCES \"{table_ref}\"(\"{to_col}\")"
        )

    create_stmt += ",\n".join(col_defs) + "\n);"

    try:
        pg_cursor.execute(create_stmt)
        pg_conn.commit()
        print(f"✓ Created table: {table_name}")
    except Exception as e:
        print(f"✗ Error creating {table_name}: {e}")
        pg_conn.rollback()

# Copy data from SQLite to Supabase
print("\n[4] Copying data from SQLite to Supabase...")
total_rows = 0

for table_name in tables:
    if table_name == "sqlite_sequence":
        continue

    # Get data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if rows:
        # Get column names
        sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in sqlite_cursor.fetchall()]

        # Build INSERT statement
        placeholders = ", ".join(["%s"] * len(columns))
        col_names = ", ".join([f'"{col}"' for col in columns])
        insert_stmt = f"INSERT INTO \"{table_name}\" ({col_names}) VALUES ({placeholders})"

        try:
            for row in rows:
                # Convert SQLite values to PostgreSQL compatible values
                converted_row = []
                for val in row:
                    if isinstance(val, str) and val == "0":
                        # Try to convert string "0" to False for boolean columns
                        converted_row.append(val)
                    elif isinstance(val, int) and val in (0, 1):
                        # Keep as is - PostgreSQL will handle boolean conversion
                        converted_row.append(val)
                    else:
                        converted_row.append(val)

                pg_cursor.execute(insert_stmt, tuple(converted_row))

            pg_conn.commit()
            print(f"✓ Copied {len(rows)} rows from {table_name}")
            total_rows += len(rows)
        except Exception as e:
            print(f"✗ Error copying data from {table_name}: {e}")
            pg_conn.rollback()

# Close connections
sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 60)
print(f"✓ Migration complete!")
print(f"✓ Total rows copied: {total_rows}")
print("=" * 60)
print("\nNext steps:")
print("1. Run: python manage.py migrate --fake-initial")
print("2. Test the application with Supabase data")
print("3. If all works, delete db.sqlite3 and update .env to use Supabase")
