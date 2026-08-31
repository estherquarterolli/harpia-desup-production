import os
import sys
from pathlib import Path
import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.accounts.models import DEFAULT_USER_PASSWORD, User
from apps.core.models import Unidade
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent
from apps.professors.models import ContractType, Professor
from seeds.helpers import update_or_create_professor


def get_or_create_component(nome, sigla, carga_horaria_padrao, creditos):
    componente = CurricularComponent.objects.filter(sigla=sigla, nome=nome).first()
    if componente:
        return componente
    return CurricularComponent.objects.create(
        nome=nome,
        sigla=sigla,
        carga_horaria_padrao=carga_horaria_padrao,
        creditos=creditos,
    )


def run():
    print("Criando Unidade...")
    unidade, _ = Unidade.objects.get_or_create(nome="Faculdade de Tecnologia", sigla="FATEC", status=True)

    print("Criando Admin DESUP (não superuser)...")
    if not User.objects.filter(email='coordenador@desup.com').exists():
        admin = User.objects.create_user(
            email='coordenador@desup.com',
            password=DEFAULT_USER_PASSWORD,
            perfil='DESUP',
            unidade=unidade,
            first_name='Coordenador',
            last_name='DESUP',
            is_superuser=False,
            is_staff=False
        )
    else:
        admin = User.objects.get(email='coordenador@desup.com')

    print("Criando Contrato...")
    contrato, _ = ContractType.objects.get_or_create(
        nome="Ensino Superior", 
        regime_trabalho="40h", 
        max_class_hours=20, 
        max_total_hours=40, 
        max_classes=5
    )

    print("Criando Professores...")
    prof1, _ = update_or_create_professor(
        id_funcional="IDF-1001",
        rh_matricula="MAT-1001",
        legacy_values=["1001"],
        defaults=dict(
            rh_nome="João Silva",
            rh_email="joao@example.com",
            unidade_principal=unidade,
            tipo_contrato=contrato,
        )
    )
    
    prof2, _ = update_or_create_professor(
        id_funcional="IDF-1002",
        rh_matricula="MAT-1002",
        legacy_values=["1002"],
        defaults=dict(
            rh_nome="Maria Souza",
            rh_email="maria@example.com",
            unidade_principal=unidade,
            tipo_contrato=contrato,
        )
    )

    print("Criando Curso...")
    curso_global, _ = Course.objects.get_or_create(
        nome="Análise e Desenvolvimento de Sistemas",
        sigla="ADS"
    )
    curso_unit, _ = CourseUnit.objects.get_or_create(
        curso=curso_global,
        unidade=unidade
    )

    print("Criando Componentes Curriculares...")
    comp1 = get_or_create_component("Programação Orientada a Objetos", "POO", 80, 4)
    comp2 = get_or_create_component("Banco de Dados", "BD", 80, 4)

    print("Criando Matrizes Curriculares...")
    matriz = CurriculumMatrix.objects.filter(curso=curso_unit).first()
    if not matriz:
        matriz = CurriculumMatrix.objects.create(curso=curso_unit, nome='Matriz 2026.1', is_vigente=True)
    
    print("Vinculando Componentes à Matriz...")
    MatrixComponent.objects.get_or_create(
        matriz=matriz,
        componente_curricular=comp1,
        periodo="1º Semestre",
        carga_horaria=80,
        creditos=4,
        docente=prof1
    )
    MatrixComponent.objects.get_or_create(
        matriz=matriz,
        componente_curricular=comp2,
        periodo="1º Semestre",
        carga_horaria=80,
        creditos=4,
        docente=prof2
    )

    print("Dados criados com sucesso!")

if __name__ == '__main__':
    run()
