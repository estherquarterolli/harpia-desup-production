"""
Seed completo para a unidade FAETEC-TESTE.

Popula TODAS as áreas do sistema para testes:
  - Unidade ativa
  - 3 Cursos (Informática, Administração, Eletrotécnica)
  - 3 Matrizes vigentes (manhã, tarde, noite)
  - 30+ componentes curriculares distribuídos
  - 15 Professores com alocações variadas
  - 1 Janela de Entrega aberta
  - Pendências extracurriculares (TCC, Extensão, Redução)
"""
import os
import sys
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from apps.core.models import Unidade, JanelaEntrega
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent
from apps.professors.models import Professor, ContractType
from apps.extra_curricular.models import PendenciaExtra, OrientacaoTCC, AtividadeExtensionista, ReducaoCargaHoraria
from seeds.helpers import update_or_create_professor

print("=" * 60)
print("  SEED COMPLETO — FAETEC TESTE")
print("=" * 60)

# ══════════════════════════════════════════════════════════════════════════════
# 1. UNIDADE
# ══════════════════════════════════════════════════════════════════════════════
unidade, _ = Unidade.objects.get_or_create(
    sigla="FAETEC-TESTE",
    defaults={"nome": "Unidade de Teste", "status": True},
)
# Garantir que está ativa
if not unidade.status:
    unidade.status = True
    unidade.save()
print(f"\n[OK] Unidade: {unidade}")

# ══════════════════════════════════════════════════════════════════════════════
# 2. TIPOS DE CONTRATO
# ══════════════════════════════════════════════════════════════════════════════
contrato_40h, _ = ContractType.objects.get_or_create(
    nome="Ensino Técnico - 40h",
    defaults={
        "regime_trabalho": "40h DE",
        "max_class_hours": 20,
        "max_total_hours": 40,
        "max_classes": 6,
    },
)

contrato_20h, _ = ContractType.objects.get_or_create(
    nome="Ensino Técnico - 20h",
    defaults={
        "regime_trabalho": "20h",
        "max_class_hours": 12,
        "max_total_hours": 20,
        "max_classes": 4,
    },
)
print(f"[OK] Contratos: {contrato_40h.nome}, {contrato_20h.nome}")

# ══════════════════════════════════════════════════════════════════════════════
# 3. CURSOS (3 cursos na mesma unidade)
# ══════════════════════════════════════════════════════════════════════════════
curso_info_global, _ = Course.objects.get_or_create(
    sigla="TI",
    defaults={"nome": "Técnico em Informática"},
)
curso_admin_global, _ = Course.objects.get_or_create(
    sigla="ADM",
    defaults={"nome": "Técnico em Administração"},
)
curso_eletro_global, _ = Course.objects.get_or_create(
    sigla="ELETRO",
    defaults={"nome": "Técnico em Eletrotécnica"},
)
curso_info, _ = CourseUnit.objects.get_or_create(curso=curso_info_global, unidade=unidade)
curso_admin, _ = CourseUnit.objects.get_or_create(curso=curso_admin_global, unidade=unidade)
curso_eletro, _ = CourseUnit.objects.get_or_create(curso=curso_eletro_global, unidade=unidade)
print(f"[OK] Cursos: {curso_info.sigla}, {curso_admin.sigla}, {curso_eletro.sigla}")

