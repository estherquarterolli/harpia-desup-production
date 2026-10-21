from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.allocations.models import AlocacaoCurricular, AlocacaoTurmaDocente
from apps.allocations.services import semestre_atual
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent
from apps.professors.models import ContractType, Professor

from .forms import AtividadeEstagioSupervisaoUnidadeForm, OcupacaoEquipeDiretivaUnidadeForm
from .models import (
    AtividadeEstagioSupervisao,
    AuditoriaGlobal,
    OcupacaoEquipeDiretiva,
    TipoCargoDiretivo,
    Unidade,
)


class Prioridade1UnidadeTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.semestre = semestre_atual()

        self.unidade_a = Unidade.objects.create(nome="Faculdade de Tecnologia A", sigla="FATEC-A")
        self.unidade_b = Unidade.objects.create(nome="Faculdade de Tecnologia B", sigla="FATEC-B")

        self.desup = User.objects.create_user(
            email="desup.p11@harpia.test",
            password="SenhaForte@123",
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.admin_user = User.objects.create_user(
            email="admin.p11@harpia.test",
            password="SenhaForte@123",
            perfil=User.Perfil.ADMIN,
            is_staff=True,
            is_superuser=True,
            forcar_troca_senha=False,
        )
        self.coord_a = User.objects.create_user(
            email="coord.a@harpia.test",
            password="SenhaForte@123",
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.unidade_a,
            forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email="coord.b@harpia.test",
            password="SenhaForte@123",
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=self.unidade_b,
            forcar_troca_senha=False,
        )
        self.coord_sem_unidade = User.objects.create_user(
            email="coord.sem.unid@harpia.test",
            password="SenhaForte@123",
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            unidade=None,
            forcar_troca_senha=False,
        )

        self.contrato = ContractType.objects.create(
            nome="PROF ENS SUP 40H",
            categoria=ContractType.CategoriaChoices.EFETIVO,
            regime_trabalho="40h",
            dias_presenca_obrigatorios=3,
            max_class_hours=20,
            max_total_hours=40,
            max_classes=8,
        )
        self.prof_a = Professor.objects.create(
            id_funcional="P11-A01",
            rh_matricula="M11-A01",
            rh_nome="Docente Alfa Unidade A",
            rh_email="alfa.a@harpia.test",
            unidade_principal=self.unidade_a,
            tipo_contrato=self.contrato,
        )
        self.prof_a.unidades.add(self.unidade_a)

        self.prof_a2 = Professor.objects.create(
            id_funcional="P11-A02",
            rh_matricula="M11-A02",
            rh_nome="Docente Beta Unidade A",
            rh_email="beta.a@harpia.test",
            unidade_principal=self.unidade_a,
            tipo_contrato=self.contrato,
        )
        self.prof_a2.unidades.add(self.unidade_a)

        self.prof_b = Professor.objects.create(
            id_funcional="P11-B01",
            rh_matricula="M11-B01",
            rh_nome="Docente Gama Unidade B",
            rh_email="gama.b@harpia.test",
            unidade_principal=self.unidade_b,
            tipo_contrato=self.contrato,
        )
        self.prof_b.unidades.add(self.unidade_b)

        self.curso = Course.objects.create(nome="Análise e Desenvolvimento de Sistemas", sigla="ADS")
        self.curso_unid_a = CourseUnit.objects.create(curso=self.curso, unidade=self.unidade_a, ativo=True)
        self.curso_unid_b = CourseUnit.objects.create(curso=self.curso, unidade=self.unidade_b, ativo=True)

        self.cargo_direcao, _ = TipoCargoDiretivo.objects.get_or_create(
            codigo="DIRECAO",
            defaults={"nome": "Diretor(a)", "exige_curso": False, "permite_multiplos": False, "ordem": 10},
        )
        self.cargo_coord_curso, _ = TipoCargoDiretivo.objects.get_or_create(
            codigo="COORDENACAO_DE_CURSO",
            defaults={"nome": "Coordenação de Curso", "exige_curso": True, "permite_multiplos": True, "ordem": 40},
        )
        self.cargo_estagio, _ = TipoCargoDiretivo.objects.get_or_create(
            codigo="COORDENACAO_DE_ESTAGIO",
            defaults={"nome": "Coordenação de Estágio", "exige_curso": False, "permite_multiplos": True, "ordem": 60},
        )

    # ------------------------------------------------------------------
    # 1. Testes de Modelo e UnitBoundManager (Isolamento Multi-tenant)
    # ------------------------------------------------------------------

    def test_unit_bound_manager_isola_ocupacoes_e_estagio_por_unidade(self):
        ocup_a = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a,
            cargo=self.cargo_direcao,
            professor=self.prof_a,
            data_inicio=self.hoje,
            criado_por=self.coord_a,
        )
        ocup_b = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_b,
            cargo=self.cargo_direcao,
            professor=self.prof_b,
            data_inicio=self.hoje,
            criado_por=self.coord_b,
        )
        est_a = AtividadeEstagioSupervisao.objects.create(
            unidade=self.unidade_a,
            professor=self.prof_a,
            tipo=AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
            semestre=self.semestre,
            num_estudantes=5,
            carga_horaria_semanal=Decimal("4.00"),
            data_inicio=self.hoje,
            criado_por=self.coord_a,
        )
        est_b = AtividadeEstagioSupervisao.objects.create(
            unidade=self.unidade_b,
            professor=self.prof_b,
            tipo=AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
            semestre=self.semestre,
            num_estudantes=3,
            carga_horaria_semanal=Decimal("2.00"),
            data_inicio=self.hoje,
            criado_por=self.coord_b,
        )

        self.assertEqual(list(OcupacaoEquipeDiretiva.objects.for_user(self.coord_a)), [ocup_a])
        self.assertEqual(list(OcupacaoEquipeDiretiva.objects.for_user(self.coord_b)), [ocup_b])
        self.assertEqual(OcupacaoEquipeDiretiva.objects.for_user(self.coord_sem_unidade).count(), 0)
        self.assertEqual(OcupacaoEquipeDiretiva.objects.for_user(self.desup).count(), 2)

        self.assertEqual(list(AtividadeEstagioSupervisao.objects.for_user(self.coord_a)), [est_a])
        self.assertEqual(list(AtividadeEstagioSupervisao.objects.for_user(self.coord_b)), [est_b])
        self.assertEqual(AtividadeEstagioSupervisao.objects.for_user(self.coord_sem_unidade).count(), 0)
        self.assertEqual(AtividadeEstagioSupervisao.objects.for_user(self.desup).count(), 2)

    def test_validacao_modelo_atividade_estagio_supervisao(self):
        invalida = AtividadeEstagioSupervisao(
            unidade=self.unidade_a,
            professor=self.prof_b,  # Professor de outra unidade
            curso=self.curso_unid_b,  # Curso de outra unidade
            tipo=AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
            semestre="2026-1",  # Formato inválido
            num_estudantes=4,
            carga_horaria_semanal=Decimal("4.00"),
            data_inicio=self.hoje,
            data_fim=self.hoje - timedelta(days=5),  # Fim antes do início
        )
        with self.assertRaises(ValidationError) as ctx:
            invalida.full_clean()

        self.assertIn("professor", ctx.exception.message_dict)
        self.assertIn("curso", ctx.exception.message_dict)
        self.assertIn("semestre", ctx.exception.message_dict)
        self.assertIn("data_fim", ctx.exception.message_dict)

    # ------------------------------------------------------------------
    # 2. Testes de Formulário (Bloqueio de Edição de Redução de Carga)
    # ------------------------------------------------------------------

    def test_formularios_da_unidade_nao_expoem_carga_reducao_horas(self):
        form_ocup = OcupacaoEquipeDiretivaUnidadeForm(
            unidade=self.unidade_a,
            cargo=self.cargo_coord_curso,
        )
        self.assertNotIn("carga_reducao_horas", form_ocup.fields)
        self.assertNotIn("unidade", form_ocup.fields)
        self.assertIn("curso", form_ocup.fields)
        self.assertEqual(list(form_ocup.fields["curso"].queryset), [self.curso_unid_a])
        self.assertEqual(
            set(form_ocup.fields["professor"].queryset),
            {self.prof_a, self.prof_a2},
        )

        form_estagio = AtividadeEstagioSupervisaoUnidadeForm(unidade=self.unidade_a)
        self.assertNotIn("carga_reducao_horas", form_estagio.fields)
        self.assertNotIn("unidade", form_estagio.fields)
        self.assertEqual(list(form_estagio.fields["curso"].queryset), [self.curso_unid_a])

    # ------------------------------------------------------------------
    # 3. Testes de Autorização e Escopo nas Views
    # ------------------------------------------------------------------

    def test_controle_de_acesso_por_perfil_nas_rotas_da_unidade(self):
        url_painel = reverse("core:equipe_diretiva_unidade")

        # Anônimo redireciona para login
        resp_anon = self.client.get(url_painel)
        self.assertEqual(resp_anon.status_code, 302)

        # DESUP recebe 403 na rota exclusiva de COORDENADOR_UNIDADE
        self.client.force_login(self.desup)
        self.assertEqual(self.client.get(url_painel).status_code, 403)

        # ADMIN é redirecionado para /admin/
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(url_painel)
        self.assertRedirects(resp_admin, "/admin/", fetch_redirect_response=False)

        # Coordenador sem unidade vinculada recebe 403
        self.client.force_login(self.coord_sem_unidade)
        self.assertEqual(self.client.get(url_painel).status_code, 403)

        # Coordenador com unidade ativa acessa normalmente (200)
        self.client.force_login(self.coord_a)
        self.assertEqual(self.client.get(url_painel).status_code, 200)

    def test_painel_da_unidade_nao_vaza_dados_de_outra_unidade(self):
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a,
            cargo=self.cargo_direcao,
            professor=self.prof_a,
            data_inicio=self.hoje,
            carga_reducao_horas=Decimal("10.00"),
        )
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_b,
            cargo=self.cargo_direcao,
            professor=self.prof_b,
            data_inicio=self.hoje,
            carga_reducao_horas=Decimal("16.00"),
        )

        self.client.force_login(self.coord_a)
        # Mesmo tentando passar unidade_id da unidade B na querystring, vê apenas a unidade A
        resposta = self.client.get(
            f"{reverse('core:equipe_diretiva_unidade')}?unidade_id={self.unidade_b.pk}"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["unidade"], self.unidade_a)
        self.assertContains(resposta, "Docente Alfa Unidade A")
        self.assertNotContains(resposta, "Docente Gama Unidade B")
        self.assertEqual(resposta.context["reducao_total"], Decimal("10.00"))

    # ------------------------------------------------------------------
    # 4. Cadastro, Atualização, Encerramento e Proteção Mass Assignment / IDOR
    # ------------------------------------------------------------------

    def test_coordenador_cadastra_ocupante_sem_poder_definir_reducao(self):
        self.client.force_login(self.coord_a)
        url = reverse("core:ocupacao_diretiva_unidade_create", args=[self.cargo_coord_curso.pk])

        resposta = self.client.post(
            url,
            {
                "professor": self.prof_a.pk,
                "curso": self.curso_unid_a.pk,
                "data_inicio": self.hoje.isoformat(),
                "data_fim": (self.hoje + timedelta(days=180)).isoformat(),
                "observacoes": "Portaria interna 01/2026.",
                # Tentativa maliciosa de mass assignment:
                "carga_reducao_horas": "20.00",
                "unidade": self.unidade_b.pk,
            },
        )
        self.assertRedirects(resposta, reverse("core:equipe_diretiva_unidade"))

        ocupacao = OcupacaoEquipeDiretiva.objects.get()
        self.assertEqual(ocupacao.unidade, self.unidade_a)
        self.assertEqual(ocupacao.cargo, self.cargo_coord_curso)
        self.assertEqual(ocupacao.professor, self.prof_a)
        self.assertEqual(ocupacao.curso, self.curso_unid_a)
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal("0.00"))
        self.assertEqual(ocupacao.criado_por, self.coord_a)
        self.assertTrue(
            AuditoriaGlobal.objects.filter(
                usuario=self.coord_a,
                acao="OCUPACAO_DIRETIVA_UNIDADE_CRIADA",
            ).exists()
        )

    def test_coordenador_atualiza_ocupacao_preservando_reducao_definida_pela_desup(self):
        ocupacao = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a,
            cargo=self.cargo_direcao,
            professor=self.prof_a,
            data_inicio=self.hoje,
            carga_reducao_horas=Decimal("12.00"),  # Definida pela DESUP
            observacoes="Observação inicial",
            criado_por=self.desup,
        )
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse("core:ocupacao_diretiva_unidade_update", args=[ocupacao.pk]),
            {
                "professor": self.prof_a2.pk,
                "data_inicio": self.hoje.isoformat(),
                "data_fim": (self.hoje + timedelta(days=90)).isoformat(),
                "observacoes": "Substituição temporária homologada.",
                # Tentativa de adulterar redução ou unidade via POST:
                "carga_reducao_horas": "20.00",
                "unidade": self.unidade_b.pk,
            },
        )
        self.assertRedirects(resposta, reverse("core:equipe_diretiva_unidade"))

        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.professor, self.prof_a2)
        self.assertEqual(ocupacao.observacoes, "Substituição temporária homologada.")
        self.assertEqual(ocupacao.carga_reducao_horas, Decimal("12.00"))
        self.assertEqual(ocupacao.unidade, self.unidade_a)

    def test_coordenador_encerra_ocupacao_da_propria_unidade(self):
        ocupacao = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a,
            cargo=self.cargo_direcao,
            professor=self.prof_a,
            data_inicio=self.hoje - timedelta(days=30),
            data_fim=None,
            carga_reducao_horas=Decimal("8.00"),
            criado_por=self.coord_a,
        )
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse("core:ocupacao_diretiva_unidade_encerrar", args=[ocupacao.pk])
        )
        self.assertRedirects(resposta, reverse("core:equipe_diretiva_unidade"))

        ocupacao.refresh_from_db()
        self.assertEqual(ocupacao.data_fim, self.hoje)
        self.assertFalse(ocupacao.vigente)
        painel = self.client.get(reverse('core:equipe_diretiva_unidade'))
        self.assertIn(ocupacao, painel.context['historico'])
        cargo = next(i for i in painel.context['composicao'] if i['cargo'] == self.cargo_direcao)
        self.assertEqual(cargo['ocupantes'], [])
        self.assertTrue(cargo['pode_adicionar'])
        self.assertEqual(self.prof_a.reducao_carga_vigente, 0)
        nova = OcupacaoEquipeDiretiva(
            unidade=self.unidade_a, cargo=self.cargo_direcao,
            professor=self.prof_a2, data_inicio=self.hoje,
        )
        nova.full_clean()
        nova.save()
        painel = self.client.get(reverse('core:equipe_diretiva_unidade'))
        self.assertNotIn(nova, painel.context['historico'])
        self.client.force_login(self.desup)
        painel_desup = self.client.get(reverse('core:equipe_diretiva_desup'), {'unidade_id': self.unidade_a.pk})
        self.assertIn(ocupacao, painel_desup.context['historico'])
        self.assertNotIn(nova, painel_desup.context['historico'])
        self.client.force_login(self.coord_a)
        self.assertTrue(
            AuditoriaGlobal.objects.filter(
                usuario=self.coord_a,
                acao="OCUPACAO_DIRETIVA_UNIDADE_ENCERRADA",
            ).exists()
        )



    def test_coordenador_remove_ocupante_do_cargo_com_sucesso(self):

        ocupacao = OcupacaoEquipeDiretiva.objects.create(

            unidade=self.unidade_a,

            cargo=self.cargo_direcao,

            professor=self.prof_a,

            data_inicio=self.hoje - timedelta(days=20),

            carga_reducao_horas=Decimal("8.00"),

            criado_por=self.coord_a,

        )

        self.assertEqual(self.prof_a.reducao_carga_vigente, 8.0)



        self.client.force_login(self.coord_a)

        resp_view_antes = self.client.get(reverse("core:equipe_diretiva_unidade"))

        self.assertEqual(resp_view_antes.status_code, 200)

        self.assertEqual(resp_view_antes.context["reducao_total"], Decimal("8.00"))



        # Executa a remoção do ocupante

        resposta = self.client.post(

            reverse("core:ocupacao_diretiva_unidade_remover", args=[ocupacao.pk])

        )

        self.assertRedirects(resposta, reverse("core:equipe_diretiva_unidade"))



        # Ocupação deletada, mas o cadastro do profissional segue intacto

        self.assertFalse(OcupacaoEquipeDiretiva.objects.filter(pk=ocupacao.pk).exists())

        self.assertTrue(Professor.objects.filter(pk=self.prof_a.pk).exists())



        # Efeitos sobre a redução de carga horária (HR):

        # A redução do professor volta para 0 e a redução total da unidade zera

        self.assertEqual(self.prof_a.reducao_carga_vigente, 0.0)



        resp_view_depois = self.client.get(reverse("core:equipe_diretiva_unidade"))

        self.assertEqual(resp_view_depois.status_code, 200)

        self.assertEqual(resp_view_depois.context["reducao_total"], Decimal("0.00"))
        self.assertNotIn(ocupacao, resp_view_depois.context["historico"])



        # O cargo fica vago e disponível para nova atribuição

        composicao = {item["cargo"].pk: item for item in resp_view_depois.context["composicao"]}

        item_direcao = composicao[self.cargo_direcao.pk]

        self.assertEqual(len(item_direcao["ocupantes"]), 0)

        self.assertTrue(item_direcao["pode_adicionar"])

        self.assertIn("form", item_direcao)



        # Auditoria registrada

        self.assertTrue(

            AuditoriaGlobal.objects.filter(

                usuario=self.coord_a,

                acao="OCUPACAO_DIRETIVA_UNIDADE_REMOVIDA",

            ).exists()

        )



    def test_usuario_nao_autorizado_ou_sem_unidade_nao_consegue_remover_ocupante(self):

        ocupacao = OcupacaoEquipeDiretiva.objects.create(

            unidade=self.unidade_a,

            cargo=self.cargo_direcao,

            professor=self.prof_a,

            data_inicio=self.hoje - timedelta(days=5),

            carga_reducao_horas=Decimal("6.00"),

            criado_por=self.coord_a,

        )

        # Usuário anônimo

        resp_anon = self.client.post(

            reverse("core:ocupacao_diretiva_unidade_remover", args=[ocupacao.pk])

        )

        self.assertEqual(resp_anon.status_code, 302)

        self.assertTrue(OcupacaoEquipeDiretiva.objects.filter(pk=ocupacao.pk).exists())



        # Usuário coordenador sem unidade vinculada

        self.client.force_login(self.coord_sem_unidade)

        resp_sem_unid = self.client.post(

            reverse("core:ocupacao_diretiva_unidade_remover", args=[ocupacao.pk])

        )

        self.assertEqual(resp_sem_unid.status_code, 403)

        self.assertTrue(OcupacaoEquipeDiretiva.objects.filter(pk=ocupacao.pk).exists())



    def test_remover_ocupante_com_professor_desvinculado_da_unidade_e_negado(self):

        # Docente pertence somente à unidade B, mas ocupação cadastrada para unidade A

        ocupacao = OcupacaoEquipeDiretiva.objects.create(

            unidade=self.unidade_a,

            cargo=self.cargo_direcao,

            professor=self.prof_b,

            data_inicio=self.hoje - timedelta(days=5),

            carga_reducao_horas=Decimal("4.00"),

        )

        self.client.force_login(self.coord_a)

        resp = self.client.post(

            reverse("core:ocupacao_diretiva_unidade_remover", args=[ocupacao.pk])

        )

        self.assertEqual(resp.status_code, 403)

        self.assertTrue(OcupacaoEquipeDiretiva.objects.filter(pk=ocupacao.pk).exists())



    def test_idor_bloqueado_ao_tentar_editar_ou_encerrar_ocupacao_de_outra_unidade(self):
        ocupacao_b = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_b,
            cargo=self.cargo_direcao,
            professor=self.prof_b,
            data_inicio=self.hoje - timedelta(days=10),
            carga_reducao_horas=Decimal("8.00"),
            criado_por=self.coord_b,
        )
        self.client.force_login(self.coord_a)

        resp_edit = self.client.post(
            reverse("core:ocupacao_diretiva_unidade_update", args=[ocupacao_b.pk]),
            {
                "professor": self.prof_a.pk,
                "data_inicio": self.hoje.isoformat(),
                "observacoes": "Tentativa de invasão",
            },
        )
        self.assertEqual(resp_edit.status_code, 404)

        resp_encerrar = self.client.post(
            reverse("core:ocupacao_diretiva_unidade_encerrar", args=[ocupacao_b.pk])
        )
        self.assertEqual(resp_encerrar.status_code, 404)

        resp_remover = self.client.post(
            reverse("core:ocupacao_diretiva_unidade_remover", args=[ocupacao_b.pk])
        )
        self.assertEqual(resp_remover.status_code, 404)

        ocupacao_b.refresh_from_db()
        self.assertEqual(ocupacao_b.professor, self.prof_b)
        self.assertIsNone(ocupacao_b.data_fim)

    # ------------------------------------------------------------------
    # 5. Alerta Visual e Acessível quando Integrante está em Sala de Aula
    # ------------------------------------------------------------------

    def test_exibe_alerta_visual_quando_integrante_da_equipe_diretiva_esta_em_sala(self):
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a,
            cargo=self.cargo_direcao,
            professor=self.prof_a,
            data_inicio=self.hoje - timedelta(days=15),
            carga_reducao_horas=Decimal("10.00"),
        )
        matriz = CurriculumMatrix.objects.create(
            curso=self.curso,
            nome="Matriz ADS Vigente",
            periodo_letivo=self.semestre,
            turno="M",
            is_vigente=True,
        )
        matriz.unidades.add(self.unidade_a)
        comp_catalogo = CurricularComponent.objects.create(
            nome="Engenharia de Software I",
            codigo="ESW1",
            carga_horaria_padrao=80,
        )
        comp_matriz = MatrixComponent.objects.create(
            matriz=matriz,
            componente_curricular=comp_catalogo,
            periodo=1,
            carga_horaria=80,  # 80 / 20 = 4.0 h/semana
            quantidade_turmas=1,
        )
        aloc_header = AlocacaoCurricular.objects.create(
            unidade=self.unidade_a,
            curso=self.curso_unid_a,
            semestre=self.semestre,
            turno="M",
            status=AlocacaoCurricular.StatusChoices.RASCUNHO,
        )
        AlocacaoTurmaDocente.objects.create(
            alocacao_curricular=aloc_header,
            componente_matriz=comp_matriz,
            docente=self.prof_a,
        )

        self.client.force_login(self.coord_a)
        resposta = self.client.get(reverse("core:equipe_diretiva_unidade"))
        self.assertEqual(resposta.status_code, 200)

        alertas = resposta.context["alertas_em_sala"]
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["professor_nome"], "Docente Alfa Unidade A")
        self.assertEqual(alertas[0]["horas_sala"], Decimal("4.0"))
        self.assertIn("Engenharia de Software I", alertas[0]["disciplinas"])

        # O aviso geral foi removido; o sinal fica no cartão do cargo e no modal.
        self.assertNotContains(resposta, "alocado(s) em sala de aula")
        self.assertContains(resposta, "Engenharia de Software I")
        self.assertContains(resposta, "Em sala de aula")

    # ------------------------------------------------------------------
    # 6. Registro e Gestão de Atividades de Estágio e Supervisão da Unidade
    # ------------------------------------------------------------------

    def test_coordenador_registra_edita_e_encerra_atividade_estagio_supervisao(self):
        self.client.force_login(self.coord_a)

        # 1. Criação
        resp_create = self.client.post(
            reverse("core:atividade_estagio_create"),
            {
                "tipo": AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
                "professor": self.prof_a.pk,
                "curso": self.curso_unid_a.pk,
                "semestre": self.semestre,
                "num_estudantes": 12,
                "carga_horaria_semanal": "6.00",
                "data_inicio": self.hoje.isoformat(),
                "data_fim": "",
                "observacoes": "Supervisão direta de estágio obrigatório em ADS.",
                "carga_reducao_horas": "10.00",  # Deve ser ignorado
            },
        )
        self.assertRedirects(resp_create, reverse("extra_curricular:supervisao_estagio"))

        atividade = AtividadeEstagioSupervisao.objects.get()
        self.assertEqual(atividade.unidade, self.unidade_a)
        self.assertEqual(atividade.professor, self.prof_a)
        self.assertEqual(atividade.curso, self.curso_unid_a)
        self.assertEqual(atividade.num_estudantes, 12)
        self.assertEqual(atividade.carga_horaria_semanal, Decimal("6.00"))
        self.assertEqual(atividade.carga_reducao_horas, Decimal("0.00"))

        # 2. Atualização (preservando carga_reducao_horas da DESUP)
        AtividadeEstagioSupervisao.objects.filter(pk=atividade.pk).update(
            carga_reducao_horas=Decimal("4.00")
        )
        resp_update = self.client.post(
            reverse("core:atividade_estagio_update", args=[atividade.pk]),
            {
                "tipo": AtividadeEstagioSupervisao.TipoChoices.COORDENACAO_ESTAGIO,
                "professor": self.prof_a.pk,
                "curso": self.curso_unid_a.pk,
                "semestre": self.semestre,
                "num_estudantes": 15,
                "carga_horaria_semanal": "8.00",
                "data_inicio": self.hoje.isoformat(),
                "data_fim": "",
                "observacoes": "Atualizado para coordenação de estágio.",
                "carga_reducao_horas": "20.00",
            },
        )
        self.assertRedirects(resp_update, reverse("extra_curricular:supervisao_estagio"))
        atividade.refresh_from_db()
        self.assertEqual(atividade.tipo, AtividadeEstagioSupervisao.TipoChoices.COORDENACAO_ESTAGIO)
        self.assertEqual(atividade.num_estudantes, 15)
        self.assertEqual(atividade.carga_reducao_horas, Decimal("4.00"))

        # 3. Isolamento contra outra unidade (IDOR)
        self.client.force_login(self.coord_b)
        self.assertEqual(
            self.client.post(reverse("core:atividade_estagio_encerrar", args=[atividade.pk])).status_code,
            404,
        )

        # 4. Encerramento pela própria unidade
        self.client.force_login(self.coord_a)
        resp_encerrar = self.client.post(
            reverse("core:atividade_estagio_encerrar", args=[atividade.pk])
        )
        self.assertRedirects(resp_encerrar, reverse("extra_curricular:supervisao_estagio"))
        atividade.refresh_from_db()
        self.assertEqual(atividade.data_fim, self.hoje)

    # ------------------------------------------------------------------
    # 7. Testes de Partials HTMX (Histórico e Lista de Estágio)
    # ------------------------------------------------------------------

    def test_htmx_partials_historico_e_estagio_filtram_por_unidade(self):
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a,
            cargo=self.cargo_direcao,
            professor=self.prof_a,
            data_inicio=self.hoje - timedelta(days=60),
            data_fim=self.hoje - timedelta(days=10),
        )
        OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_b,
            cargo=self.cargo_direcao,
            professor=self.prof_b,
            data_inicio=self.hoje - timedelta(days=60),
            data_fim=self.hoje - timedelta(days=10),
        )

        self.client.force_login(self.coord_a)
        resp_hist = self.client.get(
            f"{reverse('core:equipe_diretiva_unidade')}?partial=historico&situacao=encerrada",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp_hist.status_code, 200)
        self.assertTemplateUsed(resp_hist, "core/prioridade1/partials/_historico_equipe_unidade.html")
        self.assertContains(resp_hist, "Docente Alfa Unidade A")
        self.assertNotContains(resp_hist, "Docente Gama Unidade B")

        resp_estagio = self.client.get(
            reverse("extra_curricular:supervisao_estagio"),
        )
        self.assertEqual(resp_estagio.status_code, 200)
        self.assertTemplateUsed(resp_estagio, "extra_curricular/supervisao_estagio_list.html")

    def test_composicao_independe_do_volume_do_historico(self):
        ativa = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a, cargo=self.cargo_direcao,
            professor=self.prof_a, data_inicio=self.hoje - timedelta(days=500),
            carga_reducao_horas=Decimal('8.00'),
        )
        OcupacaoEquipeDiretiva.objects.bulk_create([
            OcupacaoEquipeDiretiva(
                unidade=self.unidade_a, cargo=self.cargo_coord_curso,
                curso=self.curso_unid_a, professor=self.prof_a2,
                data_inicio=self.hoje - timedelta(days=100),
                data_fim=self.hoje - timedelta(days=90),
            ) for _ in range(301)
        ])
        self.client.force_login(self.coord_a)
        painel = self.client.get(reverse('core:equipe_diretiva_unidade'))
        cargo = next(i for i in painel.context['composicao'] if i['cargo'] == self.cargo_direcao)
        self.assertEqual(cargo['ocupantes'], [ativa])
        self.assertEqual(painel.context['reducao_total'], Decimal('8.00'))
        self.client.force_login(self.desup)
        painel = self.client.get(reverse('core:equipe_diretiva_desup'), {'unidade_id': self.unidade_a.pk})
        cargo = next(i for i in painel.context['composicao'] if i['cargo'] == self.cargo_direcao)
        self.assertEqual(cargo['ocupantes'], [ativa])

    def test_futura_nao_e_encerrada_e_encerramento_e_idempotente(self):
        ocupacao = OcupacaoEquipeDiretiva.objects.create(
            unidade=self.unidade_a, cargo=self.cargo_direcao,
            professor=self.prof_a, data_inicio=self.hoje + timedelta(days=2),
        )
        self.client.force_login(self.coord_a)
        url = reverse('core:ocupacao_diretiva_unidade_encerrar', args=[ocupacao.pk])
        self.client.post(url)
        ocupacao.refresh_from_db()
        self.assertIsNone(ocupacao.data_fim)
        painel = self.client.get(reverse('core:equipe_diretiva_unidade'))
        self.assertNotIn(ocupacao, painel.context['historico'])
        ocupacao.data_inicio = self.hoje
        ocupacao.save()
        self.client.post(url)
        self.client.post(url)
        ocupacao.refresh_from_db()
        self.assertFalse(ocupacao.vigente)
        self.assertEqual(AuditoriaGlobal.objects.filter(acao='OCUPACAO_DIRETIVA_UNIDADE_ENCERRADA').count(), 1)
        self.assertFalse(ocupacao.conflitos_de_vigencia().exists())
