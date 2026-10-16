from django.core.management.base import BaseCommand
from django.db import transaction

from apps.professors.models import ContractType, Professor


CONTRATOS = {
    'PROF FAETEC ENS SUP 40H': {
        'categoria': ContractType.CategoriaChoices.EFETIVO,
        'regime_trabalho': '40h',
        'dias_presenca_obrigatorios': 3,
        'max_class_hours': 20,
        'max_total_hours': 40,
        'max_classes': 8,
    },
    'PROFESSOR FAETEC I 20 H': {
        'categoria': ContractType.CategoriaChoices.TERCEIRIZADO,
        'regime_trabalho': '20h',
        'dias_presenca_obrigatorios': 2,
        'max_class_hours': 10,
        'max_total_hours': 20,
        'max_classes': 4,
    },
    'PROFESSOR FAETEC I 40 H': {
        'categoria': ContractType.CategoriaChoices.CONCURSADO,
        'regime_trabalho': '40h',
        'dias_presenca_obrigatorios': 3,
        'max_class_hours': 20,
        'max_total_hours': 40,
        'max_classes': 8,
    },
    'PROFESSOR FAETEC II - 40 H/ QD SUPL': {
        'categoria': ContractType.CategoriaChoices.EFETIVO,
        'regime_trabalho': '40h',
        'dias_presenca_obrigatorios': 3,
        'max_class_hours': 20,
        'max_total_hours': 40,
        'max_classes': 8,
    },
    'PROFESSOR CEDIDO': {
        'categoria': ContractType.CategoriaChoices.EFETIVO,
        'regime_trabalho': '40h',
        'dias_presenca_obrigatorios': 3,
        'max_class_hours': 20,
        'max_total_hours': 40,
        'max_classes': 8,
    },
}


PROFESSORES = (
    {
        'id_funcional': 'TESTE-1001',
        'rh_matricula': '00-TESTE-1001',
        'rh_nome': 'Ana Beatriz Souza',
        'rh_email': 'ana.souza@teste.harpia.local',
        'cargo': 'PROF FAETEC ENS SUP 40H',
        'ha': 20,
        'nivel_ensino_origem': Professor.NivelEnsinoOrigemChoices.SUPERIOR,
    },
    {
        'id_funcional': 'TESTE-1002',
        'rh_matricula': '00-TESTE-1002',
        'rh_nome': 'Bruno Henrique Lima',
        'rh_email': 'bruno.lima@teste.harpia.local',
        'cargo': 'PROFESSOR FAETEC I 20 H',
        'ha': 10,
        'nivel_ensino_origem': Professor.NivelEnsinoOrigemChoices.MEDIO,
    },
    {
        'id_funcional': 'TESTE-1003',
        'rh_matricula': '00-TESTE-1003',
        'rh_nome': 'Carla Mendes Rocha',
        'rh_email': 'carla.rocha@teste.harpia.local',
        'cargo': 'PROFESSOR FAETEC I 40 H',
        'ha': 20,
        'nivel_ensino_origem': Professor.NivelEnsinoOrigemChoices.MEDIO,
    },
    {
        'id_funcional': 'TESTE-1004',
        'rh_matricula': '00-TESTE-1004',
        'rh_nome': 'Diego Almeida Costa',
        'rh_email': 'diego.costa@teste.harpia.local',
        'cargo': 'PROFESSOR FAETEC II - 40 H/ QD SUPL',
        'ha': 20,
        'nivel_ensino_origem': Professor.NivelEnsinoOrigemChoices.AMBOS,
    },
    {
        'id_funcional': 'TESTE-1005',
        'rh_matricula': '00-TESTE-1005',
        'rh_nome': 'Elisa Martins Nogueira',
        'rh_email': 'elisa.nogueira@teste.harpia.local',
        'cargo': 'PROFESSOR CEDIDO',
        'ha': 20,
        'nivel_ensino_origem': Professor.NivelEnsinoOrigemChoices.SUPERIOR,
        'is_cedido': True,
    },
)


class Command(BaseCommand):
    help = 'Cria professores de demonstração para validar as telas de consulta.'

    @transaction.atomic
    def handle(self, *args, **options):
        contratos = {}
        for nome, defaults in CONTRATOS.items():
            contrato = ContractType.objects.filter(nome=nome).order_by('pk').first()
            if contrato is None:
                contrato = ContractType.objects.create(nome=nome, **defaults)
            else:
                for campo, valor in defaults.items():
                    setattr(contrato, campo, valor)
                contrato.save(update_fields=list(defaults))
            contratos[nome] = contrato

        criados = 0
        atualizados = 0
        for dados in PROFESSORES:
            dados = dados.copy()
            cargo = dados.pop('cargo')
            professor, criado = Professor.objects.update_or_create(
                id_funcional=dados.pop('id_funcional'),
                defaults={
                    **dados,
                    'tipo_contrato': contratos[cargo],
                    'status': Professor.StatusChoices.ATIVO,
                },
            )
            criados += int(criado)
            atualizados += int(not criado)

        self.stdout.write(self.style.SUCCESS(
            f'Professores de teste prontos: {criados} criados e {atualizados} atualizados.'
        ))
