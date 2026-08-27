"""
Cria professores com horas curriculares incompletas para testar o
modulo de Alocacao Extracurricular.

Logica: professor com pendencia = ch_alocada < contrato.max_class_hours
  - Contrato "40h DE" tem max_class_hours = 20
  - Professores SEM componentes na matriz -> ch_alocada = 0 (pendencia total)
  - Professores com poucos componentes    -> ch_alocada < 20 (pendencia parcial)
"""
import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from apps.core.models import Unidade
from apps.courses.models import CurriculumMatrix, CurricularComponent, MatrixComponent
from apps.professors.models import Professor, ContractType
from seeds.helpers import update_or_create_professor

unidade = Unidade.objects.get(sigla="FAETEC-TESTE")
contrato = ContractType.objects.get(nome="Ensino Técnico - 40h")

# Pega a matriz existente para alocar apenas um componente nos profs parciais
matriz = CurriculumMatrix.objects.filter(unidades=unidade).first()

# ── Professores SEM alocacao curricular (pendencia total = 20h) ────────────────
sem_alocacao = [
    {"id_funcional": "IDF-P006", "rh_matricula": "MAT-P006", "legacy": "P006", "rh_nome": "Fernando Alves Costa",    "rh_email": "fernando.costa@faetec.rj.gov.br",    "eixo": "ADMIN"},
    {"id_funcional": "IDF-P007", "rh_matricula": "MAT-P007", "legacy": "P007", "rh_nome": "Gabriela Nunes Pereira",  "rh_email": "gabriela.pereira@faetec.rj.gov.br",  "eixo": "FORMACAO"},
    {"id_funcional": "IDF-P008", "rh_matricula": "MAT-P008", "legacy": "P008", "rh_nome": "Henrique Martins Duarte", "rh_email": "henrique.duarte@faetec.rj.gov.br",   "eixo": "INFO"},
]

print("--- Professores SEM alocacao (ch_alocada = 0) ---")
for d in sem_alocacao:
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
            "ha": 0,  # sem horas alocadas na matriz
        },
    )
    status = "criado" if created else "ja existia"
    print(f"  {d['rh_nome']} -> ch_alocada={prof.ch_alocada}h / meta=20h | pendencia={max(20 - prof.ch_alocada, 0)}h | {status}")

# ── Professores com alocacao PARCIAL (1 componente de 60h = 3h/semana aprox.) ─
# Vamos criar um componente extra de 60h e alocar so a esses profs
parcial_data = [
    {"id_funcional": "IDF-P009", "rh_matricula": "MAT-P009", "legacy": "P009", "rh_nome": "Isabella Rocha Santos",   "rh_email": "isabella.santos@faetec.rj.gov.br",   "eixo": "ELETRO"},
    {"id_funcional": "IDF-P010", "rh_matricula": "MAT-P010", "legacy": "P010", "rh_nome": "Joao Victor Carvalho",    "rh_email": "joao.carvalho@faetec.rj.gov.br",     "eixo": "MECANICA"},
]

# Componente de baixa CH para deixar pendencia residual
componente_extra, _ = CurricularComponent.objects.get_or_create(
    codigo="ED001",
    defaults={
        "nome": "Educacao Empreendedora",
        "sigla": "EMPR",
        "carga_horaria_padrao": 40,  # 40h semestrais = 2h/semana < meta de 20h/semana
        "creditos": 2,
    },
)

print("\n--- Professores com alocacao PARCIAL ---")
for d in parcial_data:
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
            "ha": 0,
        },
    )
    p_status = "criado" if created else "ja existia"

    if matriz:
        mc, mc_created = MatrixComponent.objects.get_or_create(
            matriz=matriz,
            componente_curricular=componente_extra,
            defaults={
                "periodo": "1 Periodo",
                "carga_horaria": 40,
                "carga_horaria_semanal": 2.0,
                "creditos": 2,
                "docente": prof,
                "status": "COMPLETO",
            },
        )
        # se o componente ja estava vinculado a outra pessoa, atualiza o docente
        if not mc_created and mc.docente != prof:
            mc.docente = prof
            mc.save()

    print(f"  {d['rh_nome']} -> ch_alocada={prof.ch_alocada}h / meta=20h | pendencia={max(20 - prof.ch_alocada, 0)}h | {p_status}")

print("\n[OK] Professores com pendencia criados!")
print("Resumo esperado de pendencias:")
print("  P006 Fernando  -> 20h pendentes (sem alocacao)")
print("  P007 Gabriela  -> 20h pendentes (sem alocacao)")
print("  P008 Henrique  -> 20h pendentes (sem alocacao)")
print("  P009 Isabella  ->  2h alocadas, ~18h pendentes")
print("  P010 Joao Victor -> 2h alocadas, ~18h pendentes")
