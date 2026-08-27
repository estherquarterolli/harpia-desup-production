#!/usr/bin/env python
"""
Generate SQL INSERT statements from CSV files
"""

import csv
from pathlib import Path

CSV_DIR = Path(__file__).parent / "docs" / "sensivel"

# Data containers
units = {}  # {unit_name}
courses = {}  # {(unit_name, course_name)}
components = {}  # {component_name: periodo}
course_components = {}  # {(unit_name, course_name, component_name): periodo}

print("Reading CSVs...")
csv_files = sorted(CSV_DIR.glob("*.CSV"))

for csv_file in csv_files:
    print(f"  {csv_file.name}")
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, fieldnames=['Faculdade', 'Curso', 'Período', 'Código', 'Disciplina'], delimiter=';')
        next(reader)  # Skip header
        for row in reader:
            faculdade = row['Faculdade'].strip()
            curso = row['Curso'].strip()
            periodo = int(row['Período'].strip()) if row['Período'].strip() else 1
            disciplina = row['Disciplina'].strip()

            if faculdade:
                units[faculdade] = None
            if curso and faculdade:
                courses[(faculdade, curso)] = None
            if disciplina:
                components[disciplina] = periodo
                if (faculdade, curso):
                    course_components[(faculdade, curso, disciplina)] = periodo

print(f"\nExtracted: {len(units)} units, {len(courses)} courses, {len(components)} components\n")

# Generate SQL
sql_lines = []
sql_lines.append("-- ============================================================================")
sql_lines.append("-- AUTO-GENERATED SQL FROM CSVs")
sql_lines.append("-- Copy and paste sections into Supabase SQL Editor")
sql_lines.append("-- ============================================================================\n")

# Step 1: Units
sql_lines.append("-- STEP 1: INSERT UNITS")
sql_lines.append("-- ============================================================================\n")
sql_lines.append('INSERT INTO "core_unidade" ("nome", "sigla") VALUES')

for i, unit_name in enumerate(sorted(units.keys())):
    parts = unit_name.split()
    if 'Santo' in unit_name or 'Itaboana' in unit_name:
        sigla = 'FAETERJ-SAP'
    elif 'ISEPAM' in unit_name:
        sigla = 'ISEPAM'
    elif 'ISERJ' in unit_name:
        sigla = 'ISERJ'
    elif len(parts) >= 2:
        sigla = f"{parts[0]}-{parts[-1][:3].upper()}"
    else:
        sigla = unit_name[:10].upper()

    comma = "," if i < len(units) - 1 else ""
    unit_escaped = unit_name.replace("'", "''")
    sql_lines.append(f"('{unit_escaped}', '{sigla}'){comma}")

sql_lines.append('ON CONFLICT ("nome") DO NOTHING;\n')

# Step 2: Courses
sql_lines.append("-- STEP 2: INSERT COURSES")
sql_lines.append("-- ============================================================================\n")
sql_lines.append('INSERT INTO "courses_course" ("nome", "sigla", "unidade_id") VALUES')

course_list = sorted(courses.keys())
for i, (unit_name, course_name) in enumerate(course_list):
    # Generate sigla from course name
    words = course_name.split()
    if len(words) >= 2:
        sigla = ''.join([w[0].upper() for w in words[:3]])  # First 3 letters of first 3 words
    else:
        sigla = course_name[:3].upper()

    comma = "," if i < len(course_list) - 1 else ""
    course_escaped = course_name.replace("'", "''")
    unit_escaped = unit_name.replace("'", "''")
    sql_lines.append(f"('{course_escaped}', '{sigla}', (SELECT id FROM \"core_unidade\" WHERE \"nome\" = '{unit_escaped}' LIMIT 1)){comma}")

sql_lines.append('ON CONFLICT ("nome", "unidade_id") DO NOTHING;\n')

# Step 3: Components
sql_lines.append("-- STEP 3: INSERT COMPONENTS")
sql_lines.append("-- ============================================================================\n")
sql_lines.append('INSERT INTO "courses_curricularcomponent" ("nome") VALUES')

component_list = sorted(components.keys())
for i, component_name in enumerate(component_list):
    comma = "," if i < len(component_list) - 1 else ""
    component_escaped = component_name.replace("'", "''")
    sql_lines.append(f"('{component_escaped}'){comma}")

sql_lines.append('ON CONFLICT ("nome") DO NOTHING;\n')

# Step 4: Mappings
sql_lines.append("-- STEP 4: MAP COMPONENTS TO COURSES")
sql_lines.append("-- ============================================================================\n")
sql_lines.append('INSERT INTO "curso_componente_assoc" ("curso_id", "componente_id", "periodo", "obrigatorio") VALUES')

mapping_list = sorted(course_components.items())
for i, ((unit_name, course_name, component_name), periodo) in enumerate(mapping_list):
    comma = "," if i < len(mapping_list) - 1 else ""
    course_escaped = course_name.replace("'", "''")
    unit_escaped = unit_name.replace("'", "''")
    component_escaped = component_name.replace("'", "''")
    sql_lines.append(f"((SELECT id FROM \"courses_course\" WHERE \"nome\" = '{course_escaped}' AND \"unidade_id\" = (SELECT id FROM \"core_unidade\" WHERE \"nome\" = '{unit_escaped}' LIMIT 1) LIMIT 1), (SELECT id FROM \"courses_curricularcomponent\" WHERE \"nome\" = '{component_escaped}' LIMIT 1), {periodo}, TRUE){comma}")

sql_lines.append('ON CONFLICT ("curso_id", "componente_id") DO NOTHING;\n')

# Verification
sql_lines.append("-- VERIFICATION")
sql_lines.append("-- ============================================================================\n")
sql_lines.append('SELECT COUNT(*) as units_count FROM "core_unidade";')
sql_lines.append('SELECT COUNT(*) as courses_count FROM "courses_course";')
sql_lines.append('SELECT COUNT(*) as components_count FROM "courses_curricularcomponent";')
sql_lines.append('SELECT COUNT(*) as mappings_count FROM "curso_componente_assoc";\n')

sql = '\n'.join(sql_lines)

# Save SQL
output_path = Path(__file__).parent / "project_root" / "IMPORT_CSV_FINAL.sql"
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(sql)

print(f"[OK] SQL generated: {output_path}")
print(f"[OK] Ready to copy/paste into Supabase SQL Editor")
print(f"\nStatistics:")
print(f"  Units: {len(units)}")
print(f"  Courses: {len(courses)}")
print(f"  Components: {len(components)}")
print(f"  Mappings: {len(course_components)}")
