"""
Seed para gerar dados de professores fictícios e seguros para demonstração local.
Garante que não existam dados reais ou sensíveis de professores no banco de dados.

Uso:
    python seeds/seed_professores_ficticios.py
"""
import os
import sys
import random
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.db import transaction
from apps.core.models import Unidade
from apps.professors.models import ContractType, Professor
from seeds.helpers import update_or_create_professor

# Listas de nomes fictícios para gerar combinações brasileiras realistas
NOMES = [
    "Ana", "Bruno", "Carlos", "Daniela", "Eduardo", "Fernanda", "Gabriel", "Helena",
    "Igor", "Juliana", "Lucas", "Mariana", "Neto", "Olívia", "Pedro", "Patrícia",
    "Renato", "Sofia", "Thiago", "Beatriz", "Ricardo", "Camila", "André", "Letícia"
]

SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira",
    "Gomes", "Ribeiro", "Carvalho", "Almeida", "Costa", "Rocha", "Nascimento", "Araújo",
    "Melo", "Barbosa", "Cardoso", "Teixeira", "Martins", "Lima", "Dias", "Moreira"
]

MATERIAS = ["INFO", "ELETRO", "MECANICA", "ADMIN", "SAUDE", "QUIMICA", "DESIGN", "TELECOMUNICACOES", "TURISMO", "FORMACAO"]

@transaction.atomic
def run():
    print("=" * 60)
    print("  SEED DE PROFESSORES FICTÍCIOS (DEMONSTRAÇÃO EVENTO)")
    print("=" * 60)

    # 1. Obter ou criar Unidade caso não exista nenhuma
    unidades = list(Unidade.objects.all())
    if not unidades:
        print("[!] Nenhuma unidade encontrada. Criando Unidade Demonstrativa...")
        u, _ = Unidade.objects.get_or_create(
            sigla="FAETEC-DEMO",
            defaults={"nome": "Unidade Demonstrativa RIW", "status": True}
        )
        unidades = [u]
    print(f"-> Unidades disponíveis: {len(unidades)}")

    # 2. Obter ou criar tipos de contrato básicos
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
    contratos = [contrato_40h, contrato_20h]
    print(f"-> Contratos garantidos: {len(contratos)}")

    # 3. Gerar professores fictícios
    professores_criados = 0
    utilizados = set()

    print("-> Gerando professores fictícios...")
    for i in range(1, 51):  # Gerando 50 professores fictícios
        # Garantir combinação de nome única
        while True:
            nome = f"{random.choice(NOMES)} {random.choice(SOBRENOMES)} {random.choice(SOBRENOMES)}"
            if nome not in utilizados:
                utilizados.add(nome)
                break
        
        id_func = f"IDF-{1000 + i}"
        mat = f"MAT-{5000 + i}"
        email = f"{nome.lower().replace(' ', '.')}@faetec.rj.gov.br"
        
        # Remove acentos e caracteres especiais simples para o email
        import unicodedata
        email = ''.join(c for c in unicodedata.normalize('NFD', email) if unicodedata.category(c) != 'Mn')

        unidade = random.choice(unidades)
        contrato = random.choice(contratos)
        ha_horas = random.choice([20, 24, 28, 30, 32, 40])
        materia = random.choice(MATERIAS)

        _, created = update_or_create_professor(
            id_funcional=id_func,
            rh_matricula=mat,
            legacy_values=[id_func, mat],
            defaults=dict(
                rh_nome=nome,
                rh_email=email,
                unidade_principal=unidade,
                tipo_contrato=contrato,
                materia=materia,
                ha=ha_horas,
                status="Ativo"
            )
        )
        if created:
            professores_criados += 1

    print(f"[OK] {professores_criados} professores fictícios criados/atualizados com sucesso!")
    print(f"Total de professores no banco: {Professor.objects.count()}")

if __name__ == "__main__":
    run()
