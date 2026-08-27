# project_root/seeds/seed_multi_unit.py
import os, sys, django
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.core.models import Unidade
from apps.professors.models import Professor, ContractType
from apps.courses.models import Course, CourseUnit, MatrixComponent, CurriculumMatrix, CurricularComponent

def run():
    u1, _ = Unidade.objects.get_or_create(nome="Unidade A", sigla="UNA", status=True)
    u2, _ = Unidade.objects.get_or_create(nome="Unidade B", sigla="UNB", status=True)
    ct, _ = ContractType.objects.get_or_create(
        nome="Efetivo", 
        defaults={'max_class_hours': 20, 'max_classes': 10, 'max_total_hours': 40}
    )
    
    curso1_global, _ = Course.objects.get_or_create(nome="Curso A", sigla="CA")
    curso2_global, _ = Course.objects.get_or_create(nome="Curso B", sigla="CB")
    curso1, _ = CourseUnit.objects.get_or_create(curso=curso1_global, unidade=u1)
    curso2, _ = CourseUnit.objects.get_or_create(curso=curso2_global, unidade=u2)
    
    m1, _ = CurriculumMatrix.objects.get_or_create(curso=curso1, nome="Matriz A", is_vigente=True)
    m2, _ = CurriculumMatrix.objects.get_or_create(curso=curso2, nome="Matriz B", is_vigente=True)
    
    for i in range(1, 6):
        # Cada professor precisa de um componente único na matriz para evitar violação de unique_together
        comp1, _ = CurricularComponent.objects.get_or_create(
            nome=f"Matemática {i}", 
            sigla=f"MAT{i}",
            defaults={'carga_horaria_padrao': 80}
        )
        comp2, _ = CurricularComponent.objects.get_or_create(
            nome=f"Física {i}", 
            sigla=f"FIS{i}",
            defaults={'carga_horaria_padrao': 80}
        )
        
        p, _ = Professor.objects.get_or_create(
            id_funcional=f"IDF-{i}",
            rh_matricula=f"MAT-{i}",
            defaults={'rh_nome': f"Professor {i}", 'rh_email': f"p{i}@test.com", 'unidade_principal': u1, 'tipo_contrato': ct}
        )
        # Aloca na Unidade A
        MatrixComponent.objects.get_or_create(
            matriz=m1, 
            componente_curricular=comp1, 
            defaults={'docente': p, 'carga_horaria': 4}
        )
        # Aloca na Unidade B
        MatrixComponent.objects.get_or_create(
            matriz=m2, 
            componente_curricular=comp2, 
            defaults={'docente': p, 'carga_horaria': 4}
        )

if __name__ == "__main__":
    run()
