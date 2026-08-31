#!/usr/bin/env python
"""Export SQLite3 schema to SQL file."""

import sqlite3
import os

db_path = "db.sqlite3"
output_path = "schema_sqlite.sql"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

with open(output_path, 'w', encoding='utf-8') as f:
    f.write("-- SQLite3 Database Schema Export\n")
    f.write("-- Generated from db.sqlite3\n\n")

    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        schema = cursor.fetchone()
        if schema and schema[0]:
            f.write(f"-- Table: {table_name}\n")
            f.write(schema[0])
            f.write(";\n\n")

    # Export data as INSERT statements (optional)
    f.write("\n-- Data Export\n")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if rows:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            col_names = ", ".join(columns)

            for row in rows:
                values = ", ".join([f"'{str(val).replace(chr(39), chr(39)*2)}'" if val is not None else 'NULL' for val in row])
                f.write(f"INSERT INTO {table_name} ({col_names}) VALUES ({values});\n")

conn.close()

print(f"Schema exported to {output_path}")
print(f"Tables: {len(tables)}")
for table in tables:
    print(f"  - {table[0]}")
