import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from django.contrib.auth.hashers import make_password
from apps.accounts.models import DEFAULT_USER_PASSWORD, User
from apps.core.models import Unidade
from apps.professors.models import Professor, ContractType
from apps.courses.models import Course, CourseUnit, CurriculumMatrix, CurricularComponent, MatrixComponent
from seeds.helpers import update_or_create_professor


def seed_code(value):
    return value.replace("/", "-")


def run():
    print("Criando Unidade Paracambi...")
    unidade, created = Unidade.objects.get_or_create(
        nome="FAETERJ Paracambi",
        defaults={"sigla": "FAETERJ-PARACAMBI", "status": True}
    )
    if not created:
        unidade.status = True
        unidade.save()
    
    print("Criando Administrador DESUP...")
    desup_user, created = User.objects.get_or_create(
        email="coordenador@desup.com",
        defaults={
            "password": make_password(DEFAULT_USER_PASSWORD),
            "perfil": "DESUP",
            "unidade": None,
            "first_name": "Coordenador",
            "last_name": "DESUP",
            "is_superuser": False,
            "is_staff": True
        }
    )
    if not created:
        desup_user.password = make_password(DEFAULT_USER_PASSWORD)
        desup_user.perfil = "DESUP"
        desup_user.is_staff = True
        desup_user.save()

    print("Criando Coordenador da Unidade Paracambi...")
    unidade_user, created = User.objects.get_or_create(
        email="unidadeparacambi@desup.com",
        defaults={
            "password": make_password(DEFAULT_USER_PASSWORD),
            "perfil": "COORDENADOR_UNIDADE",
            "unidade": unidade,
            "first_name": "Coordenador",
            "last_name": "Paracambi",
            "is_superuser": False,
            "is_staff": False
        }
    )
    if not created:
        unidade_user.password = make_password(DEFAULT_USER_PASSWORD)
        unidade_user.perfil = "COORDENADOR_UNIDADE"
        unidade_user.unidade = unidade
        unidade_user.save()

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

    print("Criando Professores Reais...")
    professors_data = [
        ("51381966", "Adilson Ricardo da Silva", c_40h_i, "MECANICA"),
        ("51244861", "Alessandro de Almeida C. Cerqueira", c_40h_sup, "INFO"),
        ("44564465", "Artur Sergio Lopes", c_40h_sup, "INFO"),
        ("42052823", "Hudson dos Santos Barros", c_40h_sup, "INFO"),
        ("44119950", "Túlio Queto de Souza Pinto", c_40h_sup, "INFO"),
        ("N/A_1", "Cinthia da Silva Lisboa", c_doutorado, "QUIMICA"),
        ("N/A_2", "Daniel Vazquez Figueiredo", c_doutorado, "FORMACAO"),
        ("N/A_3", "Diego Mota Lima", c_doutorado, "INFO"),
        ("N/A_4", "Fabio Henrique S. dos Santos", c_doutorado, "INFO"),
        ("N/A_5", "Fausto Amaro da Silva Araujo", c_mestrado, "INFO"),
        ("N/A_6", "Franziska Huber", c_doutorado, "QUIMICA"),
        ("N/A_7", "Iamara da Silva Andrade", c_doutorado, "FORMACAO"),
        ("N/A_8", "Janaina da Silva Vettorazzi", c_doutorado, "FORMACAO"),
        ("N/A_9", "Kátia Regina Araújo da Silva", c_doutorado, "FORMACAO"),
        ("N/A_10", "Leonardo Pinheiro Gomes", c_mestrado, "INFO"),
        ("N/A_11", "Márcio de Brito Serafim", c_mestrado, "ADMIN"),
        ("N/A_12", "Marcia Lie Ayukawa", c_doutorado, "QUIMICA"),
        ("N/A_13", "Romilda Maria Alves Lemos", c_doutorado, "FORMACAO"),
        ("N/A_14", "Silvestre de Mello de Souza", c_especialista, "FORMACAO"),
        ("N/A_15", "Tereza Aparecida Ferreira Dornelas", c_doutorado, "FORMACAO"),
        ("N/A_16", "Carlos Eduardo Costa", c_doutorado, "FORMACAO"),
        ("N/A_17", "Elizangela Simões", c_mestrado, "FORMACAO"),
        ("N/A_18", "Henrique de Medeiros", c_doutorado, "FORMACAO"),
        ("N/A_19", "Paulo Calixto", c_especialista, "FORMACAO"),
        ("N/A_20", "Rubens Saviano", c_doutorado, "FORMACAO"),
        ("N/A_21", "Selma Gomes", c_ppc, "FORMACAO"),
    ]

    for matricula, nome, contrato, materia in professors_data:
        codigo = seed_code(matricula)
        # Se matricula for N/A_*, salvamos como null para testar o fluxo de matricula opcional
        if matricula.startswith("N/A"):
            rh_mat = None
        else:
            rh_mat = f"MAT-{codigo}"
            
            update_or_create_professor(
            id_funcional=f"IDF-{codigo}",
            rh_matricula=rh_mat,
            legacy_values=[matricula],
            defaults={
                "rh_nome": nome,
                "rh_email": f"{matricula}@faeterj.edu.br" if not matricula.startswith("N/A") else "sem_email@faeterj.edu.br",
                "tipo_contrato": contrato,
                "unidade_principal": unidade,
                "eixo": materia
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
        cc, _ = CurricularComponent.objects.get_or_create(
            nome=nome,
            defaults={"carga_horaria_padrao": ch, "codigo": cod}
        )
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
        cc, _ = CurricularComponent.objects.get_or_create(
            nome=nome,
            defaults={"carga_horaria_padrao": ch, "codigo": cod}
        )
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

    print("Seed Real finalizado!")


if __name__ == "__main__":
    run()
