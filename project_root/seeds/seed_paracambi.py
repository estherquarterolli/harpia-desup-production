import os
import sys
import csv
import unicodedata
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.hashers import make_password
from apps.accounts.models import DEFAULT_USER_PASSWORD, User
from apps.core.models import Unidade
from apps.professors.models import Professor, ContractType
from apps.courses.models import Course, CourseUnit, CurriculumMatrix, CurricularComponent, MatrixComponent
from seeds.helpers import update_or_create_professor

from seeds.seed_paracambi_csv import seed_paracambi

if __name__ == "__main__":
    seed_paracambi()
    raise SystemExit


def seed_code(value):
    return value.replace("/", "-")


CSV_DIR = BASE_DIR.parent / "docs"


def normalize_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def title_case_name(value):
    particles = {"de", "da", "do", "das", "dos", "e"}
    parts = []
    for index, raw in enumerate(str(value or "").strip().split()):
        lowered = raw.casefold()
        if index > 0 and lowered in particles:
            parts.append(lowered)
        else:
            parts.append(lowered.capitalize())
    return " ".join(parts)


def materia_from_disciplina(value):
    normalized = normalize_text(value)
    if "informat" in normalized:
        return "INFO"
    if "quim" in normalized or "meio ambiente" in normalized:
        return "QUIMICA"
    if "direito" in normalized:
        return "ADMIN"
    if "psicologia" in normalized:
        return "FORMACAO"
    return "OUTROS"


def contract_defaults(row):
    cargo = row["NOME_CARGO"].strip()
    cargo_norm = normalize_text(cargo)
    vinculo = normalize_text(row["VINCULO_EMPREGATICIO"])
    is_20h = "20 h" in cargo_norm or "20h" in cargo_norm
    categoria = "TERCEIRIZADO" if vinculo == "contr temporario" else "EFETIVO" if vinculo == "efetivo" else "CONCURSADO"
    return {
        "nome": cargo,
        "categoria": categoria,
        "regime_trabalho": "20h" if is_20h else "40h",
        "max_class_hours": 10 if is_20h else 20,
        "max_total_hours": 20 if is_20h else 40,
        "max_classes": 5 if is_20h else 10,
    }


