"""Popula o banco local com unidades, cursos, professores e equipe diretiva de teste.

Uso: python manage.py seed_dados_teste

Idempotente: pode ser executado várias vezes sem duplicar registros. Todos os
dados criados usam o prefixo TESTE para facilitar a identificação e a limpeza.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, CourseUnit
from apps.professors.models import ContractType, Professor

from apps.core.models import (
    ExcecaoCargaUnidade,
    LimiteCargaUnidade,
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
    TipoCargoDiretivo,
    Unidade,
)


UNIDADES = (
    ("TST-ISTCC", "Instituto Superior de Tecnologia em Ciência da Computação (Teste)", ("ADS-T", "SI-T")),
    ("TST-ISERJ", "Instituto Superior de Educação do Rio de Janeiro (Teste)", ("PED-T", "LET-T", "MAT-T")),
    ("TST-ISEPAM", "Instituto Superior de Educação Professor Aldo Muylaert (Teste)", ("PED-T", "BIO-T")),
    ("TST-ISTRIO", "Instituto Superior de Tecnologia do Rio (Teste)", ("ADS-T", "GTI-T")),
    ("TST-ISEABV", "Instituto Superior de Educação de Bom Jesus (Teste)", ("PED-T", "MAT-T")),
)

CURSOS = {
    "ADS-T": "Análise e Desenvolvimento de Sistemas (Teste)",
    "SI-T": "Sistemas de Informação (Teste)",
    "GTI-T": "Gestão da Tecnologia da Informação (Teste)",
    "PED-T": "Pedagogia (Teste)",
    "LET-T": "Letras (Teste)",
    "MAT-T": "Matemática (Teste)",
    "BIO-T": "Ciências Biológicas (Teste)",
}

CONTRATOS = {
    "PROF FAETEC ENS SUP 40H": dict(categoria=ContractType.CategoriaChoices.EFETIVO, regime_trabalho="40h",
                                    dias_presenca_obrigatorios=3, max_class_hours=20, max_total_hours=40, max_classes=8),
    "PROFESSOR FAETEC I 20 H": dict(categoria=ContractType.CategoriaChoices.TERCEIRIZADO, regime_trabalho="20h",
                                    dias_presenca_obrigatorios=2, max_class_hours=10, max_total_hours=20, max_classes=4),
    "PROFESSOR FAETEC I 40 H": dict(categoria=ContractType.CategoriaChoices.CONCURSADO, regime_trabalho="40h",
                                    dias_presenca_obrigatorios=3, max_class_hours=20, max_total_hours=40, max_classes=8),
    "PROFESSOR FAETEC II - 40 H/ QD SUPL": dict(categoria=ContractType.CategoriaChoices.EFETIVO, regime_trabalho="40h",
                                                dias_presenca_obrigatorios=3, max_class_hours=20, max_total_hours=40, max_classes=8),
    "PROFESSOR CEDIDO": dict(categoria=ContractType.CategoriaChoices.EFETIVO, regime_trabalho="40h",
                             dias_presenca_obrigatorios=3, max_class_hours=20, max_total_hours=40, max_classes=8),
}

NOMES = (
    "Adriana Pereira Gomes", "Alexandre Ribeiro Dias", "Beatriz Carvalho Lopes", "Caio Fernandes Moura",
    "Camila Teixeira Barros", "Daniel Azevedo Pinto", "Débora Cunha Ramos", "Eduardo Santana Freitas",
    "Fabiana Monteiro Reis", "Felipe Duarte Cardoso", "Gabriela Nunes Araújo", "Gustavo Correia Vieira",
    "Helena Batista Rocha", "Igor Marques Campos", "Isabela Farias Mendes", "João Pedro Castro",
    "Juliana Moreira Lima", "Leonardo Prado Souza", "Luciana Brandão Alves", "Marcelo Tavares Silva",
    "Mariana Costa Rezende", "Nathalia Gonçalves Melo", "Otávio Rangel Barbosa", "Patrícia Lacerda Fonseca",
    "Rafael Siqueira Braga", "Renata Pacheco Moraes", "Rodrigo Antunes Leal", "Sabrina Queiroz Peixoto",
    "Thiago Vasconcelos Rios", "Vanessa Dantas Coelho", "Vinícius Borges Neves", "Yasmin Toledo Fragoso",
    "André Luiz Machado", "Cristiane Viana Matos", "Fernando Albuquerque Paiva", "Larissa Guimarães Sales",
)

NIVEIS = (
    Professor.NivelEnsinoOrigemChoices.SUPERIOR,
    Professor.NivelEnsinoOrigemChoices.SUPERIOR,
    Professor.NivelEnsinoOrigemChoices.MEDIO,
    Professor.NivelEnsinoOrigemChoices.AMBOS,
)

# Composição diretiva preenchida apenas nas duas primeiras unidades, para que as
# demais apareçam com cargos vagos. (código do cargo, índice do professor na unidade, redução semanal)
EQUIPES = {
    "TST-ISTCC": (("DIRECAO", 0, "20"), ("VICE_DIRECAO", 1, "12"), ("SECRETARIA", 2, "8"),
                  ("COORDENACAO_DE_CURSO", 3, "10")),
    "TST-ISERJ": (("DIRECAO", 0, "20"), ("COORDENACAO_DE_CURSO", 1, "10"),
                  ("COORDENACAO_DE_ESTAGIO", 2, "6")),
}

# Senha dos usuários de teste criados por este comando (somente ambiente local).
SENHA_TESTE = "Teste@2026"

LIMITES = {"TST-ISTCC": "160", "TST-ISERJ": "220", "TST-ISTRIO": "40"}


class Command(BaseCommand):
    help = "Cria unidades, cursos, professores e equipe diretiva de teste para uso local."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Comando restrito ao ambiente de desenvolvimento (DEBUG=True).")
        with transaction.atomic():
            resumo = self._popular()
        self.stdout.write(self.style.SUCCESS(
            "Dados de teste prontos: "
            + ", ".join(f"{valor} {chave}" for chave, valor in resumo.items())
        ))

    def _popular(self):
        hoje = timezone.localdate()

        contratos = {}
        for nome, valores in CONTRATOS.items():
            contrato = ContractType.objects.filter(nome=nome).order_by("pk").first()
            contratos[nome] = contrato or ContractType.objects.create(nome=nome, **valores)
        lista_contratos = list(contratos.values())

        cursos = {
            sigla: Course.objects.get_or_create(sigla=sigla, defaults={"nome": nome})[0]
            for sigla, nome in CURSOS.items()
        }

        unidades = {}
        cursos_unidade = {}
        for sigla, nome, siglas_curso in UNIDADES:
            unidade, _ = Unidade.objects.get_or_create(nome=nome, defaults={"sigla": sigla, "status": True})
            unidades[sigla] = unidade
            cursos_unidade[sigla] = [
                CourseUnit.objects.get_or_create(curso=cursos[c], unidade=unidade)[0] for c in siglas_curso
            ]

        professores_por_unidade = {sigla: [] for sigla in unidades}
        siglas = list(unidades)
        for indice, nome in enumerate(NOMES):
            sigla = siglas[indice % len(siglas)]
            unidade = unidades[sigla]
            contrato = lista_contratos[indice % len(lista_contratos)]
            professor, _ = Professor.objects.update_or_create(
                id_funcional=f"TESTE-{2001 + indice}",
                defaults={
                    "rh_matricula": f"00-TESTE-{2001 + indice}",
                    "rh_nome": nome,
                    "rh_email": f"teste{2001 + indice}@teste.harpia.local",
                    "unidade_principal": unidade,
                    "tipo_contrato": contrato,
                    "ha": contrato.max_class_hours,
                    "status": Professor.StatusChoices.ATIVO,
                    "nivel_ensino_origem": NIVEIS[indice % len(NIVEIS)],
                    "is_cedido": contrato.nome == "PROFESSOR CEDIDO",
                },
            )
            professor.unidades.add(unidade)
            # Alguns professores atuam em uma segunda unidade.
            if indice % 6 == 0:
                professor.unidades.add(unidades[siglas[(indice + 1) % len(siglas)]])
            professor.cursos.add(*[cu.curso for cu in cursos_unidade[sigla][:1]])
            professores_por_unidade[sigla].append(professor)

        # Professores do seed anterior (TESTE-100x) passam a ter unidade.
        for indice, professor in enumerate(Professor.objects.filter(id_funcional__startswith="TESTE-100")):
            unidade = unidades[siglas[indice % len(siglas)]]
            if not professor.unidade_principal_id:
                professor.unidade_principal = unidade
                professor.save(update_fields=["unidade_principal"])
            professor.unidades.add(unidade)

        desup = User.objects.filter(perfil=User.Perfil.DESUP).order_by("pk").first()
        cargos = {cargo.codigo: cargo for cargo in TipoCargoDiretivo.objects.all()}
        ocupacoes = 0
        for sigla, itens in EQUIPES.items():
            unidade = unidades[sigla]
            for codigo, indice_prof, reducao in itens:
                cargo = cargos.get(codigo)
                if cargo is None:
                    continue
                curso = cursos_unidade[sigla][0] if cargo.exige_curso else None
                _, criada = OcupacaoEquipeDiretiva.objects.get_or_create(
                    unidade=unidade,
                    cargo=cargo,
                    curso=curso,
                    data_fim=None,
                    defaults={
                        "professor": professores_por_unidade[sigla][indice_prof],
                        "data_inicio": hoje - timedelta(days=180),
                        "carga_reducao_horas": Decimal(reducao),
                        "criado_por": desup,
                    },
                )
                ocupacoes += int(criada)

        for sigla, horas in LIMITES.items():
            unidade = unidades[sigla]
            if not LimiteCargaUnidade.objects.filter(unidade=unidade).exists():
                LimiteCargaUnidade.objects.create(
                    unidade=unidade, limite_horas_semanais=Decimal(horas),
                    data_inicio=hoje - timedelta(days=60), criado_por=desup,
                    observacoes="Teto de teste.",
                )

        readaptado = professores_por_unidade["TST-ISEPAM"][0]
        if not ReadaptacaoProfessor.objects.filter(professor=readaptado).exists():
            ReadaptacaoProfessor.objects.create(
                professor=readaptado, data_inicio=hoje - timedelta(days=30),
                justificativa_administrativa="Readaptação funcional de teste.", criado_por=desup,
            )

        # Um coordenador por unidade de teste. A senha só é definida na criação,
        # para não sobrescrever uma troca feita depois.
        coordenadores = 0
        for sigla, unidade in unidades.items():
            email = f"coord.{sigla.removeprefix('TST-').lower()}@teste.harpia.local"
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(
                    email=email,
                    password=SENHA_TESTE,
                    perfil=User.Perfil.COORDENADOR_UNIDADE,
                    unidade=unidade,
                    forcar_troca_senha=False,
                )
                coordenadores += 1

        solicitante = User.objects.filter(
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=unidades["TST-ISTRIO"],
        ).first() or desup
        if solicitante and not ExcecaoCargaUnidade.objects.filter(unidade=unidades["TST-ISTRIO"]).exists():
            ExcecaoCargaUnidade.objects.create(
                unidade=unidades["TST-ISTRIO"], horas_adicionais=Decimal("12"),
                data_inicio=hoje, data_fim=hoje + timedelta(days=120),
                justificativa="Abertura de turma extra de ADS no semestre (teste).",
                solicitado_por=solicitante,
            )

        return {
            "unidades": len(unidades),
            "cursos": len(cursos),
            "professores": len(NOMES),
            "ocupações novas": ocupacoes,
            "coordenadores novos": coordenadores,
        }
