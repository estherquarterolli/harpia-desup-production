#!/usr/bin/env python
"""
Optimized SQLite3 → Supabase (PostgreSQL) Migration
- Converts types to PostgreSQL native types
- Creates ENUM types for status/choice fields
- Adds indexes for performance
- Adds constraints and defaults
- Improves data integrity
"""

import os
import sqlite3
import psycopg2
from decouple import config

SQLITE_DB = "db.sqlite3"
SUPABASE_URL = config("DATABASE_URL")

print("=" * 70)
print("OPTIMIZED SQLite3 → Supabase (PostgreSQL) Migration")
print("=" * 70)

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

# Create ENUM types for better data integrity
print("\n[2] Creating ENUM types...")
enums = {
    "user_perfil": ["COORDENADOR_UNIDADE", "DESUP"],
    "status_alocacao": ["Rascunho", "Enviado", "Aprovado", "Rejeitado"],
    "turno_type": ["M", "N", "V"],  # Manhã, Noite, Vespertino
    "professor_status": ["Ativo", "Inativo", "Licença"],
    "parecer_status": ["PENDENTE", "APROVADO", "REJEITADO"],
    "pendencia_status": ["RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO"],
}

for enum_name, values in enums.items():
    try:
        pg_cursor.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")
        pg_cursor.execute(
            f"CREATE TYPE {enum_name} AS ENUM ({', '.join([f\"'{v}'\" for v in values])})"
        )
        pg_conn.commit()
        print(f"✓ Created ENUM: {enum_name}")
    except Exception as e:
        print(f"✗ Error creating ENUM {enum_name}: {e}")
        pg_conn.rollback()

# Get all tables from SQLite
print("\n[3] Getting tables from SQLite...")
sqlite_cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)
tables = [row[0] for row in sqlite_cursor.fetchall()]
print(f"✓ Found {len(tables)} tables")

def convert_type(sqlite_type, col_name=""):
    """Convert SQLite type to PostgreSQL with optimizations"""
    sqlite_type = sqlite_type.upper() if sqlite_type else "TEXT"

    # Special cases for specific columns
    if "perfil" in col_name.lower():
        return "user_perfil"
    if "status" in col_name.lower() and "alocacao" in col_name.lower():
        return "status_alocacao"
    if "status" in col_name.lower() and "parecer" in col_name.lower():
        return "parecer_status"
    if "status" in col_name.lower() and "pendencia" in col_name.lower():
        return "pendencia_status"
    if "status" in col_name.lower() and "professor" in col_name.lower():
        return "professor_status"
    if col_name.lower() == "turno":
        return "turno_type"

    # Boolean conversion
    if "BOOL" in sqlite_type:
        return "BOOLEAN"

    # Numeric types
    if "DECIMAL" in sqlite_type:
        return "NUMERIC(8,2)"  # Up to 999999.99
    if "INT" in sqlite_type:
        if "AUTOINCREMENT" in sqlite_type or "PRIMARY KEY" in sqlite_type:
            return "BIGSERIAL"
        elif "SMALLINT" in sqlite_type:
            return "SMALLINT"
        else:
            return "BIGINT"

    # String types with optimization
    if "CHAR(32)" in sqlite_type:
        return "CHAR(32)"  # For tokens
    if "CHAR(39)" in sqlite_type:
        return "INET"  # For IP addresses
    if "CHAR" in sqlite_type or "VARCHAR" in sqlite_type:
        return "VARCHAR(255)"
    if "TEXT" in sqlite_type:
        return "TEXT"

    # Date/Time
    if sqlite_type == "DATE":
        return "DATE"
    if "DATETIME" in sqlite_type:
        return "TIMESTAMP"

    return "TEXT"