def load_paracambi_professores():
    csv_path = next(CSV_DIR.glob("*.csv"))
    with csv_path.open(encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if normalize_text(row["SETOR_DESC"]) != "faeterj paracambi":
                continue

            cargo = row["NOME_CARGO"].strip()
            cargo_norm = normalize_text(cargo)
            if not (cargo_norm.startswith("prof") or "ensino superior" in cargo_norm):
                continue

            id_funcional = row["ID_FUNCIONAL"].strip()
            matricula = row["MATRICULA"].strip() or f"MAT-{id_funcional}"
            nome = title_case_name(row["NOME"])
            yield {
                "id_funcional": f"IDF-{id_funcional}",
                "rh_matricula": matricula,
                "rh_nome": nome,
                "rh_email": f"{id_funcional.lower()}@faeterj.edu.br",
                "eixo": materia_from_disciplina(row["DISCIPLINA"]),
                "contract_name": cargo,
                "contract_defaults": contract_defaults(row),
                "legacy_names": [nome],
            }

def seed_paracambi():
    print("Criando Unidade Paracambi...")
    unidade, created = Unidade.objects.get_or_create(
        sigla="FAETERJ-PARACAMBI",
        defaults={"nome": "FAETERJ Paracambi"}
    )
    
    print("Criando usuário para a Unidade...")
    user, created = User.objects.get_or_create(
        email="unidadeparacambi@desup.com",
        defaults={
            "password": make_password(DEFAULT_USER_PASSWORD),
            "perfil": "COORDENADOR_UNIDADE",
            "unidade": unidade
        }
    )
    if not created:
        user.password = make_password(DEFAULT_USER_PASSWORD)
        user.save()

    print("Criando Tipos de Contrato...")
    c_40h_i, _ = ContractType.objects.get_or_create(
        nome="PROFESSOR FAETEC I 40H",
        defaults={"max_class_hours": 20, "max_total_hours": 40, "max_classes": 10}
    )
    c_40h_sup, _ = ContractType.objects.get_or_create(
        nome="PROF FAETEC ENS SUP 40H",
        defaults={"max_class_hours": 20, "max_total_hours": 40, "max_classes": 10}
    )
    c_doutorado, _ = ContractType.objects.get_or_create(
        nome="Consta no PPC (Doutorado)",
        defaults={"max_class_hours": 20, "max_total_hours": 40, "max_classes": 10}
    )
    c_mestrado, _ = ContractType.objects.get_or_create(
        nome="Consta no PPC (Mestrado)",
        defaults={"max_class_hours": 20, "max_total_hours": 40, "max_classes": 10}
    )
    c_especialista, _ = ContractType.objects.get_or_create(
        nome="Consta no PPC (Especialista)",
        defaults={"max_class_hours": 20, "max_total_hours": 40, "max_classes": 10}
    )
    c_ppc, _ = ContractType.objects.get_or_create(
        nome="Consta no PPC",
        defaults={"max_class_hours": 20, "max_total_hours": 40, "max_classes": 10}
    )

    print("Criando Professores...")
    professors_data = [
        ("51381966", "Adilson Ricardo da Silva", c_40h_i),
        ("51244861", "Alessandro de Almeida C. Cerqueira", c_40h_sup),
        ("44564465", "Artur Sergio Lopes", c_40h_sup),
        ("42052823", "Hudson dos Santos Barros", c_40h_sup),
        ("44119950", "Túlio Queto de Souza Pinto", c_40h_sup),
        ("N/A_1", "Cinthia da Silva Lisboa", c_doutorado),
        ("N/A_2", "Daniel Vazquez Figueiredo", c_doutorado),
        ("N/A_3", "Diego Mota Lima", c_doutorado),
        ("N/A_4", "Fabio Henrique S. dos Santos", c_doutorado),
        ("N/A_5", "Fausto Amaro da Silva Araujo", c_mestrado),
        ("N/A_6", "Franziska Huber", c_doutorado),
        ("N/A_7", "Iamara da Silva Andrade", c_doutorado),
        ("N/A_8", "Janaina da Silva Vettorazzi", c_doutorado),
        ("N/A_9", "Kátia Regina Araújo da Silva", c_doutorado),
        ("N/A_10", "Leonardo Pinheiro Gomes", c_mestrado),
        ("N/A_11", "Márcio de Brito Serafim", c_mestrado),
        ("N/A_12", "Marcia Lie Ayukawa", c_doutorado),
        ("N/A_13", "Romilda Maria Alves Lemos", c_doutorado),
        ("N/A_14", "Silvestre de Mello de Souza", c_especialista),
        ("N/A_15", "Tereza Aparecida Ferreira Dornelas", c_doutorado),
        ("N/A_16", "Carlos Eduardo Costa", c_doutorado),
        ("N/A_17", "Elizangela Simões", c_mestrado),
        ("N/A_18", "Henrique de Medeiros", c_doutorado),
        ("N/A_19", "Paulo Calixto", c_especialista),
        ("N/A_20", "Rubens Saviano", c_doutorado),
        ("N/A_21", "Selma Gomes", c_ppc),
    ]

    for matricula, nome, contrato in professors_data:
        codigo = seed_code(matricula)
        update_or_create_professor(
            id_funcional=f"IDF-{codigo}",
            rh_matricula=f"MAT-{codigo}",
            legacy_values=[matricula],
            defaults={
                "rh_nome": nome,
                "rh_email": f"{matricula}@faeterj.edu.br" if not matricula.startswith("N/A") else "sem_email@faeterj.edu.br",
                "tipo_contrato": contrato,
                "unidade_principal": unidade
            }
        )

    print("Criando Cursos TGA e ADS...")
    curso_tga_global, _ = Course.objects.get_or_create(sigla="TGA", defaults={"nome": "Tecnologia em Gestão Ambiental"})
    curso_ads_global, _ = Course.objects.get_or_create(sigla="ADS", defaults={"nome": "Análise e Desenvolvimento de Sistemas"})
    curso_tga, _ = CourseUnit.objects.get_or_create(curso=curso_tga_global, unidade=unidade)
    curso_ads, _ = CourseUnit.objects.get_or_create(curso=curso_ads_global, unidade=unidade)

    print("Criando Matriz TGA...")
    matriz_tga, _ = CurriculumMatrix.objects.get_or_create(
        curso=curso_tga_global,
        periodo_letivo="2026.1",
        turno="N",
        defaults={"nome": "Matriz TGA 2026", "is_vigente": True}
    )
    matriz_tga.unidades.add(unidade)

    tga_disciplinas = [
        (1, "QUG", "Química geral", 2, 40),
        (1, "NOD", "Noções de Direito", 2, 40),
        (1, "POR", "Língua Portuguesa", 2, 40),
        (1, "STM", "Segurança do Trabalho e Meio Ambiente", 2, 40),
        (1, "ETI", "Ética", 2, 40),
        (1, "EDU", "Educação Ambiental e Sustentabilidade", 3, 60),
        (1, "GAM", "Geometria aplicada ao Meio Ambiente", 3, 60),
        (1, "ENS", "Energia e Sustentabilidade", 3, 60),
        (1, "MPC", "Metodologia da Pesquisa Científica", 2, 40),
        (1, "EAP", "Estatística Aplicada", 2, 40),
        (1, "MER", "Economia dos Recursos Naturais e Ambiente", 3, 60),
        (1, "QIN", "Química inorgânica", 2, 40),
        (1, "BBT", "Biologia e Biotecnologia Aplicada", 3, 60),
        (2, "BOT", "Botânica Geral", 2, 40),
        (2, "GEO", "Geociência ambiental", 2, 40),
        (2, "ZGE", "Zoologia Geral", 3, 60),
        (2, "ELA", "Ecologia", 3, 60),
        (2, "POL", "Política e Legislação Ambiental", 3, 60),
        (2, "EXT1", "Extensão 1", 2, 40),
        (3, "AGP", "Administração e Gerenciamento de Projetos", 3, 60),
        (3, "RES", "Gerenciamento de Resíduos", 3, 60),
        (3, "GES", "Gestão pela Qualidade de Equipes", 2, 40),
        (3, "GRR", "Georreferenciamento", 3, 60),
        (3, "QAN", "Química Analítica", 3, 60),
        (3, "MIC", "Microbiologia Ambiental", 2, 40),
        (3, "QOR", "Química Orgânica Ambiental", 2, 40),
        (3, "LAG", "Limnologia", 2, 40),
        (3, "CON", "Controle poluição da água", 3, 60),
        (3, "EXT2", "Projeto de Extensão 2", 4, 80),
        (4, "REC", "Recuperação de Áreas degradadas", 3, 60),
        (4, "CAR", "Controle da Poluição Atmosférica", 3, 60),
        (4, "MGB", "Manejo e Gerenciamento de Bacias Hidrográficas", 3, 60),
        (4, "CSO", "Controle da Poluição do Solo", 3, 60),
        (4, "SPQ", "Saúde Pública e a Questão Ambiental", 3, 60),
        (4, "LCA", "Licenciamento, Certificação e Auditoria Ambiental", 5, 100),
        (4, "GUC", "Gestão de Unidades de Conservação", 2, 40),
        (4, "EXT3", "Projeto de Extensão 3", 4, 80),
    ]

    for periodo, cod, nome, cred, ch in tga_disciplinas:
        cc, _ = CurricularComponent.objects.get_or_create(nome=nome, defaults={"carga_horaria_padrao": ch})
        MatrixComponent.objects.get_or_create(
            matriz=matriz_tga,
            codigo=cod,
            defaults={
                "componente_curricular": cc,
                "periodo": periodo,
                "creditos": cred,
                "carga_horaria": ch,
                "carga_horaria_semanal": ch // 20
            }
        )

    print("Criando Matriz ADS...")
    matriz_ads, _ = CurriculumMatrix.objects.get_or_create(
        curso=curso_ads_global,
        periodo_letivo="2026.1",
        turno="N",
        defaults={"nome": "Matriz ADS 2026", "is_vigente": True}
    )
    matriz_ads.unidades.add(unidade)

    ads_disciplinas = [
        (1, "PRG-1", "Programação Estruturada", 4, 80),
        (2, "FGE-V", "Inglês Instrumental", 2, 40),
        (3, "EXT-I", "Projeto de Extensão I", 0, 0),
        (4, "EXT-II", "Projeto de Extensão II", 0, 0),
        (5, "EXT-III", "Projeto de Extensão III", 4, 96),
    ]

    for periodo, cod, nome, cred, ch in ads_disciplinas:
        cc, _ = CurricularComponent.objects.get_or_create(nome=nome, defaults={"carga_horaria_padrao": ch})
        MatrixComponent.objects.get_or_create(
            matriz=matriz_ads,
            codigo=cod,
            defaults={
                "componente_curricular": cc,
                "periodo": periodo,
                "creditos": cred,
                "carga_horaria": ch,
                "carga_horaria_semanal": ch // 20 if ch > 0 else 0
            }
        )

    print("Seed finalizado!")

if __name__ == "__main__":
    seed_paracambi()
