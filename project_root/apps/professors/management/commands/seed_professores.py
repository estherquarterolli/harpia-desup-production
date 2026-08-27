from django.core.management.base import BaseCommand
from apps.professors.models import Professor, ContractType
from apps.core.models import Unidade
from apps.courses.models import CourseUnit
import random


class Command(BaseCommand):
    help = 'Insere professores de teste no banco de dados'

    def handle(self, *args, **options):
        # Pegar unidades disponíveis
        unidades = Unidade.objects.all()
        if not unidades.exists():
            self.stdout.write(self.style.ERROR('❌ Nenhuma unidade encontrada. Crie unidades primeiro.'))
            return

        # Pegar tipos de contrato disponíveis
        contratos = ContractType.objects.all()
        if not contratos.exists():
            self.stdout.write(self.style.ERROR('❌ Nenhum tipo de contrato encontrado. Crie tipos de contrato primeiro.'))
            return

        self.stdout.write(self.style.SUCCESS(f'✅ Encontradas {unidades.count()} unidades'))
        self.stdout.write(self.style.SUCCESS(f'✅ Encontrados {contratos.count()} tipos de contrato'))

        # Dados dos professores de teste
        professores_dados = [
            {
                'id_funcional': 'PROF001',
                'rh_matricula': 'MAT001',
                'rh_nome': 'Dr. João Silva',
                'rh_email': 'joao.silva@faetec.rj.gov.br',
                'materia': 'INFO',
                'ha': 30,
            },
            {
                'id_funcional': 'PROF002',
                'rh_matricula': 'MAT002',
                'rh_nome': 'Dra. Maria Santos',
                'rh_email': 'maria.santos@faetec.rj.gov.br',
                'materia': 'ELETRO',
                'ha': 20,
            },
            {
                'id_funcional': 'PROF003',
                'rh_matricula': 'MAT003',
                'rh_nome': 'Prof. Carlos Oliveira',
                'rh_email': 'carlos.oliveira@faetec.rj.gov.br',
                'materia': 'MECANICA',
                'ha': 40,
            },
            {
                'id_funcional': 'PROF004',
                'rh_matricula': 'MAT004',
                'rh_nome': 'Prof. Ana Costa',
                'rh_email': 'ana.costa@faetec.rj.gov.br',
                'materia': 'ADMIN',
                'ha': 25,
            },
            {
                'id_funcional': 'PROF005',
                'rh_matricula': 'MAT005',
                'rh_nome': 'Prof. Pedro Ferreira',
                'rh_email': 'pedro.ferreira@faetec.rj.gov.br',
                'materia': 'SAUDE',
                'ha': 28,
            },
            {
                'id_funcional': 'PROF006',
                'rh_matricula': 'MAT006',
                'rh_nome': 'Dra. Fernanda Gomes',
                'rh_email': 'fernanda.gomes@faetec.rj.gov.br',
                'materia': 'QUIMICA',
                'ha': 32,
            },
            {
                'id_funcional': 'PROF007',
                'rh_matricula': 'MAT007',
                'rh_nome': 'Prof. Roberto Lima',
                'rh_email': 'roberto.lima@faetec.rj.gov.br',
                'materia': 'FORMACAO',
                'ha': 20,
            },
            {
                'id_funcional': 'PROF008',
                'rh_matricula': 'MAT008',
                'rh_nome': 'Prof. Juliana Martins',
                'rh_email': 'juliana.martins@faetec.rj.gov.br',
                'materia': 'DESIGN',
                'ha': 25,
            },
            {
                'id_funcional': 'PROF009',
                'rh_matricula': 'MAT009',
                'rh_nome': 'Prof. Leonardo Dias',
                'rh_email': 'leonardo.dias@faetec.rj.gov.br',
                'materia': 'TELECOMUNICACOES',
                'ha': 30,
            },
            {
                'id_funcional': 'PROF010',
                'rh_matricula': 'MAT010',
                'rh_nome': 'Prof. Beatriz Rocha',
                'rh_email': 'beatriz.rocha@faetec.rj.gov.br',
                'materia': 'TURISMO',
                'ha': 22,
            },
        ]

        # Criar professores
        created_count = 0
        skipped_count = 0

        for prof_data in professores_dados:
            # Verificar se já existe
            if Professor.objects.filter(id_funcional=prof_data['id_funcional']).exists():
                self.stdout.write(f"⏭️  {prof_data['rh_nome']} já existe. Pulando...")
                skipped_count += 1
                continue
            
            # Pegar unidade e contrato aleatórios
            unidade = random.choice(unidades)
            contrato = random.choice(contratos)
            
            try:
                prof = Professor.objects.create(
                    id_funcional=prof_data['id_funcional'],
                    rh_matricula=prof_data['rh_matricula'],
                    rh_nome=prof_data['rh_nome'],
                    rh_email=prof_data['rh_email'],
                    unidade_principal=unidade,
                    tipo_contrato=contrato,
                    materia=prof_data['materia'],
                    ha=prof_data['ha'],
                    status='Ativo',
                )
                
                # Associar alguns cursos aleatoriamente
                cursos = CourseUnit.objects.filter(unidade=unidade)[:2]
                if cursos.exists():
                    prof.cursos.set(cursos)
                
                self.stdout.write(self.style.SUCCESS(f"✅ Professor '{prof.nome}' criado com sucesso!"))
                created_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erro ao criar professor '{prof_data['rh_nome']}': {str(e)}"))
                skipped_count += 1

        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"📊 RESUMO:"))
        self.stdout.write(self.style.SUCCESS(f"   ✅ Criados: {created_count}"))
        self.stdout.write(f"   ⏭️  Pulados: {skipped_count}")
        self.stdout.write(self.style.SUCCESS(f"   📈 Total de professores no BD: {Professor.objects.count()}"))
        self.stdout.write("="*60)
