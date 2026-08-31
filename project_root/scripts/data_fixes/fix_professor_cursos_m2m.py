r"""
fix_professor_cursos_m2m.py — Repara a tabela intermediária do M2M `Professor.cursos`
quando o banco está defasado (coluna `courseunit_id` em vez de `course_id`).

Contexto: bancos criados antes da troca do alvo do M2M `CourseUnit -> Course` têm a
coluna física `courseunit_id` (FK -> courses_courseunit), enquanto o código/migração atual
espera `course_id` (FK -> courses_course). Isso causa HTTP 500 em `/professores/`:
    psycopg2.errors.UndefinedColumn: coluna professors_professor_cursos.course_id não existe
Ver: docs/relatorios/relatorio_correcao_professores_m2m_cursos.md

Este script é IDEMPOTENTE e SEGURO:
  - Por padrão roda em DRY-RUN (só diagnostica, não altera nada).
  - Se já estiver correto (course_id), não faz nada.
  - Se estiver defasado e a tabela estiver VAZIA, o reparo é trivial (rename + FK).
  - Se estiver defasado e TIVER dados, exige a flag --migrate-data (mapeia
    courseunit_id -> courses_courseunit.course_id, deduplica e recria a FK). Sem essa
    flag, ele apenas mostra um preview e aborta, para você decidir.

Uso (DEV local — settings de desenvolvimento é o default):
    ..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py            # dry-run (diagnóstico)
    ..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply    # aplica (só se vazio)

Uso (PRODUÇÃO / Supabase — aponte o settings e o DATABASE_URL antes):
    set DJANGO_SETTINGS_MODULE=config.settings.production
    ..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py            # dry-run primeiro!
    ..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply    # reparo se vazio
    ..\.venv\Scripts\python.exe fix_professor_cursos_m2m.py --apply --migrate-data  # se houver dados
"""
import os
import sys
import argparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import django  # noqa: E402
django.setup()

# Console Windows pode estar em cp1252; força UTF-8 para não quebrar em acentos/símbolos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from django.db import connection, transaction  # noqa: E402

TABLE = "professors_professor_cursos"
NEW_FK_NAME = "professors_professor_cursos_course_id_fk_courses_course"
NEW_UNIQUE_NAME = "professors_professor_cursos_professor_id_course_id_uniq"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de introspecção (read-only)
# ─────────────────────────────────────────────────────────────────────────────
def get_columns(cur):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        [TABLE],
    )
    return {r[0] for r in cur.fetchall()}


def table_exists(cur):
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        [TABLE],
    )
    return cur.fetchone() is not None


def get_fk_name_for_column(cur, column):
    """Descobre dinamicamente o nome da FK que cobre `column` (o hash varia por ambiente)."""
    cur.execute(
        """
        SELECT tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = %s
          AND tc.constraint_type = 'FOREIGN KEY'
          AND kcu.column_name = %s
        """,
        [TABLE, column],
    )
    row = cur.fetchone()
    return row[0] if row else None


def row_count(cur):
    cur.execute(f'SELECT COUNT(*) FROM "{TABLE}"')
    return cur.fetchone()[0]


def db_label():
    d = connection.settings_dict
    return f"{d.get('NAME')} @ {d.get('HOST') or 'local'}"


# ─────────────────────────────────────────────────────────────────────────────
# Diagnóstico
# ─────────────────────────────────────────────────────────────────────────────
def diagnose(cur):
    """Retorna o estado: 'ok', 'stale', 'ambiguous', 'missing'."""
    if not table_exists(cur):
        return "missing", None
    cols = get_columns(cur)
    has_course = "course_id" in cols
    has_courseunit = "courseunit_id" in cols
    n = row_count(cur)
    if has_course and not has_courseunit:
        return "ok", n
    if has_courseunit and not has_course:
        return "stale", n
    if has_course and has_courseunit:
        return "ambiguous", n
    return "missing", n


