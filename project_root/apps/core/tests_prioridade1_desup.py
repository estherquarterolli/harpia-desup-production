from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, CourseUnit
from apps.professors.models import ContractType, Professor

from .models import (
    AuditoriaGlobal,
    ExcecaoCargaUnidade,
    LimiteCargaUnidade,
    Notificacao,
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
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
        cargo = TipoCargoDiretivo.objects.create(nome="Cargo para teste", codigo="CARGO_TESTE")
        urls = (
            reverse("core:equipe_diretiva_desup"),
            reverse("core:solicitacao_professor_list"),
            reverse("core:alertas_carga_desup"),
        )
        url_excluir_cargo = reverse("core:cargo_diretivo_delete", args=[cargo.pk])

        self.client.force_login(self.coordenador)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url_excluir_cargo).status_code, 403)

        self.client.force_login(self.desup)
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_formulario_de_cargo_por_curso_lista_cursos_ativos_da_unidade(self):
        from .forms import OcupacaoEquipeDiretivaForm

        curso = Course.objects.create(nome="Curso de Teste", sigla="CT")
        curso_unidade = CourseUnit.objects.create(curso=curso, unidade=self.origem)
        cargo = TipoCargoDiretivo.objects.create(
            nome="Coordenação por Curso",
            codigo="COORDENACAO_POR_CURSO",
            exige_curso=True,
        )

        form = OcupacaoEquipeDiretivaForm(unidade=self.origem, cargo=cargo)

        self.assertTrue(form.fields["curso"].required)
        self.assertEqual(list(form.fields["curso"].queryset), [curso_unidade])
        self.assertEqual(form.fields["curso"].label, "Curso")
        self.assertIn("curso ativo desta unidade", form.fields["curso"].help_text)

    def test_formulario_informa_quando_unidade_nao_tem_curso_ativo(self):
        from .forms import OcupacaoEquipeDiretivaForm

        cargo = TipoCargoDiretivo.objects.create(
            nome="Coordenação sem Curso Ativo",
            codigo="COORDENACAO_SEM_CURSO_ATIVO",
            exige_curso=True,
        )

        form = OcupacaoEquipeDiretivaForm(unidade=self.origem, cargo=cargo)

        self.assertEqual(form.fields["curso"].queryset.count(), 0)
        self.assertIn("Nenhum curso ativo cadastrado", form.fields["curso"].help_text)

    def test_configuracao_de_cargo_nao_exibe_ordem_ou_catalogo_de_cursos(self):
        curso = Course.objects.create(nome="Curso Oculto", sigla="CO")
        CourseUnit.objects.create(curso=curso, unidade=self.origem)
        cargo = TipoCargoDiretivo.objects.create(
            nome="Coordenação de Curso sem Catálogo",
            codigo="COORDENACAO_SEM_CATALOGO",
            exige_curso=True,
        )
        self.client.force_login(self.desup)

        resposta = self.client.get(
            f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}"
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Ordem de exibição")
        self.assertNotContains(resposta, "Cursos ativos por unidade")

    def test_desup_exclui_cargo_sem_ocupacoes(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Cargo Excluível", codigo="EXCLUIVEL")
        self.client.force_login(self.desup)

        resposta = self.client.post(
            reverse("core:cargo_diretivo_delete", args=[cargo.pk]),
            {"next": f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}"},
        )

        self.assertRedirects(
            resposta,
            f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}",
        )
        self.assertFalse(TipoCargoDiretivo.objects.filter(pk=cargo.pk).exists())

    def test_cargo_com_ocupantes_pode_ser_excluido_junto_com_as_ocupacoes(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Cargo com Histórico", codigo="COM_HISTORICO")
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem,
            cargo=cargo,
            professor=self.professor,
            data_inicio=self.hoje,
            criado_por=self.desup,
        )
        self.client.force_login(self.desup)

        resposta = self.client.post(
            reverse("core:cargo_diretivo_delete", args=[cargo.pk]),
        )

        self.assertRedirects(resposta, reverse("core:equipe_diretiva_desup"))
        self.assertFalse(TipoCargoDiretivo.objects.filter(pk=cargo.pk).exists())
        self.assertFalse(OcupacaoEquipeDiretiva.objects.filter(cargo_id=cargo.pk).exists())
        # A pessoa e a unidade continuam cadastradas: só a ocupação do cargo some.
        self.assertTrue(Professor.objects.filter(pk=self.professor.pk).exists())

    def test_modal_de_edicao_oferece_excluir_mesmo_com_ocupantes(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Cargo Preenchido", codigo="PREENCHIDO")
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem, cargo=cargo, professor=self.professor,
            data_inicio=self.hoje, criado_por=self.desup,
        )
        self.client.force_login(self.desup)

        resposta = self.client.get(
            f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}"
        )

        self.assertContains(resposta, reverse("core:cargo_diretivo_delete", args=[cargo.pk]))
        self.assertContains(resposta, "Excluir cargo")
        self.assertNotContains(resposta, "não pode ser excluído")

    def test_ocupacoes_de_outro_cargo_nao_sao_afetadas_pela_exclusao(self):
        excluido = TipoCargoDiretivo.objects.create(nome="Cargo A", codigo="CARGO_A")
        mantido = TipoCargoDiretivo.objects.create(nome="Cargo B", codigo="CARGO_B")
        for cargo in (excluido, mantido):
            OcupacaoEquipeDiretiva.objects.create(
                unidade=self.origem, cargo=cargo, professor=self.professor,
                data_inicio=self.hoje, criado_por=self.desup,
            )
        self.client.force_login(self.desup)

        self.client.post(reverse("core:cargo_diretivo_delete", args=[excluido.pk]))

        self.assertEqual(OcupacaoEquipeDiretiva.objects.filter(cargo=mantido).count(), 1)

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

    def test_cargo_sem_multiplos_bloqueia_outra_ocupacao_em_outro_curso(self):
        curso_a = Course.objects.create(nome="Curso A", sigla="CA")
        curso_b = Course.objects.create(nome="Curso B", sigla="CB")
        course_unit_a = CourseUnit.objects.create(curso=curso_a, unidade=self.origem)
        course_unit_b = CourseUnit.objects.create(curso=curso_b, unidade=self.origem)
        cargo = TipoCargoDiretivo.objects.create(
            nome="Coordenação exclusiva por curso",
            codigo="COORDENACAO_EXCLUSIVA",
            exige_curso=True,
            permite_multiplos=False,
        )
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem,
            cargo=cargo,
            professor=self.professor,
            curso=course_unit_a,
            data_inicio=self.hoje,
            criado_por=self.desup,
        )
        self.client.force_login(self.desup)
        resposta = self.client.get(
            f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}"
        )
        item_cargo = next(
            item for item in resposta.context["composicao"]
            if item["cargo"].pk == cargo.pk
        )
        self.assertFalse(item_cargo["pode_adicionar"])
        self.assertNotIn("form", item_cargo)

        segunda_ocupacao = OcupacaoEquipeDiretiva(
            unidade=self.origem,
            cargo=cargo,
            professor=self.professor,
            curso=course_unit_b,
            data_inicio=self.hoje,
            criado_por=self.desup,
        )

        with self.assertRaises(ValidationError):
            segunda_ocupacao.full_clean()

    def test_formulario_de_cargo_oculta_ordem_de_exibicao(self):
        from .forms import TipoCargoDiretivoForm

        form = TipoCargoDiretivoForm()

        self.assertNotIn("ordem", form.fields)

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

    def test_desup_preenche_cargo_da_unidade_e_ve_reducao_total(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Direção", codigo="DIRECAO", ordem=10)
        self.client.force_login(self.desup)
        retorno = f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}"

        resposta = self.client.post(
            reverse("core:ocupacao_diretiva_create", args=[self.origem.pk, cargo.pk]),
            {
                "professor": self.professor.pk,
                "data_inicio": self.hoje.isoformat(),
                "carga_reducao_horas": "12.00",
                "observacoes": "",
                "next": retorno,
            },
        )

        self.assertRedirects(resposta, retorno)
        ocupacao = OcupacaoEquipeDiretiva.objects.get()
        self.assertEqual(ocupacao.unidade_id, self.origem.pk)
        self.assertEqual(ocupacao.cargo_id, cargo.pk)
        self.assertEqual(ocupacao.criado_por, self.desup)

        pagina = self.client.get(retorno)
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context["reducao_total"], Decimal("12.00"))
        self.assertFalse(pagina.context["composicao"][0]["pode_adicionar"])
        self.assertNotContains(pagina, "Prioridade 1")

    def test_preencher_cargo_rejeita_servidor_de_outra_unidade(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Direção", codigo="DIRECAO", ordem=10)
        self.client.force_login(self.desup)

        resposta = self.client.post(
            reverse("core:ocupacao_diretiva_create", args=[self.destino.pk, cargo.pk]),
            {"professor": self.professor.pk, "data_inicio": self.hoje.isoformat(), "carga_reducao_horas": "4"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(OcupacaoEquipeDiretiva.objects.exists())

    def test_tela_de_alertas_mostra_readaptacao_e_excecao_em_modais(self):
        readaptacao = ReadaptacaoProfessor.objects.create(
            professor=self.professor, data_inicio=self.hoje,
            justificativa_administrativa="Restrição funcional.", criado_por=self.desup,
        )
        excecao = ExcecaoCargaUnidade.objects.create(
            unidade=self.origem, horas_adicionais=Decimal("10.00"), data_inicio=self.hoje,
            data_fim=self.hoje + timedelta(days=30), justificativa="Turma extra.",
            solicitado_por=self.coordenador,
        )
        self.client.force_login(self.desup)

        pagina = self.client.get(reverse("core:alertas_carga_desup"))

        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, 'data-aba="tetos"')
        self.assertContains(pagina, f'id="modalEncerrar{readaptacao.pk}"')
        self.assertContains(pagina, f'id="modalExcecao{excecao.pk}"')
        self.assertNotContains(pagina, "Prioridade 1")

    def test_editar_readaptacao_volta_para_origem_sem_trocar_professor(self):
        readaptacao = ReadaptacaoProfessor.objects.create(
            professor=self.professor, data_inicio=self.hoje,
            justificativa_administrativa="Restrição funcional.", criado_por=self.desup,
        )
        self.client.force_login(self.desup)
        retorno = f"{reverse('core:alertas_carga_desup')}?unidade_id={self.origem.pk}"

        resposta = self.client.post(
            reverse("core:readaptacao_update", args=[readaptacao.pk]),
            {
                "data_inicio": self.hoje.isoformat(),
                "data_fim": (self.hoje + timedelta(days=90)).isoformat(),
                "justificativa_administrativa": "Atualizada.",
                "next": retorno,
            },
        )

        self.assertRedirects(resposta, retorno)
        readaptacao.refresh_from_db()
        self.assertEqual(readaptacao.professor_id, self.professor.pk)
        self.assertEqual(readaptacao.justificativa_administrativa, "Atualizada.")

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

    def test_barra_de_reducao_aparece_ao_preencher_e_ao_ajustar_o_cargo(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Cargo Barra", codigo="CARGO_BARRA")
        ocupacao = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem, cargo=cargo, professor=self.professor,
            data_inicio=self.hoje, carga_reducao_horas=9.5, criado_por=self.desup,
        )
        TipoCargoDiretivo.objects.create(nome="Cargo Vago", codigo="CARGO_VAGO_BARRA")
        self.client.force_login(self.desup)

        html = self.client.get(
            f"{reverse('core:equipe_diretiva_desup')}?unidade_id={self.origem.pk}"
        ).content.decode()

        # Uma barra no modal de preenchimento e outra no de ajuste de redução da ocupação.
        self.assertGreaterEqual(html.count('class="reducao-ctl'), 2)
        self.assertIn(f'id="{ocupacao.pk}-reducao"', html)
        self.assertIn('Redução total (20 h)', html)
        self.assertNotIn('max="168"', html.split('modalPreencher')[1].split('</form>')[0])

    def test_reducao_de_carga_da_desup_diminui_a_meta_em_sala(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Direção Red", codigo="DIRECAO_RED")
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem, cargo=cargo, professor=self.professor,
            data_inicio=self.hoje - timedelta(days=5), carga_reducao_horas=Decimal("6.00"),
            criado_por=self.desup,
        )
        professor = Professor.objects.get(pk=self.professor.pk)

        self.assertEqual(professor.reducao_carga_vigente, 6.0)
        self.assertEqual(professor.meta_horas_sala, 14.0)

    def test_reducao_encerrada_nao_diminui_a_meta(self):
        cargo = TipoCargoDiretivo.objects.create(nome="Direção Antiga", codigo="DIRECAO_ANTIGA")
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.origem, cargo=cargo, professor=self.professor,
            data_inicio=self.hoje - timedelta(days=60), data_fim=self.hoje - timedelta(days=10),
            carga_reducao_horas=Decimal("6.00"), criado_por=self.desup,
        )
        professor = Professor.objects.get(pk=self.professor.pk)

        self.assertEqual(professor.meta_horas_sala, 20)

    def test_pedido_de_cadastro_aparece_em_solicitacoes(self):
        self.client.force_login(self.coordenador)
        self.client.post(reverse("professors:professor_solicitar_cadastro"), {"nome": "Novo Docente"})

        solicitacao = SolicitacaoProfessorExterno.objects.get()
        self.assertEqual(solicitacao.tipo, SolicitacaoProfessorExterno.TipoChoices.CADASTRO)
        self.assertEqual(solicitacao.unidade_solicitante, self.destino)

        self.client.force_login(self.desup)
        resposta = self.client.get(reverse("core:solicitacao_professor_list"))
        self.assertContains(resposta, "Novo Docente")
        self.assertContains(resposta, "Cadastro de professor")

    def test_pedido_de_professor_de_outra_unidade_aparece_em_solicitacoes(self):
        self.client.force_login(self.coordenador)
        self.client.post(
            reverse("professors:professor_solicitar_cessao"),
            {"professor": self.professor.pk, "justificativa": "Preciso dele."},
        )

        solicitacao = SolicitacaoProfessorExterno.objects.get()
        self.assertEqual(solicitacao.tipo, SolicitacaoProfessorExterno.TipoChoices.CESSAO)
        self.assertEqual(solicitacao.unidade_origem, self.origem)

        self.client.force_login(self.desup)
        resposta = self.client.get(reverse("core:solicitacao_professor_list"))
        self.assertContains(resposta, "Cessão de professor")

    def test_notificacao_da_cessao_abre_o_cadastro_do_professor(self):
        from .models import Notificacao

        self.client.force_login(self.coordenador)
        self.client.post(
            reverse("professors:professor_solicitar_cessao"),
            {"professor": self.professor.pk, "justificativa": "Preciso dele."},
        )

        notificacao = Notificacao.objects.filter(titulo__startswith="Solicitação de professor").get()
        self.assertEqual(
            notificacao.url_acao, reverse("professors:professor_update", args=[self.professor.pk])
        )

    def test_unidade_ve_na_lista_so_professores_da_propria_unidade(self):
        self.client.force_login(self.coordenador)
        resposta = self.client.get(reverse("professors:professor_list"))
        self.assertNotContains(resposta, "Professor de Teste")

        self.client.force_login(self.desup)
        resposta = self.client.get(reverse("professors:professor_list"))
        self.assertContains(resposta, "Professor de Teste")

    def test_busca_marca_professor_de_outra_unidade(self):
        self.client.force_login(self.coordenador)
        resposta = self.client.get(
            reverse("buscar_professores"), {"q": "Professor de Teste", "unidade_alocacao": self.destino.pk}
        )
        item = resposta.json()["results"][0]
        self.assertTrue(item["outra_unidade"])

        resposta = self.client.get(
            reverse("buscar_professores"), {"q": "Professor de Teste", "unidade_alocacao": self.origem.pk}
        )
        self.assertFalse(resposta.json()["results"][0]["outra_unidade"])

    def test_readaptado_vigente_e_detectado(self):
        self.assertFalse(Professor.objects.get(pk=self.professor.pk).readaptado_vigente)
        ReadaptacaoProfessor.objects.create(
            professor=self.professor, data_inicio=self.hoje - timedelta(days=3),
            justificativa_administrativa="Readaptação administrativa.", criado_por=self.desup,
        )
        self.assertTrue(Professor.objects.get(pk=self.professor.pk).readaptado_vigente)