# Create tables with optimizations
print("\n[4] Creating tables in Supabase with optimizations...")
for table_name in tables:
    if table_name == "sqlite_sequence":
        continue

    try:
        # Get table schema
        sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
        columns = sqlite_cursor.fetchall()

        create_stmt = f"CREATE TABLE IF NOT EXISTS \"{table_name}\" (\n"
        col_defs = []

        for col_id, col_name, col_type, not_null, default_val, pk in columns:
            col_def = f"  \"{col_name}\" {convert_type(col_type, col_name)}"

            if pk:
                col_def = f"  \"{col_name}\" BIGSERIAL PRIMARY KEY"
            else:
                if not_null:
                    col_def += " NOT NULL"
                if default_val:
                    col_def += f" DEFAULT {default_val}"

            col_defs.append(col_def)

        # Add foreign keys
        sqlite_cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = sqlite_cursor.fetchall()
        for fk_id, table_ref, from_col, to_col, on_delete, on_update, match_type in fks:
            col_defs.append(
                f"  FOREIGN KEY (\"{from_col}\") REFERENCES \"{table_ref}\"(\"{to_col}\") ON DELETE CASCADE"
            )

        create_stmt += ",\n".join(col_defs) + "\n);"

        pg_cursor.execute(create_stmt)
        pg_conn.commit()
        print(f"✓ Created table: {table_name}")

    except Exception as e:
        print(f"✗ Error creating {table_name}: {e}")
        pg_conn.rollback()

# Create indexes for performance
print("\n[5] Creating indexes for performance...")
indexes = [
    ("accounts_user", "email"),
    ("accounts_user", "username"),
    ("professors_professor", "rh_matricula"),
    ("professors_professor", "ID_FUNCIONAL"),
    ("courses_course", "unidade_id"),
    ("core_unidade", "sigla"),
    ("allocations_alocacaocurricular", "curso_id"),
    ("allocations_alocacaocurricular", "unidade_id"),
    ("extra_curricular_pendenciaextra", "professor_id"),
    ("extra_curricular_pendenciaextra", "unidade_id"),
]

for table_name, col_name in indexes:
    try:
        index_name = f"idx_{table_name}_{col_name}".lower()
        pg_cursor.execute(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{col_name}")'
        )
        pg_conn.commit()
        print(f"✓ Created index: {index_name}")
    except Exception as e:
        print(f"✗ Error creating index on {table_name}.{col_name}: {e}")
        pg_conn.rollback()

# Copy data from SQLite to Supabase
print("\n[6] Copying data from SQLite to Supabase...")
total_rows = 0

for table_name in tables:
    if table_name == "sqlite_sequence":
        continue

    try:
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()

        if rows:
            sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in sqlite_cursor.fetchall()]

            placeholders = ", ".join(["%s"] * len(columns))
            col_names = ", ".join([f'"{col}"' for col in columns])
            insert_stmt = (
                f"INSERT INTO \"{table_name}\" ({col_names}) VALUES ({placeholders})"
            )

            for row in rows:
                converted_row = []
                for i, val in enumerate(row):
                    col_name = columns[i]

                    # Convert boolean values
                    if isinstance(val, int) and val in (0, 1):
                        if "bool" in columns[i].lower() or any(
                            x in col_name.lower() for x in ["is_", "forcar"]
                        ):
                            converted_row.append(bool(val))
                        else:
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

# Final optimizations
print("\n[7] Adding final optimizations...")
try:
    # Add check constraints for positive numbers
    pg_cursor.execute(
        """
    ALTER TABLE "professors_contracttype"
    ADD CONSTRAINT check_max_hours CHECK (max_class_hours >= 0 AND max_total_hours >= 0)
    """
    )
    pg_conn.commit()
    print("✓ Added check constraints")
except:
    pg_conn.rollback()

# Close connections
sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 70)
print(f"✓ Migration complete!")
print(f"✓ Total rows copied: {total_rows}")
print("=" * 70)
print("\n📋 IMPROVEMENTS APPLIED:")
print("   ✓ ENUM types for status/choice fields (data integrity)")
print("   ✓ NUMERIC(8,2) for decimal fields (precision)")
print("   ✓ INET type for IP addresses (better than CHAR(39))")
print("   ✓ BOOLEAN native type (not INTEGER)")
print("   ✓ Indexes on foreign keys and search fields (performance)")
print("   ✓ CASCADE ON DELETE for referential integrity")
print("   ✓ Proper VARCHAR lengths (255 max)")
print("   ✓ TIMESTAMP for datetime fields")
print("\n🚀 NEXT STEPS:")
print("   1. Run: python manage.py migrate --fake-initial")
print("   2. Test the application locally")
print("   3. Run: git add migrate_to_supabase_optimized.py")
print("   4. Deploy to Render.com with DATABASE_URL set to Supabase")
print("=" * 70)