# ══════════════════════════════════════════════════════════════════════════════
# 4. PROFESSORES (15 docentes com perfis variados)
# ══════════════════════════════════════════════════════════════════════════════
professores_data = [
    # --- 40h DE — alocação completa (alocados na curricular) ---
    {"id": "IDF-P001", "mat": "MAT-P001", "leg": "P001", "nome": "Ana Carolina Souza",      "email": "ana.souza@faetec.rj.gov.br",       "materia": "INFO",     "contrato": contrato_40h, "ha": 20},
    {"id": "IDF-P002", "mat": "MAT-P002", "leg": "P002", "nome": "Bruno Henrique Lima",     "email": "bruno.lima@faetec.rj.gov.br",      "materia": "ELETRO",   "contrato": contrato_40h, "ha": 20},
    {"id": "IDF-P003", "mat": "MAT-P003", "leg": "P003", "nome": "Carla Regina Mendes",     "email": "carla.mendes@faetec.rj.gov.br",    "materia": "ADMIN",    "contrato": contrato_40h, "ha": 20},
    {"id": "IDF-P004", "mat": "MAT-P004", "leg": "P004", "nome": "Diego Ferreira Rocha",    "email": "diego.rocha@faetec.rj.gov.br",     "materia": "INFO",     "contrato": contrato_40h, "ha": 20},
    {"id": "IDF-P005", "mat": "MAT-P005", "leg": "P005", "nome": "Elaine Cristina Barbosa", "email": "elaine.barbosa@faetec.rj.gov.br",  "materia": "FORMACAO", "contrato": contrato_40h, "ha": 20},
    # --- 40h DE — alocação parcial (precisam de extracurricular) ---
    {"id": "IDF-P006", "mat": "MAT-P006", "leg": "P006", "nome": "Fernando Alves Costa",    "email": "fernando.costa@faetec.rj.gov.br",  "materia": "ADMIN",    "contrato": contrato_40h, "ha": 0},
    {"id": "IDF-P007", "mat": "MAT-P007", "leg": "P007", "nome": "Gabriela Nunes Pereira",  "email": "gabriela.pereira@faetec.rj.gov.br","materia": "FORMACAO", "contrato": contrato_40h, "ha": 0},
    {"id": "IDF-P008", "mat": "MAT-P008", "leg": "P008", "nome": "Henrique Martins Duarte", "email": "henrique.duarte@faetec.rj.gov.br", "materia": "INFO",     "contrato": contrato_40h, "ha": 0},
    # --- 40h DE — parcial com poucas horas ---
    {"id": "IDF-P009", "mat": "MAT-P009", "leg": "P009", "nome": "Isabella Rocha Santos",   "email": "isabella.santos@faetec.rj.gov.br", "materia": "ELETRO",   "contrato": contrato_40h, "ha": 0},
    {"id": "IDF-P010", "mat": "MAT-P010", "leg": "P010", "nome": "João Victor Carvalho",    "email": "joao.carvalho@faetec.rj.gov.br",   "materia": "MECANICA", "contrato": contrato_40h, "ha": 0},
    # --- 20h — regime parcial ---
    {"id": "IDF-P011", "mat": "MAT-P011", "leg": "P011", "nome": "Karen Oliveira Dias",     "email": "karen.dias@faetec.rj.gov.br",      "materia": "INFO",     "contrato": contrato_20h, "ha": 12},
    {"id": "IDF-P012", "mat": "MAT-P012", "leg": "P012", "nome": "Lucas Ribeiro Martins",   "email": "lucas.martins@faetec.rj.gov.br",   "materia": "ADMIN",    "contrato": contrato_20h, "ha": 12},
    # --- 40h DE — professor afastado ---
    {"id": "IDF-P013", "mat": "MAT-P013", "leg": "P013", "nome": "Mariana Castro Lopes",    "email": "mariana.lopes@faetec.rj.gov.br",   "materia": "ELETRO",   "contrato": contrato_40h, "ha": 0, "status": "Afastado"},
    # --- 40h DE — extras para variedade ---
    {"id": "IDF-P014", "mat": "MAT-P014", "leg": "P014", "nome": "Natália Ferraz Gomes",    "email": "natalia.gomes@faetec.rj.gov.br",   "materia": "FORMACAO", "contrato": contrato_40h, "ha": 20},
    {"id": "IDF-P015", "mat": "MAT-P015", "leg": "P015", "nome": "Otávio Cardoso Farias",   "email": "otavio.farias@faetec.rj.gov.br",   "materia": "ELETRO",   "contrato": contrato_40h, "ha": 20},
]

professores = []
for d in professores_data:
    prof, created = update_or_create_professor(
        id_funcional=d["id"],
        rh_matricula=d["mat"],
        legacy_values=[d["leg"]],
        defaults={
            "rh_nome": d["nome"],
            "rh_email": d["email"],
            "materia": d["materia"],
            "tipo_contrato": d["contrato"],
            "unidade_principal": unidade,
            "status": d.get("status", "Ativo"),
            "ha": d["ha"],
        },
    )
    professores.append(prof)
    tag = "criado" if created else "atualizado"
    print(f"  [{tag}] {d['nome']} ({d['contrato'].nome})")

print(f"[OK] {len(professores)} professores configurados")

# ══════════════════════════════════════════════════════════════════════════════
# 5. COMPONENTES CURRICULARES
# ══════════════════════════════════════════════════════════════════════════════

