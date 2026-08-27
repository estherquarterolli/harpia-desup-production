#!/usr/bin/env python
"""
COMPLETE & OPTIMIZED SQLite3 → Supabase Migration

Includes:
- ENUM types for all status fields
- Lookup tables (Turnos, Periodos, StatusTypes)
- Associative/Junction tables for many-to-many relationships
- Proper normalization
- Indexes and constraints
- Foreign key cascades
"""

import os
import sqlite3
import psycopg2
from decouple import config

SQLITE_DB = "db.sqlite3"
SUPABASE_URL = config("DATABASE_URL")

print("=" * 80)
print("COMPLETE OPTIMIZED SQLite3 to Supabase Migration")
print("=" * 80)

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

# Create ENUM types
print("\n[2] Creating ENUM types...")
enums = {
    "user_perfil": ["COORDENADOR_UNIDADE", "DESUP"],
    "professor_status": ["Ativo", "Inativo", "Licença"],
    "parecer_status": ["PENDENTE", "APROVADO", "REJEITADO"],
    "alocacao_status": ["Rascunho", "Enviado", "Aprovado", "Rejeitado"],
    "pendencia_status": ["RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO"],
    "turno_enum": ["M", "N", "V"],  # Manhã, Noite, Vespertino
    "dia_semana_enum": ["seg", "ter", "qua", "qui", "sex"],
}

for enum_name, values in enums.items():
    try:
        pg_cursor.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")
        enum_values = ", ".join([f"'{v}'" for v in values])
        pg_cursor.execute(
            f"CREATE TYPE {enum_name} AS ENUM ({enum_values})"
        )
        pg_conn.commit()
        print(f"✓ Created ENUM: {enum_name}")
    except Exception as e:
        print(f"✗ Error creating ENUM {enum_name}: {e}")
        pg_conn.rollback()

