"""
fix_unidades.py — Corrige as unidades no banco de dados:
1. Separa a unidade composta em 4 unidades independentes
2. Mantém ISEPAM e ISERJ com seus nomes corretos do CSV
3. Cria/atualiza os logins de coordenador para cada unidade
Executar com: ..\.venv\Scripts\python.exe fix_unidades.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
django.setup()

from apps.accounts.models import User
from apps.core.models import Unidade
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent
import csv

print("=" * 70)
print("  FIX UNIDADES — AllocGest DESUP")
print("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Remover a unidade composta e criar as 4 separadas
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] Corrigindo unidade composta (4 unidades)...")

nome_composto = "FAETEC Santo Antônio de Pádua / Bom Jesus de Itabapoana / Itaperuna / Três Rios"
unidade_composta = Unidade.objects.filter(nome=nome_composto).first()

# Definição das 4 unidades separadas
quatro_unidades = [
    {
        "nome": "FAETEC Santo Antônio de Pádua",
        "sigla": "FAETEC-SAdP",
        "email": "santoantoniopadua.unidade@faetec.rj.gov.br",
    },
    {
        "nome": "FAETEC Bom Jesus de Itabapoana",
        "sigla": "FAETEC-BJI",
        "email": "bomjesusitabapoana.unidade@faetec.rj.gov.br",
    },
    {
        "nome": "FAETEC Itaperuna",
        "sigla": "FAETEC-ITP",
        "email": "itaperuna.unidade@faetec.rj.gov.br",
    },
    {
        "nome": "FAETERJ Três Rios",
        "sigla": "FAETERJ-TR",
        "email": "tresrios.unidade@faetec.rj.gov.br",
    },
]

# Criar as 4 unidades individuais
unidades_criadas = []
for u_data in quatro_unidades:
    u, created = Unidade.objects.get_or_create(
        nome=u_data["nome"],
        defaults={"sigla": u_data["sigla"], "status": True}
    )
    print(f"  {'CRIADA' if created else 'Já existia'}: {u.nome}")
    unidades_criadas.append((u, u_data["email"]))

    # Criar user para a unidade
    email = u_data["email"]
    if not User.objects.filter(email=email).exists():
        User.objects.create_user(
            email=email,
            password="Faetec@123",
            first_name="Coordenador",
            last_name=u.sigla,
            perfil="COORDENADOR_UNIDADE",
            unidade=u,
            forcar_troca_senha=True
        )
        print(f"    → Usuário criado: {email}")

# Migrar cursos e componentes da unidade composta para Santo Antônio de Pádua (primeira das 4)
if unidade_composta:
    print(f"\n  Migrando dados da unidade composta para FAETEC Santo Antônio de Pádua...")
    unidade_principal = Unidade.objects.get(nome="FAETEC Santo Antônio de Pádua")
    cursos_migrados = CourseUnit.objects.filter(unidade=unidade_composta)
    count = cursos_migrados.count()
    cursos_migrados.update(unidade=unidade_principal)
    print(f"  {count} curso(s) migrado(s)")

    # Migrar usuário da unidade composta
    users_compostos = User.objects.filter(unidade=unidade_composta)
    users_compostos.update(unidade=unidade_principal)
    print(f"  {users_compostos.count()} usuário(s) migrado(s)")

    # Agora re-popular o CSV desta unidade para as 4
    csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "sensivel",
                            "FAETERJ_STANTONIODEPADUA-ITABOANA-ITAPERUNA-3RIOS.CSV")
    print(f"\n  Re-populando dados do CSV para as 4 unidades...")
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
    except Exception:
        with open(csv_path, 'r', encoding='latin1') as f:
            rows = list(csv.DictReader(f, delimiter=';'))

    # Todas as 4 unidades recebem os mesmos cursos e matrizes
    for unidade_alvo, _ in unidades_criadas:
        for row in rows:
            curso_nome = str(row.get('Curso', '')).strip()
            periodo = str(row.get('Período', '')).strip()
            codigo = str(row.get('Código', '')).strip()
            disciplina = str(row.get('Disciplina', '')).strip()

            if not curso_nome or curso_nome == 'nan':
                continue

            sigla_curso = ''.join([w[0] for w in curso_nome.split() if len(w) > 2])[:10]
            curso_global, _ = Course.objects.get_or_create(
                nome=curso_nome,
                defaults={"sigla": sigla_curso}
            )
            curso, _ = CourseUnit.objects.get_or_create(curso=curso_global, unidade=unidade_alvo)

            matriz, _ = CurriculumMatrix.objects.get_or_create(
                curso=curso,
                nome=f"Matriz {curso.sigla} 2024",
                defaults={"is_vigente": True, "periodo_letivo": "2024.1", "turno": "N"}
            )

            if codigo == '-' or codigo == 'nan' or not codigo:
                codigo_comp = f"{sigla_curso}-{periodo}-{''.join([w[0] for w in disciplina.split() if len(w) > 2])[:3]}"
            else:
                codigo_comp = codigo

            componente, _ = CurricularComponent.objects.get_or_create(
                codigo=codigo_comp,
                defaults={
                    "nome": disciplina,
                    "sigla": codigo_comp[:10],
                    "carga_horaria_padrao": 80,
                    "creditos": 4,
                }
            )

            MatrixComponent.objects.get_or_create(
                matriz=matriz,
                componente_curricular=componente,
                defaults={
                    "codigo": codigo_comp,
                    "periodo": f"{periodo}º Período",
                    "carga_horaria": 80,
                    "creditos": 4,
                    "status": "SEM_PROFESSOR",
                }
            )

    # Remover a unidade composta
    unidade_composta.delete()
    print(f"  Unidade composta removida com sucesso.")
else:
    print("  Unidade composta não encontrada (já pode ter sido removida).")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Verificar/Corrigir nomes de ISEPAM e ISERJ
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] Verificando ISEPAM e ISERJ...")

isepam_nome = "Instituto de Educação Aldo Muylaert (ISEPAM)"
iserj_nome = "Instituto de Educação do Rio de Janeiro (ISERJ)"

for nome, sigla, email_prefix in [
    (isepam_nome, "ISEPAM", "isepam"),
    (iserj_nome, "ISERJ", "iserj"),
]:
    u = Unidade.objects.filter(nome=nome).first()
    if u:
        print(f"  OK: {u.nome} (sigla: {u.sigla})")
        if u.sigla != sigla:
            u.sigla = sigla
            u.save()
            print(f"    Sigla corrigida para: {sigla}")
    else:
        u, created = Unidade.objects.get_or_create(
            nome=nome,
            defaults={"sigla": sigla, "status": True}
        )
        print(f"  {'CRIADA' if created else 'Já existia'}: {u.nome}")

    email = f"{email_prefix}.unidade@faeterj-pr.edu.br"
    if not User.objects.filter(email=email).exists():
        User.objects.create_user(
            email=email,
            password="Faetec@123",
            first_name="Coordenador",
            last_name=sigla,
            perfil="COORDENADOR_UNIDADE",
            unidade=u,
            forcar_troca_senha=True
        )
        print(f"    → Usuário criado: {email}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Verificar FAETERJ Três Rios (se existia separado)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] Verificando FAETERJ Três Rios do CSV separado...")
tr_csv = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "sensivel", "FAETERJ_3RIOS.CSV")
try:
    with open(tr_csv, 'r', encoding='utf-8') as f:
        rows_tr = list(csv.DictReader(f, delimiter=';'))
except Exception:
    with open(tr_csv, 'r', encoding='latin1') as f:
        rows_tr = list(csv.DictReader(f, delimiter=';'))

# Já deve existir via quatro_unidades acima
u_tr = Unidade.objects.filter(nome="FAETERJ Três Rios").first()
if u_tr:
    print(f"  OK: {u_tr.nome}")
    for row in rows_tr:
        curso_nome = str(row.get('Curso', '')).strip()
        periodo = str(row.get('Período', '')).strip()
        codigo = str(row.get('Código', '')).strip()
        disciplina = str(row.get('Disciplina', '')).strip()

        if not curso_nome or curso_nome == 'nan':
            continue

        sigla_curso = ''.join([w[0] for w in curso_nome.split() if len(w) > 2])[:10]
        curso_global, _ = Course.objects.get_or_create(
            nome=curso_nome,
            defaults={"sigla": sigla_curso}
        )
        curso, _ = CourseUnit.objects.get_or_create(curso=curso_global, unidade=u_tr)

        matriz, _ = CurriculumMatrix.objects.get_or_create(
            curso=curso,
            nome=f"Matriz {curso.sigla} 2024",
            defaults={"is_vigente": True, "periodo_letivo": "2024.1", "turno": "N"}
        )

        if codigo == '-' or codigo == 'nan' or not codigo:
            codigo_comp = f"{sigla_curso}-{periodo}-{''.join([w[0] for w in disciplina.split() if len(w) > 2])[:3]}"
        else:
            codigo_comp = codigo

        componente, _ = CurricularComponent.objects.get_or_create(
            codigo=codigo_comp,
            defaults={
                "nome": disciplina,
                "sigla": codigo_comp[:10],
                "carga_horaria_padrao": 80,
                "creditos": 4,
            }
        )

        MatrixComponent.objects.get_or_create(
            matriz=matriz,
            componente_curricular=componente,
            defaults={
                "codigo": codigo_comp,
                "periodo": f"{periodo}º Período",
                "carga_horaria": 80,
                "creditos": 4,
                "status": "SEM_PROFESSOR",
            }
        )
    print(f"  Dados do CSV de Três Rios processados.")

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  RESUMO")
print("=" * 70)
print(f"  Total de Unidades no banco: {Unidade.objects.count()}")
for u in Unidade.objects.order_by('nome'):
    users_count = User.objects.filter(unidade=u).count()
    cursos_count = CourseUnit.objects.filter(unidade=u).count()
    print(f"  [{u.sigla}] {u.nome} — {cursos_count} curso(s), {users_count} user(s)")
print()
