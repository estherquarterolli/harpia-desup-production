import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

from apps.core.models import Unidade
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent
from apps.professors.models import Professor, ContractType
from seeds.helpers import update_or_create_professor

# ── Unidade ────────────────────────────────────────────────────────────────────
unidade, _ = Unidade.objects.get_or_create(
    sigla="FAETEC-TESTE",
    defaults={"nome": "Unidade de Teste", "status": True},
)
print(f"[OK] Unidade: {unidade}")

# ── Tipo de Contrato ───────────────────────────────────────────────────────────
contrato, _ = ContractType.objects.get_or_create(
    nome="Ensino Técnico - 40h",
    defaults={
        "regime_trabalho": "40h DE",
        "max_class_hours": 20,
        "max_total_hours": 40,
        "max_classes": 6,
    },
)
print(f"[OK] Contrato: {contrato}")

# ── Professores ────────────────────────────────────────────────────────────────
professores_data = [
    {"id_funcional": "IDF-P001", "rh_matricula": "MAT-P001", "legacy": "P001", "rh_nome": "Ana Carolina Souza",      "rh_email": "ana.souza@faetec.rj.gov.br",      "eixo": "INFO"},
    {"id_funcional": "IDF-P002", "rh_matricula": "MAT-P002", "legacy": "P002", "rh_nome": "Bruno Henrique Lima",     "rh_email": "bruno.lima@faetec.rj.gov.br",     "eixo": "ELETRO"},
    {"id_funcional": "IDF-P003", "rh_matricula": "MAT-P003", "legacy": "P003", "rh_nome": "Carla Regina Mendes",     "rh_email": "carla.mendes@faetec.rj.gov.br",   "eixo": "ADMIN"},
    {"id_funcional": "IDF-P004", "rh_matricula": "MAT-P004", "legacy": "P004", "rh_nome": "Diego Ferreira Rocha",    "rh_email": "diego.rocha@faetec.rj.gov.br",    "eixo": "INFO"},
    {"id_funcional": "IDF-P005", "rh_matricula": "MAT-P005", "legacy": "P005", "rh_nome": "Elaine Cristina Barbosa", "rh_email": "elaine.barbosa@faetec.rj.gov.br", "eixo": "FORMACAO"},
]

professores = []
for d in professores_data:
    prof, created = update_or_create_professor(
        id_funcional=d["id_funcional"],
        rh_matricula=d["rh_matricula"],
        legacy_values=[d["legacy"]],
        defaults={
            "rh_nome": d["rh_nome"],
            "rh_email": d["rh_email"],
            "eixo": d["eixo"],
            "tipo_contrato": contrato,
            "unidade_principal": unidade,
            "status": "Ativo",
            "ha": 20,
        },
    )
    professores.append(prof)
    status = "criado" if created else "já existia"
    print(f"[OK] Professor {d['rh_nome']} — {status}")

# ── Curso ──────────────────────────────────────────────────────────────────────
curso_global, _ = Course.objects.get_or_create(
    sigla="TI",
    defaults={"nome": "Técnico em Informática"},
)
curso, _ = CourseUnit.objects.get_or_create(curso=curso_global, unidade=unidade)
print(f"[OK] Curso: {curso}")

# ── Componentes Curriculares (4 períodos × 3 matérias) ────────────────────────
disciplinas_por_periodo = {
    "1": [
        ("Algoritmos e Lógica de Programação", "ALGO",  "ALP001", 80),
        ("Fundamentos de Hardware",             "HARD",  "HRD001", 60),
        ("Matemática Aplicada",                 "MAT",   "MAT001", 80),
    ],
    "2": [
        ("Programação Orientada a Objetos",     "POO",   "POO001", 80),
        ("Sistemas Operacionais",               "SO",    "SO001",  60),
        ("Banco de Dados I",                    "BD1",   "BD001",  60),
    ],
    "3": [
        ("Desenvolvimento Web Front-end",       "WEB",   "WEB001", 80),
        ("Banco de Dados II",                   "BD2",   "BD002",  60),
        ("Redes de Computadores",               "REDES", "RDS001", 60),
    ],
    "4": [
        ("Projeto Integrador",                  "PROJ",  "PRJ001", 80),
        ("Segurança da Informação",             "SEG",   "SEG001", 60),
        ("Estágio Supervisionado",              "EST",   "EST001", 160),
    ],
}

# ── Matriz Curricular ──────────────────────────────────────────────────────────
matriz, m_created = CurriculumMatrix.objects.get_or_create(
    curso=curso,
    nome="Matriz 2026.1",
    defaults={
        "is_vigente": True,
        "periodo_letivo": "2026.1",
        "turno": "M",
    },
)
print(f"[OK] Matriz: {matriz} — {'criada' if m_created else 'já existe'}")

# ── Componentes da Matriz ──────────────────────────────────────────────────────
prof_idx = 0  # distribui professores ciclicamente
for periodo, disciplinas in disciplinas_por_periodo.items():
    for nome_disc, sigla_disc, codigo_disc, ch in disciplinas:
        componente, _ = CurricularComponent.objects.get_or_create(
            codigo=codigo_disc,
            defaults={
                "nome": nome_disc,
                "sigla": sigla_disc,
                "carga_horaria_padrao": ch,
                "creditos": ch // 20,
            },
        )
        professor_alocado = professores[prof_idx % len(professores)]
        prof_idx += 1

        mc, mc_created = MatrixComponent.objects.get_or_create(
            matriz=matriz,
            componente_curricular=componente,
            defaults={
                "periodo": f"{periodo}° Período",
                "carga_horaria": ch,
                "carga_horaria_semanal": round(ch / 20, 2),
                "creditos": ch // 20,
                "docente": professor_alocado,
                "status": "COMPLETO",
            },
        )
        status = "criado" if mc_created else "já existe"
        print(f"  [{periodo}P] {nome_disc} -> {professor_alocado.rh_nome} - {status}")

print("\n[OK] Seed concluido com sucesso!")
print(f"   Unidade  : {unidade}")
print(f"   Curso    : {curso}")
print(f"   Matriz   : {matriz}")
print(f"   Periodos : 4 (3 materias cada = 12 componentes)")
print(f"   Profs    : {len(professores)}")