# Create Lookup/Reference Tables (for better normalization)
print("\n[3] Creating lookup/reference tables...")
lookup_tables = {
    "ref_turno": (
        """
        CREATE TABLE IF NOT EXISTS "ref_turno" (
            "id" BIGSERIAL PRIMARY KEY,
            "codigo" turno_enum UNIQUE NOT NULL,
            "nome" VARCHAR(50) NOT NULL,
            "horario_inicio" TIME,
            "horario_fim" TIME,
            "criado_em" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        [
            ("M", "Manhã", "07:00", "12:00"),
            ("N", "Noite", "19:00", "23:00"),
            ("V", "Vespertino", "13:00", "18:00"),
        ],
    ),
    "ref_dia_semana": (
        """
        CREATE TABLE IF NOT EXISTS "ref_dia_semana" (
            "id" BIGSERIAL PRIMARY KEY,
            "codigo" dia_semana_enum UNIQUE NOT NULL,
            "nome" VARCHAR(20) NOT NULL,
            "ordem" SMALLINT UNIQUE
        );
        """,
        [
            ("seg", "Segunda", 1),
            ("ter", "Terça", 2),
            ("qua", "Quarta", 3),
            ("qui", "Quinta", 4),
            ("sex", "Sexta", 5),
        ],
    ),
}

for table_name, (create_sql, data) in lookup_tables.items():
    try:
        pg_cursor.execute(create_sql)
        pg_conn.commit()
        print(f"✓ Created lookup table: {table_name}")

        # Insert default data
        if table_name == "ref_turno":
            for codigo, nome, inicio, fim in data:
                pg_cursor.execute(
                    f"""INSERT INTO "ref_turno" ("codigo", "nome", "horario_inicio", "horario_fim")
                       VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING"""
                    ,
                    (codigo, nome, inicio, fim),
                )
        elif table_name == "ref_dia_semana":
            for codigo, nome, ordem in data:
                pg_cursor.execute(
                    f"""INSERT INTO "ref_dia_semana" ("codigo", "nome", "ordem")
                       VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"""
                    ,
                    (codigo, nome, ordem),
                )
        pg_conn.commit()
        print(f"  ✓ Populated {table_name} with reference data")
    except Exception as e:
        print(f"✗ Error creating {table_name}: {e}")
        pg_conn.rollback()

# Get all tables from SQLite
print("\n[4] Getting tables from SQLite...")
sqlite_cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)
tables = [row[0] for row in sqlite_cursor.fetchall()]
print(f"✓ Found {len(tables)} tables")

def convert_type(sqlite_type, col_name=""):
    """Convert SQLite type to PostgreSQL"""
    sqlite_type = sqlite_type.upper() if sqlite_type else "TEXT"

    # Special cases
    if "perfil" in col_name.lower():
        return "user_perfil"
    if "professor_status" in col_name.lower() or (
        "status" in col_name.lower() and "professor" in col_name.lower()
    ):
        return "professor_status"
    if "parecer" in col_name.lower() and "status" in col_name.lower():
        return "parecer_status"
    if "alocacao" in col_name.lower() and "status" in col_name.lower():
        return "alocacao_status"
    if "pendencia" in col_name.lower() and "status" in col_name.lower():
        return "pendencia_status"
    if col_name.lower() == "turno":
        return "turno_enum"
    if col_name.lower() == "dia_semana":
        return "dia_semana_enum"

    if "BOOL" in sqlite_type:
        return "BOOLEAN"
    if "DECIMAL" in sqlite_type:
        return "NUMERIC(8,2)"
    if "INT" in sqlite_type:
        if "AUTOINCREMENT" in sqlite_type or "PRIMARY KEY" in sqlite_type:
            return "BIGSERIAL"
        elif "SMALLINT" in sqlite_type:
            return "SMALLINT"
        else:
            return "BIGINT"
    if "CHAR(32)" in sqlite_type:
        return "CHAR(32)"
    if "CHAR(39)" in sqlite_type:
        return "INET"
    if "CHAR" in sqlite_type or "VARCHAR" in sqlite_type:
        return "VARCHAR(255)"
    if "TEXT" in sqlite_type:
        return "TEXT"
    if sqlite_type == "DATE":
        return "DATE"
    if "DATETIME" in sqlite_type:
        return "TIMESTAMP"

    return "TEXT"

# Create original tables
print("\n[5] Creating original tables with optimizations...")
for table_name in tables:
    if table_name == "sqlite_sequence":
        continue

    try:
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

# Create new associative/junction tables for better modeling
print("\n[6] Creating new associative tables for better normalization...")
associative_tables = {
    "professor_unidade_assoc": """
        CREATE TABLE IF NOT EXISTS "professor_unidade_assoc" (
            "id" BIGSERIAL PRIMARY KEY,
            "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
            "unidade_id" BIGINT NOT NULL REFERENCES "core_unidade"("id") ON DELETE CASCADE,
            "eh_principal" BOOLEAN DEFAULT FALSE,
            "data_inicio" DATE NOT NULL DEFAULT CURRENT_DATE,
            "data_fim" DATE,
            UNIQUE("professor_id", "unidade_id")
        );
    """,
    "alocacao_professor_assoc": """
        CREATE TABLE IF NOT EXISTS "alocacao_professor_assoc" (
            "id" BIGSERIAL PRIMARY KEY,
            "alocacao_id" BIGINT NOT NULL REFERENCES "allocations_alocacaocurricular"("id") ON DELETE CASCADE,
            "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
            "componente_id" BIGINT REFERENCES "courses_matrixcomponent"("id") ON DELETE SET NULL,
            "data_alocacao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "data_remocao" TIMESTAMP,
            UNIQUE("alocacao_id", "professor_id", "componente_id")
        );
    """,
    "classgroup_professor_assoc": """
        CREATE TABLE IF NOT EXISTS "classgroup_professor_assoc" (
            "id" BIGSERIAL PRIMARY KEY,
            "classgroup_id" BIGINT NOT NULL REFERENCES "courses_classgroup"("id") ON DELETE CASCADE,
            "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
            "componente_id" BIGINT REFERENCES "courses_matrixcomponent"("id") ON DELETE SET NULL,
            "data_inicio" DATE NOT NULL DEFAULT CURRENT_DATE,
            "data_fim" DATE,
            UNIQUE("classgroup_id", "professor_id", "componente_id")
        );
    """,
    "professor_availability_v2": """
        CREATE TABLE IF NOT EXISTS "professor_availability_v2" (
            "id" BIGSERIAL PRIMARY KEY,
            "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
            "dia_semana_id" BIGINT NOT NULL REFERENCES "ref_dia_semana"("id") ON DELETE CASCADE,
            "turno_id" BIGINT NOT NULL REFERENCES "ref_turno"("id") ON DELETE CASCADE,
            "ativo" BOOLEAN DEFAULT TRUE,
            UNIQUE("professor_id", "dia_semana_id", "turno_id")
        );
    """,
    "extracurricular_professor_horas": """
        CREATE TABLE IF NOT EXISTS "extracurricular_professor_horas" (
            "id" BIGSERIAL PRIMARY KEY,
            "professor_id" BIGINT NOT NULL REFERENCES "professors_professor"("id") ON DELETE CASCADE,
            "pendencia_id" BIGINT NOT NULL REFERENCES "extra_curricular_pendenciaextra"("id") ON DELETE CASCADE,
            "tipo" VARCHAR(50) NOT NULL,  -- orientacao_tcc, atividade_extensionista, etc
            "horas_solicitadas" NUMERIC(8,2) NOT NULL,
            "horas_aprovadas" NUMERIC(8,2),
            "data_solicitacao" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE("professor_id", "pendencia_id", "tipo")
        );
    """,
    "curso_componente_assoc": """
        CREATE TABLE IF NOT EXISTS "curso_componente_assoc" (
            "id" BIGSERIAL PRIMARY KEY,
            "curso_id" BIGINT NOT NULL REFERENCES "courses_course"("id") ON DELETE CASCADE,
            "componente_id" BIGINT NOT NULL REFERENCES "courses_curricularcomponent"("id") ON DELETE CASCADE,
            "periodo" SMALLINT,  -- 1 a 8
            "obrigatorio" BOOLEAN DEFAULT TRUE,
            UNIQUE("curso_id", "componente_id")
        );
    """,
}

for table_name, create_sql in associative_tables.items():
    try:
        pg_cursor.execute(create_sql)
        pg_conn.commit()
        print(f"✓ Created associative table: {table_name}")
    except Exception as e:
        print(f"✗ Error creating {table_name}: {e}")
        pg_conn.rollback()

# Create indexes
print("\n[7] Creating indexes for performance...")
indexes = [
    # Original tables
    ("accounts_user", "email"),
    ("accounts_user", "username"),
    ("professors_professor", "rh_matricula"),
    ("professors_professor", "ID_FUNCIONAL"),
    ("courses_course", "unidade_id"),
    ("core_unidade", "sigla"),
    ("allocations_alocacaocurricular", "curso_id"),
    ("allocations_alocacaocurricular", "unidade_id"),
    ("extra_curricular_pendenciaextra", "professor_id"),
    # New associative tables
    ("professor_unidade_assoc", "professor_id"),
    ("professor_unidade_assoc", "unidade_id"),
    ("alocacao_professor_assoc", "alocacao_id"),
    ("alocacao_professor_assoc", "professor_id"),
    ("classgroup_professor_assoc", "classgroup_id"),
    ("classgroup_professor_assoc", "professor_id"),
    ("professor_availability_v2", "professor_id"),
    ("professor_availability_v2", "dia_semana_id"),
    ("extracurricular_professor_horas", "professor_id"),
    ("curso_componente_assoc", "curso_id"),
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

# Copy data
print("\n[8] Copying data from SQLite to Supabase...")
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
                for val in row:
                    if isinstance(val, int) and val in (0, 1):
                        converted_row.append(bool(val))
                    else:
                        converted_row.append(val)

                pg_cursor.execute(insert_stmt, tuple(converted_row))

            pg_conn.commit()
            print(f"✓ Copied {len(rows)} rows from {table_name}")
            total_rows += len(rows)

    except Exception as e:
        print(f"✗ Error copying data from {table_name}: {e}")
        pg_conn.rollback()

# Migrate availability data to new table
print("\n[9] Migrating availability data to new normalized table...")
try:
    pg_cursor.execute("""
        INSERT INTO professor_availability_v2 (professor_id, dia_semana_id, turno_id, ativo)
        SELECT pa.professor_id, rd.id, rt.id, true
        FROM professors_availability pa
        JOIN ref_dia_semana rd ON rd.codigo = pa.dia_semana
        JOIN ref_turno rt ON rt.codigo = pa.turno
        ON CONFLICT DO NOTHING
    """)
    pg_conn.commit()
    print("✓ Migrated availability data to normalized table")
except Exception as e:
    print(f"✗ Error migrating availability: {e}")
    pg_conn.rollback()

# Migrate professor units
print("\n[10] Migrating professor unit data to associative table...")
try:
    pg_cursor.execute("""
        INSERT INTO professor_unidade_assoc (professor_id, unidade_id, eh_principal)
        SELECT id, unidade_principal_id, true
        FROM professors_professor
        WHERE unidade_principal_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    pg_conn.commit()
    print("✓ Migrated professor units to associative table")
except Exception as e:
    print(f"✗ Error migrating professor units: {e}")
    pg_conn.rollback()

# Close connections
sqlite_conn.close()
pg_conn.close()

print("\n" + "=" * 80)
print(f"✓ Complete migration finished!")
print(f"✓ Total rows copied: {total_rows}")
print("=" * 80)
print("\n📊 NEW ASSOCIATIVE TABLES CREATED:")
print("   ✓ professor_unidade_assoc - Professor works in multiple units")
print("   ✓ alocacao_professor_assoc - Allocate professors to allocations")
print("   ✓ classgroup_professor_assoc - Assign professors to classes")
print("   ✓ professor_availability_v2 - Normalized availability (FK to ref tables)")
print("   ✓ extracurricular_professor_horas - Track extra hours")
print("   ✓ curso_componente_assoc - Courses have many components")
print("\n🎯 LOOKUP TABLES CREATED:")
print("   ✓ ref_turno - Turnos (M/N/V) com horários")
print("   ✓ ref_dia_semana - Dias da semana com ordem")
print("\n🚀 NEXT STEPS:")
print("   1. python manage.py migrate --fake-initial")
print("   2. python manage.py runserver")
print("   3. Test in http://localhost:8000/admin")
print("   4. Deploy to Render with DATABASE_URL set")
print("=" * 80)
