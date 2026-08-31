import os
import sys
import django
import csv

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from apps.accounts.models import User
from apps.core.models import Unidade
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent

# --- 1. Create SuperAdmins and Admin ---
def create_global_users():
    print("Creating global users...")
    users_to_create = [
        {
            "email": "estagio.analista1@desup.faetec.rj.gov.br",
            "password": "@Eq122507@",
            "is_superuser": True,
            "is_staff": True,
            "perfil": "DESUP",
            "first_name": "SuperAdmin",
            "last_name": "Analista 1",
        },
        {
            "email": "estagio.analista2@desup.faetec.rj.gov.br",
            "password": "Faetec@123",
            "is_superuser": True,
            "is_staff": True,
            "perfil": "DESUP",
            "first_name": "SuperAdmin",
            "last_name": "Analista 2",
        },
        {
            "email": "alberto.alvaraes@desup.faetec.rj.gov.br",
            "password": "0@Aprisma",
            "is_superuser": False,
            "is_staff": True,
            "perfil": "DESUP",
            "first_name": "Admin",
            "last_name": "Alberto",
        }
    ]

    for u_data in users_to_create:
        email = u_data["email"]
        if not User.objects.filter(email=email).exists():
            user = User.objects.create_user(
                email=email,
                password=u_data["password"],
                first_name=u_data["first_name"],
                last_name=u_data["last_name"],
                perfil=u_data["perfil"],
                is_staff=u_data["is_staff"],
                is_superuser=u_data["is_superuser"],
                forcar_troca_senha=False
            )
            print(f"Created user: {email}")
        else:
            print(f"User {email} already exists.")

# --- 2. Process Unidades and CSVs ---
def process_unidades_and_csvs():
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "sensivel")
    if not os.path.exists(docs_dir):
        print(f"Directory not found: {docs_dir}")
        return

    csv_files = [f for f in os.listdir(docs_dir) if f.upper().endswith('.CSV')]

    for filename in csv_files:
        filepath = os.path.join(docs_dir, filename)
        print(f"\nProcessing {filename}...")
        
        rows = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = list(reader)
        except Exception as e:
            try:
                with open(filepath, 'r', encoding='latin1') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    rows = list(reader)
            except Exception as e2:
                print(f"Error reading {filename}: {e2}")
                continue

        if not rows:
            print(f"File {filename} is empty.")
            continue

        faculdade_name = str(rows[0].get('Faculdade', '')).strip()
        sigla = faculdade_name.split(' ')[0] + '-' + ''.join([word[0] for word in faculdade_name.split(' ')[1:] if word])
        if len(sigla) > 20:
            sigla = sigla[:20]

        # Determine email prefix from filename
        prefix = filename.split('.')[0].lower()
        if prefix.startswith('faeterj_'):
            prefix = prefix.replace('faeterj_', '')
        
        email_unidade = f"{prefix}.unidade@faeterj-pr.edu.br"

        # Create Unidade
        unidade, created = Unidade.objects.get_or_create(
            nome=faculdade_name,
            defaults={'sigla': sigla, 'status': True}
        )
        if created:
            print(f"Created Unidade: {faculdade_name}")
        
        # Create User for Unidade
        if not User.objects.filter(email=email_unidade).exists():
            User.objects.create_user(
                email=email_unidade,
                password="Faetec@123",
                first_name="Coordenador",
                last_name=prefix.capitalize(),
                perfil="COORDENADOR_UNIDADE",
                unidade=unidade,
                forcar_troca_senha=True
            )
            print(f"Created Unidade user: {email_unidade}")
        
        # Parse and populate Courses and Components
        for row in rows:
            curso_nome = str(row.get('Curso', '')).strip()
            periodo = str(row.get('Período', '')).strip()
            codigo = str(row.get('Código', '')).strip()
            disciplina = str(row.get('Disciplina', '')).strip()

            if not curso_nome or curso_nome == 'nan':
                continue

            # Create Course
            curso_global, _ = Course.objects.get_or_create(
                nome=curso_nome,
                defaults={'sigla': ''.join([w[0] for w in curso_nome.split() if len(w) > 2])[:10]}
            )
            curso, _ = CourseUnit.objects.get_or_create(curso=curso_global, unidade=unidade)

            # Create Matrix
            matriz, _ = CurriculumMatrix.objects.get_or_create(
                curso=curso,
                nome=f"Matriz {curso.sigla} 2024",
                defaults={
                    'is_vigente': True,
                    'periodo_letivo': '2024.1',
                    'turno': 'N',
                }
            )

            # Create Curricular Component
            if codigo == '-' or codigo == 'nan' or not codigo:
                # Generate a code if none provided
                codigo_comp = f"{curso.sigla}-{periodo}-{''.join([w[0] for w in disciplina.split() if len(w) > 2])[:3]}"
            else:
                codigo_comp = codigo

            componente, _ = CurricularComponent.objects.get_or_create(
                codigo=codigo_comp,
                defaults={
                    'nome': disciplina,
                    'carga_horaria_padrao': 80, # default
                    'creditos': 4, # default
                }
            )

            # Link Matrix Component
            MatrixComponent.objects.get_or_create(
                matriz=matriz,
                componente_curricular=componente,
                defaults={
                    'codigo': codigo_comp,
                    'periodo': f"{periodo}º Período",
                    'carga_horaria': 80,
                    'creditos': 4,
                    'status': 'SEM_PROFESSOR',
                }
            )

if __name__ == "__main__":
    create_global_users()
    process_unidades_and_csvs()
    print("\nData population completed successfully!")
