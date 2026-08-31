#!/usr/bin/env python
"""
Script para inserir professores de teste no banco de dados.
Executa: python manage.py shell < seed_professores_teste.py
Ou: python manage.py shell
    >>> exec(open('seed_professores_teste.py').read())
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from apps.professors.models import Professor, ContractType
from apps.core.models import Unidade, Course
from faker import Faker
import random

fake = Faker('pt_BR')

# Pegar unidades disponíveis
unidades = Unidade.objects.all()
if not unidades.exists():
    print("❌ Nenhuma unidade encontrada. Crie unidades primeiro.")
    exit(1)

# Pegar tipos de contrato disponíveis
contratos = ContractType.objects.all()
if not contratos.exists():
    print("❌ Nenhum tipo de contrato encontrado. Crie tipos de contrato primeiro.")
    exit(1)

print(f"✅ Encontradas {unidades.count()} unidades")
print(f"✅ Encontrados {contratos.count()} tipos de contrato")

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
        print(f"⏭️  {prof_data['rh_nome']} já existe. Pulando...")
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
        cursos = Course.objects.filter(unidade=unidade)[:2]
        if cursos.exists():
            prof.cursos.set(cursos)
        
        print(f"✅ Professor '{prof.nome}' criado com sucesso!")
        created_count += 1
        
    except Exception as e:
        print(f"❌ Erro ao criar professor '{prof_data['rh_nome']}': {str(e)}")
        skipped_count += 1

print("\n" + "="*60)
print(f"📊 RESUMO:")
print(f"   ✅ Criados: {created_count}")
print(f"   ⏭️  Pulados: {skipped_count}")
print(f"   📈 Total de professores no BD: {Professor.objects.count()}")
print("="*60)