# --- INFORMÁTICA (Manhã) ---
disc_info = {
    "1º Período": [
        ("Algoritmos e Lógica de Programação",  "ALP",   "ALP001", 80),
        ("Fundamentos de Hardware",              "HARD",  "HRD001", 60),
        ("Matemática Aplicada",                  "MAT",   "MAT001", 80),
    ],
    "2º Período": [
        ("Programação Orientada a Objetos",      "POO",   "POO001", 80),
        ("Sistemas Operacionais",                "SO",    "SO001",  60),
        ("Banco de Dados I",                     "BD1",   "BD001",  60),
    ],
    "3º Período": [
        ("Desenvolvimento Web Front-end",        "WEB",   "WEB001", 80),
        ("Banco de Dados II",                    "BD2",   "BD002",  60),
        ("Redes de Computadores",                "REDES", "RDS001", 60),
    ],
    "4º Período": [
        ("Projeto Integrador",                   "PROJ",  "PRJ001", 80),
        ("Segurança da Informação",              "SEG",   "SEG001", 60),
        ("Estágio Supervisionado",               "EST",   "EST001", 160),
    ],
}

# --- ADMINISTRAÇÃO (Tarde) ---
disc_admin = {
    "1º Período": [
        ("Introdução à Administração",          "IADM",  "IAD001", 80),
        ("Contabilidade Básica",                "CONT",  "CNT001", 60),
        ("Português Instrumental",              "PORT",  "PRT001", 60),
    ],
    "2º Período": [
        ("Gestão de Pessoas",                   "GP",    "GP001",  80),
        ("Marketing e Vendas",                  "MKT",   "MKT001", 60),
        ("Matemática Financeira",               "MFIN",  "MFN001", 60),
    ],
    "3º Período": [
        ("Logística e Cadeia de Suprimentos",   "LOG",   "LOG001", 80),
        ("Direito Empresarial",                 "DIR",   "DIR001", 60),
        ("Gestão da Qualidade",                 "QUAL",  "QUA001", 60),
    ],
    "4º Período": [
        ("Empreendedorismo",                    "EMPR",  "EMP001", 80),
        ("Projeto Integrador Adm.",             "PJADM", "PJA001", 60),
        ("Estágio Supervisionado Adm.",         "ESTADM","ESA001", 160),
    ],
}

# --- ELETROTÉCNICA (Noite) ---
disc_eletro = {
    "1º Período": [
        ("Eletricidade Básica",                 "ELET",  "ELT001", 80),
        ("Desenho Técnico",                     "DEST",  "DST001", 60),
        ("Física Aplicada",                     "FIS",   "FIS001", 80),
    ],
    "2º Período": [
        ("Circuitos Elétricos",                 "CIRC",  "CRC001", 80),
        ("Eletrônica Analógica",                "EANA",  "EAN001", 60),
        ("Instalações Elétricas I",             "INST1", "IN1001", 60),
    ],
    "3º Período": [
        ("Máquinas Elétricas",                  "MAQ",   "MAQ001", 80),
        ("Eletrônica Digital",                  "EDIG",  "EDG001", 60),
        ("Instalações Elétricas II",            "INST2", "IN2001", 60),
    ],
    "4º Período": [
        ("Automação Industrial",                "AUTO",  "AUT001", 80),
        ("Comandos Elétricos",                  "CMD",   "CMD001", 60),
        ("Estágio Eletrotécnica",               "ESTEL", "ETE001", 160),
    ],
}


def criar_componentes(disciplinas_dict):
    """Cria os CurricularComponent e retorna dict {periodo: [(componente, ch)]}."""
    resultado = {}
    for periodo, disciplinas in disciplinas_dict.items():
        comps = []
        for nome, sigla, codigo, ch in disciplinas:
            comp, _ = CurricularComponent.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "nome": nome,
                    "sigla": sigla,
                    "carga_horaria_padrao": ch,
                    "creditos": ch // 20,
                },
            )
            comps.append((comp, ch))
        resultado[periodo] = comps
    return resultado


comps_info = criar_componentes(disc_info)
comps_admin = criar_componentes(disc_admin)
comps_eletro = criar_componentes(disc_eletro)
print(f"[OK] Componentes curriculares criados")

# ══════════════════════════════════════════════════════════════════════════════
# 6. MATRIZES CURRICULARES (3 matrizes vigentes)
# ══════════════════════════════════════════════════════════════════════════════

def criar_matriz(curso, nome, turno, componentes_dict, profs_pool):
    """Cria matriz vigente e vincula componentes, distribuindo professores."""
    matriz, m_created = CurriculumMatrix.objects.get_or_create(
        curso=curso,
        nome=nome,
        defaults={
            "is_vigente": True,
            "periodo_letivo": "2026.1",
            "turno": turno,
        },
    )
    tag = "criada" if m_created else "já existe"
    print(f"  [Matriz {tag}] {nome} ({curso.sigla} - {turno})")

    prof_idx = 0
    for periodo, comps in componentes_dict.items():
        for comp, ch in comps:
            professor = profs_pool[prof_idx % len(profs_pool)]
            prof_idx += 1

            mc, mc_created = MatrixComponent.objects.get_or_create(
                matriz=matriz,
                componente_curricular=comp,
                defaults={
                    "periodo": periodo,
                    "carga_horaria": ch,
                    "carga_horaria_semanal": round(ch / 20, 2),
                    "creditos": ch // 20,
                    "docente": professor,
                    "status": "COMPLETO",
                },
            )
            if mc_created:
                print(f"    [{periodo}] {comp.nome} -> {professor.rh_nome}")
    return matriz


