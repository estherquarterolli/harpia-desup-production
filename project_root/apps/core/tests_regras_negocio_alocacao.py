from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.allocations.models import AlocacaoCurricular, AlocacaoTurmaDocente
from apps.allocations.services import semestre_atual
from apps.core.models import AtividadeEstagioSupervisao, JanelaEntrega, SolicitacaoProfessorExterno, Unidade
from apps.courses.models import Course, CourseUnit, CurriculumMatrix, MatrixComponent, CurricularComponent
from apps.extra_curricular.models import PendenciaExtra, OrientacaoTCC
from apps.professors.models import ContractType, Professor


class RegrasNegocioAdequacaoTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Unidades
        self.unidade_a = Unidade.objects.create(nome="Unidade A", sigla="UA", status=True)
        self.unidade_b = Unidade.objects.create(nome="Unidade B", sigla="UB", status=True)

        # 2. Usuários
        self.coord_a = User.objects.create_user(
            email="coord.a@harpia.test",
            password="password123",
            perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade_a,
            forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email="coord.b@harpia.test",
            password="password123",
            perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade_b,
            forcar_troca_senha=False,
        )
        self.desup_user = User.objects.create_user(
            email="desup@harpia.test",
            password="password123",
            perfil="DESUP",
            forcar_troca_senha=False,
        )

        # 3. Contratos e Professores
        self.contrato = ContractType.objects.create(
            nome="Contrato 40h",
            categoria="EFETIVO",
            max_class_hours=20,
            max_total_hours=40,
            max_classes=5,
        )

        # Professor próprio da Unidade A
        self.prof_a = Professor.objects.create(
            id_funcional="11111111",
            rh_matricula="00/111111",
            rh_nome="Professor Proprio A",
            tipo_contrato=self.contrato,
            unidade_principal=self.unidade_a,
            status="Ativo",
        )

        # Professor próprio da Unidade B (sem vínculo com A)
        self.prof_b = Professor.objects.create(
            id_funcional="22222222",
            rh_matricula="00/222222",
            rh_nome="Professor Proprio B",
            tipo_contrato=self.contrato,
            unidade_principal=self.unidade_b,
            status="Ativo",
        )

        # Professor Cedido: de B para A com solicitação aprovada
        self.prof_cedido = Professor.objects.create(
            id_funcional="33333333",
            rh_matricula="00/333333",
            rh_nome="Professor Cedido para A",
            tipo_contrato=self.contrato,
            unidade_principal=self.unidade_b,
            status="Ativo",
        )
        self.cessao = SolicitacaoProfessorExterno.objects.create(
            tipo=SolicitacaoProfessorExterno.TipoChoices.CESSAO,
            unidade_solicitante=self.unidade_a,
            unidade_origem=self.unidade_b,
            professor=self.prof_cedido,
            status=SolicitacaoProfessorExterno.StatusChoices.APROVADA,
            solicitado_por=self.coord_a,
        )

        # 4. Estrutura acadêmica para alocação curricular
        self.curso = Course.objects.create(nome="Sistemas de Informação", sigla="SI")
        self.course_unit = CourseUnit.objects.create(curso=self.curso, unidade=self.unidade_a)
        self.matriz = CurriculumMatrix.objects.create(
            curso=self.curso,
            nome="Matriz SI 2026",
            turno="M",
            is_vigente=True,
        )
        self.matriz.unidades.add(self.unidade_a)

        self.comp_base = CurricularComponent.objects.create(
            nome="Programação I",
            carga_horaria_padrao=80,
        )
        self.componente = MatrixComponent.objects.create(
            matriz=self.matriz,
            componente_curricular=self.comp_base,
            periodo="1",
            carga_horaria=80,
            carga_horaria_semanal=Decimal("4.00"),
        )

        self.semestre = semestre_atual()

        # Janela de entrega aberta cobrindo a data atual
        self.janela = JanelaEntrega.objects.create(
            semestre=self.semestre,
            data_inicio=date.today() - timedelta(days=5),
            data_fim=date.today() + timedelta(days=15),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )

    # =========================================================================
    # MUDANÇA 1: SEI Opcional na Alocação Extracurricular
    # =========================================================================

    def test_cadastro_extracurricular_sem_sei(self):
        """1. É possível cadastrar uma Alocação Extracurricular sem informar o SEI."""
        self.client.force_login(self.coord_a)
        pendencia = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="",  # sem SEI
            status=PendenciaExtra.StatusChoices.RASCUNHO,
            criado_por=self.coord_a,
        )
        self.assertEqual(pendencia.sei_numero, "")
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)

    def test_edicao_extracurricular_mantem_sei_vazio(self):
        """2. É possível editar um registro existente e manter o SEI vazio."""
        self.client.force_login(self.coord_a)
        pendencia = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="",
            status=PendenciaExtra.StatusChoices.RASCUNHO,
        )
        # Edita SEI via POST para vazio
        url_edit_sei = reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk})
        resposta = self.client.post(url_edit_sei, {"sei_numero": ""})
        self.assertEqual(resposta.status_code, 302)
        pendencia.refresh_from_db()
        self.assertIn(pendencia.sei_numero, ("", None))

    def test_cadastro_com_sei_preenchido(self):
        """3. O sistema aceita e armazena o SEI quando informado no formato correto."""
        self.client.force_login(self.coord_a)
        pendencia = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            status=PendenciaExtra.StatusChoices.RASCUNHO,
        )
        url_edit_sei = reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk})
        resposta = self.client.post(url_edit_sei, {"sei_numero": "SEI-123456/123456/2026"})
        self.assertEqual(resposta.status_code, 302)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.sei_numero, "SEI-123456/123456/2026")

    def test_envio_individual_para_desup_sem_sei(self):
        """4. É possível enviar justificativa para a DESUP individualmente sem preencher SEI."""
        self.client.force_login(self.coord_a)
        pendencia = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="",  # sem SEI
            status=PendenciaExtra.StatusChoices.RASCUNHO,
        )
        url_enviar = reverse("extra_curricular:enviar_desup", kwargs={"pk": pendencia.pk})
        resposta = self.client.post(url_enviar)
        self.assertEqual(resposta.status_code, 302)
        pendencia.refresh_from_db()
        # Status deve ter sido promovido a ENVIADO
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)

    def test_envio_em_lote_para_desup_sem_sei(self):
        """5. É possível enviar justificativas em lote para a DESUP sem preencher SEI."""
        self.client.force_login(self.coord_a)
        p1 = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="",  # sem SEI
            status=PendenciaExtra.StatusChoices.RASCUNHO,
        )
        url_lote = reverse("extra_curricular:enviar_desup_lote")
        resposta = self.client.post(url_lote, {"ids": str(self.prof_a.pk)})
        self.assertEqual(resposta.status_code, 302)
        p1.refresh_from_db()
        self.assertEqual(p1.status, PendenciaExtra.StatusChoices.ENVIADO)

    def test_salvar_item_apos_5_dias_sem_sei_nao_bloqueia(self):
        """6. Salvar item de justificativa após 5 dias da criação não bloqueia por falta de SEI."""
        self.client.force_login(self.coord_a)
        p = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="",
            status=PendenciaExtra.StatusChoices.RASCUNHO,
        )
        # Simula pendência criada há 10 dias
        PendenciaExtra.objects.filter(pk=p.pk).update(
            data_criacao=timezone.now() - timedelta(days=10)
        )
        p.refresh_from_db()

        # Salva um item TCC
        url_tcc = reverse("extra_curricular:salvar_tcc", kwargs={"pk": p.pk})
        post_data = {
            "tcc-TOTAL_FORMS": "1",
            "tcc-INITIAL_FORMS": "0",
            "tcc-MIN_NUM_FORMS": "0",
            "tcc-MAX_NUM_FORMS": "1000",
            "tcc-0-num_orientandos": "2",
        }
        resposta = self.client.post(url_tcc, post_data)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(OrientacaoTCC.objects.filter(pendencia=p, num_orientandos=2).exists())

    # =========================================================================
    # MUDANÇA 2: Supervisão de Estágio na Alocação Extracurricular
    # =========================================================================

    def test_equipe_diretiva_nao_contem_mais_estagio(self):
        """1. A aba Equipe Diretiva não apresenta mais a janela ou o botão de atividades de estágio."""
        self.client.force_login(self.coord_a)
        url_equipe = reverse("core:equipe_diretiva_unidade")
        resposta = self.client.get(url_equipe)
        self.assertEqual(resposta.status_code, 200)
        # Não deve conter o botão nem o modal de novo estágio
        self.assertNotContains(resposta, "modalNovoEstagioUnidade")
        self.assertNotContains(resposta, "Atividades de estágio e supervisão da unidade")
        self.assertNotContains(resposta, reverse("core:atividade_estagio_create"))

    def test_alocacao_extracurricular_contem_aba_supervisao_estagio(self):
        """2. A aba Alocação Extracurricular apresenta o acesso à nova janela Supervisão de Estágio."""
        self.client.force_login(self.coord_a)
        url_pendencias = reverse("extra_curricular:pendencia_list")
        resposta = self.client.get(url_pendencias)
        self.assertEqual(resposta.status_code, 200)
        url_estagio = reverse("extra_curricular:supervisao_estagio")
        self.assertContains(resposta, url_estagio)
        self.assertContains(resposta, "Supervisão de Estágio")

    def test_supervisao_estagio_lista_e_opera_registros(self):
        """3. A tela de Supervisão de Estágio lista atividades existentes e permite cadastrar nova."""
        # Cria registro prévio
        estagio = AtividadeEstagioSupervisao.objects.create(
            unidade=self.unidade_a,
            professor=self.prof_a,
            curso=self.course_unit,
            tipo=AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
            semestre=self.semestre,
            num_estudantes=3,
            carga_horaria_semanal=Decimal("6.00"),
            data_inicio=date.today(),
            criado_por=self.coord_a,
        )

        self.client.force_login(self.coord_a)
        url_estagio = reverse("extra_curricular:supervisao_estagio")
        resposta = self.client.get(url_estagio)
        self.assertEqual(resposta.status_code, 200)
        # Registro antigo é exibido
        self.assertContains(resposta, "Professor Proprio A")
        self.assertContains(resposta, "Supervisão de Estágio")
        self.assertContains(resposta, "3 supervisionado(s)")

        # Cadastra nova atividade de estágio via POST
        url_create = reverse("extra_curricular:atividade_estagio_create")
        dados = {
            "professor": self.prof_a.pk,
            "curso": self.course_unit.pk,
            "tipo": AtividadeEstagioSupervisao.TipoChoices.ORIENTACAO_ESTAGIO,
            "semestre": self.semestre,
            "num_estudantes": 2,
            "carga_horaria_semanal": "4.00",
            "data_inicio": date.today().strftime("%Y-%m-%d"),
        }
        res_create = self.client.post(url_create, dados)
        self.assertEqual(res_create.status_code, 302)
        self.assertTrue(
            AtividadeEstagioSupervisao.objects.filter(
                unidade=self.unidade_a,
                tipo=AtividadeEstagioSupervisao.TipoChoices.ORIENTACAO_ESTAGIO,
                num_estudantes=2,
            ).exists()
        )

        # Encerra atividade de estágio
        url_encerrar = reverse("extra_curricular:atividade_estagio_encerrar", kwargs={"pk": estagio.pk})
        res_encerrar = self.client.post(url_encerrar)
        self.assertEqual(res_encerrar.status_code, 302)
        estagio.refresh_from_db()
        self.assertIsNotNone(estagio.data_fim)

    def test_semestre_letivo_da_supervisao_e_preenchido_automaticamente(self):
        """O coordenador não precisa informar o semestre ao cadastrar a atividade."""
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse("extra_curricular:atividade_estagio_create"),
            {
                "professor": self.prof_a.pk,
                "curso": self.course_unit.pk,
                "tipo": AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
                "num_estudantes": 2,
                "carga_horaria_semanal": "4.00",
                "data_inicio": date.today().strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(resposta.status_code, 302)
        atividade = AtividadeEstagioSupervisao.objects.get(
            tipo=AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
        )
        self.assertEqual(atividade.semestre, semestre_atual())

    def test_semestre_letivo_da_supervisao_nao_pode_ser_adulterado(self):
        """O backend ignora um semestre enviado manualmente na criação."""
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse("extra_curricular:atividade_estagio_create"),
            {
                "professor": self.prof_a.pk,
                "curso": self.course_unit.pk,
                "tipo": AtividadeEstagioSupervisao.TipoChoices.ORIENTACAO_ESTAGIO,
                "semestre": "1999.1",
                "num_estudantes": 1,
                "carga_horaria_semanal": "2.00",
                "data_inicio": date.today().strftime("%Y-%m-%d"),
            },
        )

        self.assertEqual(resposta.status_code, 302)
        atividade = AtividadeEstagioSupervisao.objects.get(
            tipo=AtividadeEstagioSupervisao.TipoChoices.ORIENTACAO_ESTAGIO,
        )
        self.assertEqual(atividade.semestre, semestre_atual())

    def test_edicao_da_supervisao_preserva_semestre_historico(self):
        """Editar uma atividade antiga não a move para o semestre corrente."""
        atividade = AtividadeEstagioSupervisao.objects.create(
            unidade=self.unidade_a,
            professor=self.prof_a,
            curso=self.course_unit,
            tipo=AtividadeEstagioSupervisao.TipoChoices.SUPERVISAO_ESTAGIO,
            semestre="2025.1",
            num_estudantes=1,
            carga_horaria_semanal=Decimal("2.00"),
            data_inicio=date(2025, 2, 1),
            criado_por=self.coord_a,
        )
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse("extra_curricular:atividade_estagio_update", kwargs={"pk": atividade.pk}),
            {
                "professor": self.prof_a.pk,
                "curso": self.course_unit.pk,
                "tipo": AtividadeEstagioSupervisao.TipoChoices.COORDENACAO_ESTAGIO,
                "semestre": semestre_atual(),
                "num_estudantes": 3,
                "carga_horaria_semanal": "3.00",
                "data_inicio": "2025-02-01",
            },
        )

        self.assertEqual(resposta.status_code, 302)
        atividade.refresh_from_db()
        self.assertEqual(atividade.semestre, "2025.1")

    # =========================================================================
    # MUDANÇA 3: Restringir Professores por Unidade na Alocação Curricular
    # =========================================================================

    def test_coordenador_ve_professor_proprio_e_cedido_na_busca(self):
        """1. A unidade visualiza seus próprios professores e professores cedidos na busca."""
        self.client.force_login(self.coord_a)
        url_busca = reverse("buscar_professores")
        resposta = self.client.get(url_busca)
        self.assertEqual(resposta.status_code, 200)
        nomes = [item["nome"] for item in resposta.json()["results"]]
        # Deve conter o próprio e o cedido
        self.assertIn("Professor Proprio A", nomes)
        self.assertIn("Professor Cedido para A", nomes)
        # NÃO deve conter o professor exclusivo da Unidade B
        self.assertNotIn("Professor Proprio B", nomes)

    def test_coordenador_nao_consegue_burlar_busca_com_parametro_unidade(self):
        """2. Tentativas de passar unidade_alocacao de outra unidade são ignoradas pelo backend."""
        self.client.force_login(self.coord_a)
        url_busca = reverse("buscar_professores")
        # Tenta passar o ID da Unidade B
        resposta = self.client.get(url_busca, {"unidade_alocacao": self.unidade_b.pk})
        self.assertEqual(resposta.status_code, 200)
        nomes = [item["nome"] for item in resposta.json()["results"]]
        self.assertNotIn("Professor Proprio B", nomes)
        self.assertIn("Professor Proprio A", nomes)

    def test_bloqueio_backend_ao_alocar_professor_de_outra_unidade_sem_cessao(self):
        """3. Tentativa de manipulação direta via POST para alocar professor de outra unidade é bloqueada (403)."""
        self.client.force_login(self.coord_a)
        url_alocar = reverse("alocar_docente_componente", kwargs={"pk": self.componente.pk})
        # Tenta alocar professor da Unidade B que NÃO possui cessão
        resposta = self.client.post(
            url_alocar,
            {"docente_id": str(self.prof_b.pk)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 403)
        self.assertIn("Acesso negado", resposta.json().get("message", ""))
        self.assertFalse(
            AlocacaoTurmaDocente.objects.filter(
                componente_matriz=self.componente, docente=self.prof_b
            ).exists()
        )

    def test_sucesso_ao_alocar_professor_proprio(self):
        """4. É permitido alocar normalmente professor da própria unidade."""
        self.client.force_login(self.coord_a)
        url_alocar = reverse("alocar_docente_componente", kwargs={"pk": self.componente.pk})
        resposta = self.client.post(
            url_alocar,
            {"docente_id": str(self.prof_a.pk)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["ok"])
        self.assertTrue(
            AlocacaoTurmaDocente.objects.filter(
                componente_matriz=self.componente, docente=self.prof_a
            ).exists()
        )

    def test_sucesso_ao_alocar_professor_cedido_autorizado(self):
        """5. É permitido alocar professor cedido formalmente com cessão aprovada."""
        self.client.force_login(self.coord_a)
        url_alocar = reverse("alocar_docente_componente", kwargs={"pk": self.componente.pk})
        resposta = self.client.post(
            url_alocar,
            {"docente_id": str(self.prof_cedido.pk)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["ok"])
        self.assertTrue(
            AlocacaoTurmaDocente.objects.filter(
                componente_matriz=self.componente, docente=self.prof_cedido
            ).exists()
        )

    def test_desup_mantem_acesso_global_a_busca_e_alocacao(self):
        """6. Perfil DESUP mantém acesso administrativo e visão global dos professores."""
        self.client.force_login(self.desup_user)
        url_busca = reverse("buscar_professores")
        resposta = self.client.get(url_busca)
        self.assertEqual(resposta.status_code, 200)
        nomes = [item["nome"] for item in resposta.json()["results"]]
        self.assertIn("Professor Proprio A", nomes)
        self.assertIn("Professor Proprio B", nomes)
        self.assertIn("Professor Cedido para A", nomes)