# ─────────────────────────────────────────────────────────────────────────────
# Preview do mapeamento de dados (quando a tabela não está vazia)
# ─────────────────────────────────────────────────────────────────────────────
def preview_data_mapping(cur):
    # linhas cujo courseunit_id não existe em courses_courseunit (órfãs)
    cur.execute(
        f"""
        SELECT COUNT(*) FROM "{TABLE}" ppc
        LEFT JOIN courses_courseunit cu ON ppc.courseunit_id = cu.id
        WHERE cu.id IS NULL
        """
    )
    orfas = cur.fetchone()[0]
    # linhas cujo courseunit existe mas o course_id do courseunit é nulo
    cur.execute(
        f"""
        SELECT COUNT(*) FROM "{TABLE}" ppc
        JOIN courses_courseunit cu ON ppc.courseunit_id = cu.id
        WHERE cu.course_id IS NULL
        """
    )
    sem_course = cur.fetchone()[0]
    # pares (professor, course) distintos que resultariam do mapeamento
    cur.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT ppc.professor_id, cu.course_id
            FROM "{TABLE}" ppc
            JOIN courses_courseunit cu ON ppc.courseunit_id = cu.id
            WHERE cu.course_id IS NOT NULL
        ) x
        """
    )
    pares_distintos = cur.fetchone()[0]
    return orfas, sem_course, pares_distintos


# ─────────────────────────────────────────────────────────────────────────────
# Reparo — tabela VAZIA (rename simples)
# ─────────────────────────────────────────────────────────────────────────────
def repair_empty(cur):
    fk = get_fk_name_for_column(cur, "courseunit_id")
    if fk:
        cur.execute(f'ALTER TABLE "{TABLE}" DROP CONSTRAINT "{fk}"')
        print(f"    - FK antiga removida: {fk}")
    cur.execute(f'ALTER TABLE "{TABLE}" RENAME COLUMN courseunit_id TO course_id')
    print("    - Coluna renomeada: courseunit_id -> course_id")
    cur.execute(
        f'''ALTER TABLE "{TABLE}"
            ADD CONSTRAINT "{NEW_FK_NAME}"
            FOREIGN KEY (course_id) REFERENCES courses_course(id)
            DEFERRABLE INITIALLY DEFERRED'''
    )
    print(f"    - FK recriada: {NEW_FK_NAME} (course_id -> courses_course)")


# ─────────────────────────────────────────────────────────────────────────────
# Reparo — tabela COM dados (mapeia, deduplica, recria)
# ─────────────────────────────────────────────────────────────────────────────
def repair_with_data(cur):
    orfas, sem_course, pares = preview_data_mapping(cur)
    if orfas or sem_course:
        raise RuntimeError(
            f"Não é seguro migrar automaticamente: {orfas} linha(s) órfã(s) "
            f"(courseunit inexistente) e {sem_course} linha(s) cujo courseunit não tem "
            f"course_id. Trate esses dados manualmente antes de aplicar."
        )
    # 1) adiciona course_id temporário (nullable)
    cur.execute(f'ALTER TABLE "{TABLE}" ADD COLUMN course_id bigint')
    # 2) popula a partir do mapeamento courseunit -> course
    cur.execute(
        f"""
        UPDATE "{TABLE}" ppc
        SET course_id = cu.course_id
        FROM courses_courseunit cu
        WHERE ppc.courseunit_id = cu.id
        """
    )
    # 3) deduplica pares (professor_id, course_id) — múltiplos courseunit podem virar o mesmo course
    cur.execute(
        f"""
        DELETE FROM "{TABLE}" a
        USING "{TABLE}" b
        WHERE a.ctid < b.ctid
          AND a.professor_id = b.professor_id
          AND a.course_id = b.course_id
        """
    )
    # 4) remove FK/coluna antiga (dropar a coluna leva junto índice/unique que a referenciavam)
    fk = get_fk_name_for_column(cur, "courseunit_id")
    if fk:
        cur.execute(f'ALTER TABLE "{TABLE}" DROP CONSTRAINT "{fk}"')
    cur.execute(f'ALTER TABLE "{TABLE}" DROP COLUMN courseunit_id')
    # 5) finaliza course_id: NOT NULL + FK + unique
    cur.execute(f'ALTER TABLE "{TABLE}" ALTER COLUMN course_id SET NOT NULL')
    cur.execute(
        f'''ALTER TABLE "{TABLE}"
            ADD CONSTRAINT "{NEW_FK_NAME}"
            FOREIGN KEY (course_id) REFERENCES courses_course(id)
            DEFERRABLE INITIALLY DEFERRED'''
    )
    cur.execute(
        f'''ALTER TABLE "{TABLE}"
            ADD CONSTRAINT "{NEW_UNIQUE_NAME}" UNIQUE (professor_id, course_id)'''
    )
    print(f"    - Dados mapeados para course_id; {pares} par(es) distinto(s) preservado(s)")
    print("    - Coluna courseunit_id removida; FK e UNIQUE recriadas sobre course_id")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Repara o M2M professors_professor_cursos.")
    parser.add_argument("--apply", action="store_true",
                        help="Aplica as alterações. Sem esta flag, apenas diagnostica (dry-run).")
    parser.add_argument("--migrate-data", action="store_true",
                        help="Permite migrar dados quando a tabela não estiver vazia.")
    parser.add_argument("--yes", action="store_true",
                        help="Pula a confirmação interativa em bancos remotos (para automação).")
    args = parser.parse_args()

    print("=" * 72)
    print("  FIX PROFESSOR.CURSOS M2M - Harpia (HARPIA-DESUP)")
    print("=" * 72)
    print(f"  Banco: {db_label()}")
    print(f"  Modo:  {'APPLY' if args.apply else 'DRY-RUN (nenhuma alteração será feita)'}")
    print("-" * 72)

    with connection.cursor() as cur:
        state, n = diagnose(cur)

        if state == "missing":
            print("  [!] Tabela professors_professor_cursos não encontrada (ou sem colunas "
                  "esperadas). Nada a fazer — verifique o banco/migrações.")
            return 2

        if state == "ok":
            print(f"  [OK] Tabela já está correta (coluna 'course_id' presente). "
                  f"Linhas: {n}. Nada a fazer (idempotente).")
            return 0

        if state == "ambiguous":
            print(f"  [!] Estado inesperado: existem AMBAS as colunas 'course_id' e "
                  f"'courseunit_id' (linhas: {n}). Não vou alterar automaticamente. "
                  f"Inspecione manualmente.")
            return 2

        # state == "stale"
        print(f"  [DEFASADO] Coluna física é 'courseunit_id' (esperado: 'course_id').")
        print(f"             Linhas na tabela M2M: {n}")

        if n and n > 0:
            orfas, sem_course, pares = preview_data_mapping(cur)
            print("  Preview do mapeamento courseunit_id -> courses_courseunit.course_id:")
            print(f"    - linhas órfãs (courseunit inexistente):        {orfas}")
            print(f"    - linhas sem course_id no courseunit:           {sem_course}")
            print(f"    - pares (professor, course) distintos após map: {pares}")
            if not args.migrate_data:
                print("  [ABORTADO] A tabela tem dados. Rode com --apply --migrate-data para "
                      "migrar (após revisar o preview acima). Nenhuma alteração feita.")
                return 3
            if orfas or sem_course:
                print("  [ABORTADO] Há linhas que não mapeiam com segurança "
                      "(órfãs ou sem course_id). Trate os dados manualmente. Nada alterado.")
                return 3

        if not args.apply:
            plano = "rename simples (tabela vazia)" if not n else "migração de dados"
            print(f"  [DRY-RUN] Reparo aplicável: {plano}. "
                  f"Rode novamente com --apply para executar.")
            return 0

        # APPLY — confirmação extra quando o alvo não é localhost (ex.: Supabase)
        host = (connection.settings_dict.get("HOST") or "").lower()
        is_local = host in ("", "localhost", "127.0.0.1", "::1")
        if not is_local and not args.yes:
            print(f"  [ATENCAO] Você está prestes a ALTERAR um banco REMOTO: {db_label()}")
            try:
                resp = input("  Digite 'APLICAR' (maiúsculas) para confirmar: ").strip()
            except EOFError:
                resp = ""
            if resp != "APLICAR":
                print("  [CANCELADO] Confirmação não recebida. Nenhuma alteração feita.")
                return 4

        try:
            with transaction.atomic():
                print("  Aplicando reparo...")
                if not n or n == 0:
                    repair_empty(cur)
                else:
                    repair_with_data(cur)
            print("  [SUCESSO] Reparo aplicado e commitado.")
        except Exception as e:  # noqa: BLE001
            print(f"  [ERRO] Reparo revertido (rollback). Causa: {e}")
            return 1

        # verificação pós-reparo
        state2, n2 = diagnose(cur)
        cols = get_columns(cur)
        print("-" * 72)
        print(f"  Verificação: estado={state2}, colunas={sorted(cols)}, linhas={n2}")
        if state2 == "ok":
            print("  [OK] Tabela agora está em conformidade com as migrações.")
            return 0
        print("  [!] Estado ainda não 'ok' — inspecione manualmente.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