# Pools de professores por curso
profs_info = [professores[0], professores[3], professores[7], professores[10], professores[4]]   # Ana, Diego, Henrique, Karen, Elaine
profs_admin = [professores[2], professores[5], professores[11], professores[4], professores[13]]  # Carla, Fernando, Lucas, Elaine, Natália
profs_eletro = [professores[1], professores[8], professores[14], professores[9], professores[4]]  # Bruno, Isabella, Otávio, João, Elaine

matriz_info = criar_matriz(curso_info, "Matriz Informática 2026.1", "M", comps_info, profs_info)
matriz_admin = criar_matriz(curso_admin, "Matriz Administração 2026.1", "T", comps_admin, profs_admin)
matriz_eletro = criar_matriz(curso_eletro, "Matriz Eletrotécnica 2026.1", "N", comps_eletro, profs_eletro)

# Vincular professores aos cursos
for prof in profs_info:
    prof.cursos.add(curso_info)
for prof in profs_admin:
    prof.cursos.add(curso_admin)
for prof in profs_eletro:
    prof.cursos.add(curso_eletro)

print(f"[OK] 3 matrizes criadas com componentes alocados")

# ══════════════════════════════════════════════════════════════════════════════
# 7. JANELA DE ENTREGA (aberta para o semestre atual)
# ══════════════════════════════════════════════════════════════════════════════
hoje = date.today()
janela, j_created = JanelaEntrega.objects.get_or_create(
    semestre="2026.1",
    unidade=unidade,
    defaults={
        "data_inicio": hoje - timedelta(days=7),
        "data_fim": hoje + timedelta(days=60),
        "status": JanelaEntrega.StatusChoices.ABERTO,
    },
)
if not j_created:
    # Garantir que está aberta e com datas válidas
    janela.status = JanelaEntrega.StatusChoices.ABERTO
    janela.data_inicio = hoje - timedelta(days=7)
    janela.data_fim = hoje + timedelta(days=60)
    janela.save()
print(f"[OK] Janela de Entrega: {janela.semestre} — {janela.data_inicio} até {janela.data_fim} (ABERTA)")

# Criar também uma janela global (para todas as unidades)
janela_global, jg_created = JanelaEntrega.objects.get_or_create(
    semestre="2026.1",
    unidade=None,
    defaults={
        "data_inicio": hoje - timedelta(days=30),
        "data_fim": hoje + timedelta(days=90),
        "status": JanelaEntrega.StatusChoices.ABERTO,
    },
)
if not jg_created:
    janela_global.status = JanelaEntrega.StatusChoices.ABERTO
    janela_global.data_inicio = hoje - timedelta(days=30)
    janela_global.data_fim = hoje + timedelta(days=90)
    janela_global.save()
print(f"[OK] Janela Global: {janela_global.semestre} — ABERTA para todas as unidades")

# ══════════════════════════════════════════════════════════════════════════════
# 8. PENDÊNCIAS EXTRACURRICULARES
# ══════════════════════════════════════════════════════════════════════════════
print("\n--- Pendências Extracurriculares ---")

# P006 Fernando — sem alocação curricular, precisa justificar 20h
# → TCC (4 orientandos = 2h) + Extensão (10 alunos = 5h) + Redução (13h)
pend_fernando, _ = PendenciaExtra.objects.get_or_create(
    professor=professores[5],  # Fernando
    semestre="2026.1",
    defaults={
        "unidade": unidade,
        "status": PendenciaExtra.StatusChoices.ENVIADO,
    },
)
OrientacaoTCC.objects.get_or_create(
    pendencia=pend_fernando,
    defaults={"num_orientandos": 4},
)
AtividadeExtensionista.objects.get_or_create(
    pendencia=pend_fernando,
    defaults={"num_estudantes": 10},
)
ReducaoCargaHoraria.objects.get_or_create(
    pendencia=pend_fernando,
    defaults={
        "motivo_reducao": "Licença para capacitação docente (Art. 87, Lei 8.112/90)",
        "horas_reduzidas": Decimal("13.0"),
    },
)
print(f"  [OK] {professores[5].rh_nome} — Pendência ENVIADA (TCC + Extensão + Redução)")

