"""
Seed COMPLETA de estrutura curricular (todas as unidades/cursos).

Porta os dados de `seeds/sql/seed_supabase.sql` (gerado dos PPCs) para o schema
ATUAL (pós-refatoração multi-unidade), via ORM:

  - core_unidade                -> Unidade
  - courses_course (por unidade)-> Course (global, deduplicado) + CourseUnit(curso, unidade)
  - courses_curricularcomponent -> CurricularComponent
  - courses_curriculummatrix    -> CurriculumMatrix (curso global) + matriz.unidades.add(unidade)
  - courses_matrixcomponent     -> MatrixComponent

NÃO importa usuários nem professores (esses já são semeados à parte).

Idempotente: usa get_or_create por chaves naturais. Pode rodar várias vezes.

Uso:
    python seeds/seed_matrizes_completo.py
"""
import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

from django.db import transaction

from apps.core.models import Unidade
from apps.courses.models import (
    Course,
    CourseUnit,
    CurricularComponent,
    CurriculumMatrix,
    MatrixComponent,
)

SQL_PATH = Path(__file__).resolve().parent / "sql" / "seed_supabase.sql"


# ──────────────────────────────────────────────────────────────
# Parser de INSERT ... VALUES do dump SQL
# ──────────────────────────────────────────────────────────────
def _coerce(token: str):
    token = token.strip()
    if not token:
        return None
    if token[0] == "'":
        # string SQL: remove aspas externas e desfaz o escape '' -> '
        return token[1:-1].replace("''", "'")
    upper = token.upper()
    if upper == "NULL":
        return None
    if upper == "TRUE":
        return True
    if upper == "FALSE":
        return False
    if upper == "NOW()":
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token


def _split_row(inner: str):
    """Divide o conteúdo de uma linha '(a, b, c)' por vírgulas de topo, respeitando aspas."""
    fields, buf, in_quote, i = [], [], False, 0
    while i < len(inner):
        ch = inner[i]
        if ch == "'":
            if in_quote and i + 1 < len(inner) and inner[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_quote = not in_quote
            buf.append(ch)
        elif ch == "," and not in_quote:
            fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        fields.append("".join(buf))
    return [_coerce(f) for f in fields]


def _extract_rows(text: str, table: str):
    """Extrai as tuplas de valores do primeiro `INSERT INTO <table> ... VALUES ... ;`."""
    marker = f"INSERT INTO {table}"
    start = text.index(marker)
    values_at = text.index("VALUES", start) + len("VALUES")

    # Coleta até o ';' terminador, respeitando aspas.
    rows, depth, in_quote, buf, i = [], 0, False, [], values_at
    while i < len(text):
        ch = text[i]
        if ch == "'":
            if in_quote and i + 1 < len(text) and text[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_quote = not in_quote
            if depth > 0:
                buf.append(ch)
        elif not in_quote and ch == "(":
            depth += 1
            if depth == 1:
                buf = []
            else:
                buf.append(ch)
        elif not in_quote and ch == ")":
            depth -= 1
            if depth == 0:
                rows.append(_split_row("".join(buf)))
            else:
                buf.append(ch)
        elif not in_quote and ch == ";" and depth == 0:
            break
        else:
            if depth > 0:
                buf.append(ch)
        i += 1
    return rows


# ──────────────────────────────────────────────────────────────
# Carga
# ──────────────────────────────────────────────────────────────
@transaction.atomic
def run():
    if not SQL_PATH.exists():
        raise SystemExit(f"SQL não encontrado: {SQL_PATH}")
    text = SQL_PATH.read_text(encoding="utf-8")

    # 1) Unidades ------------------------------------------------
    unidade_by_old = {}
    for oid, nome, sigla, status in _extract_rows(text, "core_unidade"):
        # Dedup por NOME (único). A unidade pode já existir com outra sigla
        # (ex.: Paracambi já cadastrada como 'FAETERJ-PARACAMBI'); nesse caso reutiliza.
        u, _ = Unidade.objects.get_or_create(nome=nome, defaults={"sigla": sigla, "status": bool(status)})
        unidade_by_old[oid] = u
    print(f"Unidades: {len(unidade_by_old)}")

    # 2) Cursos (por unidade) -> Course global + CourseUnit ------
    # old course id -> (Course global, Unidade)
    course_by_old = {}
    for oid, nome, sigla, unidade_id in _extract_rows(text, "courses_course"):
        curso, _ = Course.objects.get_or_create(nome=nome, defaults={"sigla": sigla})
        unidade = unidade_by_old[unidade_id]
        CourseUnit.objects.get_or_create(curso=curso, unidade=unidade)
        course_by_old[oid] = (curso, unidade)
    print(f"Cursos globais: {Course.objects.count()} | CourseUnits: {CourseUnit.objects.count()}")

    # 3) Componentes curriculares --------------------------------
    comp_by_old = {}
    for row in _extract_rows(text, "courses_curricularcomponent"):
        oid, nome, sigla, codigo, ch_padrao, creditos, ementa = row
        comp, created = CurricularComponent.objects.get_or_create(
            nome=nome,
            defaults={
                "codigo": codigo or "",
                "carga_horaria_padrao": ch_padrao or 0,
                "creditos": creditos or 0,
                "ementa": ementa or "",
            },
        )
        if not created and codigo and not comp.codigo:
            comp.codigo = codigo
            comp.save(update_fields=["codigo"])
        comp_by_old[oid] = comp
    print(f"Componentes curriculares: {len(comp_by_old)}")

    # 4) Matrizes ------------------------------------------------
    matriz_by_old = {}
    for row in _extract_rows(text, "courses_curriculummatrix"):
        oid, curso_id, nome, is_vigente, is_rascunho, periodo_letivo, turno, _criada = row
        curso, unidade = course_by_old[curso_id]
        existente = CurriculumMatrix.objects.filter(
            curso=curso, periodo_letivo=periodo_letivo, turno=turno, unidades=unidade
        ).first()
        if existente:
            matriz = existente
        else:
            matriz = CurriculumMatrix.objects.create(
                curso=curso,
                nome=nome or "",
                is_vigente=bool(is_vigente),
                is_rascunho=bool(is_rascunho),
                periodo_letivo=periodo_letivo,
                turno=turno,
            )
            matriz.unidades.add(unidade)
        matriz_by_old[oid] = matriz
    print(f"Matrizes: {len(matriz_by_old)}")

    # 5) Componentes das matrizes --------------------------------
    criados = 0
    for row in _extract_rows(text, "courses_matrixcomponent"):
        (oid, matriz_id, comp_id, codigo, periodo, carga_horaria, creditos,
         _docente, compartilhado, _curso_comp, ch_semanal, distrib, status, obs) = row
        matriz = matriz_by_old.get(matriz_id)
        comp = comp_by_old.get(comp_id)
        if not matriz or not comp:
            continue
        _, created = MatrixComponent.objects.get_or_create(
            matriz=matriz,
            componente_curricular=comp,
            defaults={
                "codigo": codigo or "",
                "periodo": periodo or "",
                "carga_horaria": carga_horaria or 0,
                "creditos": creditos or 0,
                "compartilhado": bool(compartilhado),
                "distribuicao_semanal": distrib or "",
                "status": status or "SEM_PROFESSOR",
                "observacoes": obs or "",
            },
        )
        criados += int(created)
    print(f"Vínculos matriz-componente (novos): {criados} | total: {MatrixComponent.objects.count()}")

    print("\nSeed de estrutura curricular completa finalizada!")


if __name__ == "__main__":
    run()
