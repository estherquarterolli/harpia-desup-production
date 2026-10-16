from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.professors.models import ContractType, Professor

from .models import (
    AuditoriaGlobal,
    LimiteCargaUnidade,
    Notificacao,
    OcupacaoEquipeDiretiva,
    SolicitacaoProfessorExterno,
    TipoCargoDiretivo,
    Unidade,
)
from .priority1 import obter_resumo_prioridade1


class Prioridade1DesupTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.origem = Unidade.objects.create(nome="Unidade de Origem", sigla="UO")
        self.destino = Unidade.objects.create(nome="Unidade Solicitante", sigla="US")
        self.desup = User.objects.create_user(
            email="esther.desup@example.test",
            password="SenhaForte@123",
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.coordenador = User.objects.create_user(
            email="gestor.unidade@example.test",
            password="SenhaForte@123",
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.destino,
            forcar_troca_senha=False,
        )
        self.contrato = ContractType.objects.create(
            nome="PROF FAETEC ENS SUP 40H",
            categoria=ContractType.CategoriaChoices.EFETIVO,
            regime_trabalho="40h",
            dias_presenca_obrigatorios=3,
            max_class_hours=20,
            max_total_hours=40,
            max_classes=8,
        )
        self.professor = Professor.objects.create(
            id_funcional="P1-0001",
            rh_matricula="M1-0001",
            rh_nome="Professor de Teste",
            rh_email="professor@example.test",
            unidade_principal=self.origem,
            tipo_contrato=self.contrato,
        )
        self.professor.unidades.add(self.origem)

    def test_paginas_da_prioridade_um_sao_exclusivas_da_desup(self):
        urls = (
            reverse("core:equipe_diretiva_desup"),
            reverse("core:solicitacao_professor_list"),
            reverse("core:alertas_carga_desup"),
        )

        self.client.force_login(self.coordenador)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.desup)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_ocupacao_diretiva_impede_sobreposicao(self):
        cargo = TipoCargoDiretivo.objects.create(
            nome="Direção",
            codigo="DIRECAO",
            ordem=10,
        )
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem,
            cargo=cargo,
            professor=self.professor,
            data_inicio=self.hoje - timedelta(days=30),
            criado_por=self.desup,
        )
        conflitante = OcupacaoEquipeDiretiva(
            unidade=self.origem,
            cargo=cargo,
            professor=self.professor,
            data_inicio=self.hoje,
            criado_por=self.desup,
        )

        with self.assertRaises(ValidationError):
            conflitante.full_clean()

    def test_desup_ajusta_reducao_sem_alterar_ocupante_ou_unidade(self):
        cargo = TipoCargoDiretivo.objects.create(
            nome="Coordenação de Estágio",
            codigo="COORDENACAO_DE_ESTAGIO",
            ordem=60,
        )
        ocupacao = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem,
            cargo=cargo,
            professor=self.professor,
            data_inicio=self.hoje,
            criado_por=self.desup,
        )
        self.client.force_login(self.desup)

        resposta = self.client.post(
            reverse("core:ocupacao_diretiva_update", args=[ocupacao.pk]),
            {
                "carga_reducao_horas": "8.00",
                "observacoes": "Redução validada pela DESUP.",
                "unidade": self.destino.pk,
                "professor": 999999,
            },
        )

        self.assertRedirects(resposta, reverse("core:equipe_diretiva_desup"))
        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal("8.00"))
        self.assertEqual(ocupacao.unidade_id, self.origem.pk)
        self.assertEqual(ocupacao.professor_id, self.professor.pk)

    def test_limite_da_unidade_impede_periodos_sobrepostos(self):
        LimiteCargaUnidade.objects.create(
            unidade=self.origem,
            limite_horas_semanais=Decimal("120.00"),
            data_inicio=self.hoje - timedelta(days=15),
            criado_por=self.desup,
        )
        conflitante = LimiteCargaUnidade(
            unidade=self.origem,
            limite_horas_semanais=Decimal("140.00"),
            data_inicio=self.hoje,
            criado_por=self.desup,
        )

        with self.assertRaises(ValidationError):
            conflitante.full_clean()

    def test_resumo_inclui_professor_ativo_ainda_sem_alocacao(self):
        resumo = obter_resumo_prioridade1(
            unidade_id=self.origem.pk,
            semestre=f"{self.hoje.year}.1",
        )

        self.assertEqual(resumo["professores_alocados"], 0)
        self.assertEqual(resumo["professores_com_sobra"], 1)

    @patch("apps.core.services.send_email_task.delay")
    def test_aprovacao_vincula_professor_notifica_e_audita(self, email_delay):
        solicitacao = SolicitacaoProfessorExterno.objects.create(
            unidade_solicitante=self.destino,
            unidade_origem=self.origem,
            professor=self.professor,
            semestre=f"{self.hoje.year}.1",
            justificativa="Necessidade acadêmica temporária.",
            solicitado_por=self.coordenador,
        )
        self.client.force_login(self.desup)

        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(
                reverse("core:solicitacao_professor_decidir", args=[solicitacao.pk]),
                {"decisao": "APROVADA", "motivo_decisao": ""},
            )

        self.assertRedirects(resposta, reverse("core:solicitacao_professor_list"))
        solicitacao.refresh_from_db()
        self.assertEqual(solicitacao.status, SolicitacaoProfessorExterno.StatusChoices.APROVADA)
        self.assertTrue(self.professor.unidades.filter(pk=self.destino.pk).exists())
        self.assertTrue(Notificacao.objects.filter(unidade_destino=self.destino).exists())
        self.assertTrue(
            AuditoriaGlobal.objects.filter(
                usuario=self.desup,
                acao="SOLICITACAO_PROFESSOR_DECIDIDA",
            ).exists()
        )
        email_delay.assert_called_once()

        resposta_repetida = self.client.post(
            reverse("core:solicitacao_professor_decidir", args=[solicitacao.pk]),
            {"decisao": "RECUSADA", "motivo_decisao": "Tentativa repetida."},
        )
        self.assertEqual(resposta_repetida.status_code, 302)
        solicitacao.refresh_from_db()
        self.assertEqual(solicitacao.status, SolicitacaoProfessorExterno.StatusChoices.APROVADA)

    def test_recusa_exige_motivo(self):
        solicitacao = SolicitacaoProfessorExterno.objects.create(
            unidade_solicitante=self.destino,
            unidade_origem=self.origem,
            professor=self.professor,
            semestre=f"{self.hoje.year}.2",
            justificativa="Necessidade acadêmica temporária.",
            solicitado_por=self.coordenador,
        )
        self.client.force_login(self.desup)
        resposta = self.client.post(
            reverse("core:solicitacao_professor_decidir", args=[solicitacao.pk]),
            {"decisao": "RECUSADA", "motivo_decisao": ""},
        )

        self.assertEqual(resposta.status_code, 302)
        solicitacao.refresh_from_db()
        self.assertEqual(solicitacao.status, SolicitacaoProfessorExterno.StatusChoices.PENDENTE)