# P007 Gabriela — sem alocação, TCC com 8 orientandos (máx = 4h)
pend_gabriela, _ = PendenciaExtra.objects.get_or_create(
    professor=professores[6],  # Gabriela
    semestre="2026.1",
    defaults={
        "unidade": unidade,
        "status": PendenciaExtra.StatusChoices.RASCUNHO,
    },
)
OrientacaoTCC.objects.get_or_create(
    pendencia=pend_gabriela,
    defaults={"num_orientandos": 8},
)
print(f"  [OK] {professores[6].rh_nome} — Pendência RASCUNHO (TCC 8 orientandos)")

# P008 Henrique — sem alocação, extensão com 30 alunos (15h) + redução 5h
pend_henrique, _ = PendenciaExtra.objects.get_or_create(
    professor=professores[7],  # Henrique
    semestre="2026.1",
    defaults={
        "unidade": unidade,
        "status": PendenciaExtra.StatusChoices.APROVADO,
        "sei_numero": "SEI-123456/789012/2026",
    },
)
AtividadeExtensionista.objects.get_or_create(
    pendencia=pend_henrique,
    defaults={"num_estudantes": 30},
)
ReducaoCargaHoraria.objects.get_or_create(
    pendencia=pend_henrique,
    defaults={
        "motivo_reducao": "Coordenação de laboratório de informática",
        "horas_reduzidas": Decimal("5.0"),
    },
)
print(f"  [OK] {professores[7].rh_nome} — Pendência APROVADA (Extensão + Redução)")

# P009 Isabella — alocação parcial, TCC 2 orientandos
pend_isabella, _ = PendenciaExtra.objects.get_or_create(
    professor=professores[8],  # Isabella
    semestre="2026.1",
    defaults={
        "unidade": unidade,
        "status": PendenciaExtra.StatusChoices.ENVIADO,
    },
)
OrientacaoTCC.objects.get_or_create(
    pendencia=pend_isabella,
    defaults={"num_orientandos": 2},
)
AtividadeExtensionista.objects.get_or_create(
    pendencia=pend_isabella,
    defaults={"num_estudantes": 5},
)
print(f"  [OK] {professores[8].rh_nome} — Pendência ENVIADA (TCC + Extensão)")

# P010 João Victor — rejeitada
pend_joao, _ = PendenciaExtra.objects.get_or_create(
    professor=professores[9],  # João
    semestre="2026.1",
    defaults={
        "unidade": unidade,
        "status": PendenciaExtra.StatusChoices.REJEITADO,
        "motivo_status_desup": "Documentação insuficiente. Favor reenviar com comprovantes.",
    },
)
ReducaoCargaHoraria.objects.get_or_create(
    pendencia=pend_joao,
    defaults={
        "motivo_reducao": "Pesquisa em projeto FAPERJ",
        "horas_reduzidas": Decimal("10.0"),
    },
)
print(f"  [OK] {professores[9].rh_nome} — Pendência REJEITADA (Redução)")

# ══════════════════════════════════════════════════════════════════════════════
# RESUMO FINAL
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  RESUMO DO SEED")
print("=" * 60)
print(f"  Unidade       : {unidade.sigla} — {unidade.nome}")
print(f"  Cursos        : {curso_info.sigla}, {curso_admin.sigla}, {curso_eletro.sigla}")
print(f"  Matrizes      : 3 vigentes (Manhã, Tarde, Noite)")
print(f"  Componentes   : 12 por matriz × 3 = 36 componentes")
print(f"  Professores   : {len(professores)} (13 ativos, 1 afastado, 2 regime 20h)")
print(f"  Janela Entrega: 2026.1 — ABERTA ({janela.data_inicio} a {janela.data_fim})")
print(f"  Pendências    : 5 (1 rascunho, 2 enviadas, 1 aprovada, 1 rejeitada)")
print(f"")
print(f"  Professores com pendência extracurricular:")
print(f"    P006 Fernando  -> ENVIADO  (TCC 4 + Extensão 10 + Redução 13h)")
print(f"    P007 Gabriela  -> RASCUNHO (TCC 8)")
print(f"    P008 Henrique  -> APROVADO (Extensão 30 + Redução 5h)")
print(f"    P009 Isabella  -> ENVIADO  (TCC 2 + Extensão 5)")
print(f"    P010 João V.   -> REJEITADO (Redução 10h)")
print("=" * 60)
print("[OK] Seed concluído com sucesso!")
