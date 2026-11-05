import json

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditoriaGlobal
from apps.extra_curricular.models import OrientacaoTCC, PendenciaExtra


class RegularizarSEILegadoTests(TransactionTestCase):
    """Reproduz a CHECK externa que bloqueava o SET_NULL ao excluir usuários."""

    def setUp(self):
        super().setUp()
        if (
            "extra_curricular" in settings.MIGRATION_MODULES
            and settings.MIGRATION_MODULES["extra_curricular"] is None
        ):
            self.skipTest("Este teste requer migrations reais (settings.development).")
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        previous = [node for node in self.latest if node[0] != "extra_curricular"]
        previous.append(("extra_curricular", "0007_tcc_sem_limite_orientandos"))
        executor.migrate(previous)
        self.addCleanup(self._restaurar_schema)
        old_apps = executor.loader.project_state(previous).apps
        Unidade = old_apps.get_model("core", "Unidade")
        Professor = old_apps.get_model("professors", "Professor")
        ContractType = old_apps.get_model("professors", "ContractType")
        Usuario = old_apps.get_model("accounts", "User")
        Pendencia = old_apps.get_model("extra_curricular", "PendenciaExtra")
        Orientacao = old_apps.get_model("extra_curricular", "OrientacaoTCC")
        unidade = Unidade.objects.create(nome="Unidade SEI legado", sigla="USL")
        contrato = ContractType.objects.create(nome="Contrato SEI", max_class_hours=20, max_classes=10)
        self.usuario_id = Usuario.objects.create(
            email="criador-legado@teste.com", username="criador-legado"
        ).pk
        self.invalidas = []
        for index, sei in enumerate(("2254646565626262323", "processo antigo")):
            professor = Professor.objects.create(
                rh_nome=f"Docente legado {index}", id_funcional=f"sei-legado-{index}",
                tipo_contrato=contrato,
            )
            pendencia = Pendencia.objects.create(
                professor=professor, unidade=unidade, semestre="2026.2",
                sei_numero=sei, status="ENVIADO", criado_por_id=self.usuario_id,
            )
            self.invalidas.append((pendencia.pk, sei, pendencia.data_atualizacao))
        self.item_id = Orientacao.objects.create(
            pendencia_id=self.invalidas[0][0], num_orientandos=2,
            carga_horaria=1, horas_aprovadas=1, parecer_desup="APROVADO",
        ).pk
        self.validas = []
        for index, sei in enumerate(("SEI-123456/123456/2026", "", None)):
            professor = Professor.objects.create(
                rh_nome=f"Docente válido {index}", id_funcional=f"sei-valido-{index}",
                tipo_contrato=contrato,
            )
            pendencia = Pendencia.objects.create(
                professor=professor, unidade=unidade, semestre="2026.2", sei_numero=sei,
            )
            self.validas.append((pendencia.pk, sei))
        if connection.vendor == "postgresql":
            # NOT VALID admite registros antigos inválidos, mas toda UPDATE
            # continua sujeita à CHECK, mesmo quando só altera criado_por_id.
            with connection.cursor() as cursor:
                cursor.execute(
                    'ALTER TABLE "harpiadb_extracurricular_pendencia" '
                    'ADD CONSTRAINT "chk_sei_formato" '
                    "CHECK (sei_numero IS NULL OR sei_numero = '' "
                    "OR sei_numero ~ '^SEI-[0-9]{6}/[0-9]{6}/[0-9]{4}$') NOT VALID"
                )

    def _restaurar_schema(self):
        MigrationExecutor(connection).migrate(self.latest)

    def _regularizar(self):
        MigrationExecutor(connection).migrate(self.latest)

    def _login_admin(self):
        admin = User.objects.create_superuser(
            email="admin-sei@teste.com", password="Teste@2026", forcar_troca_senha=False,
        )
        self.client.force_login(admin)

    def test_migration_preserva_originais_status_itens_e_seis_validos(self):
        if connection.vendor == "postgresql":
            with self.assertRaisesMessage(IntegrityError, "chk_sei_formato"):
                with transaction.atomic():
                    User.objects.filter(pk=self.usuario_id).delete()
            self.assertTrue(User.objects.filter(pk=self.usuario_id).exists())
        self._regularizar()
        for pk, original, atualizado_em in self.invalidas:
            pendencia = PendenciaExtra.objects.get(pk=pk)
            self.assertIsNone(pendencia.sei_numero)
            self.assertEqual(pendencia.status, "ENVIADO")
            self.assertEqual(pendencia.data_atualizacao, atualizado_em)
            self.assertEqual(pendencia.criado_por_id, self.usuario_id)
            registro = AuditoriaGlobal.objects.get(
                acao="SEI_LEGADO_INVALIDO", detalhes__contains=original,
            )
            dados = json.loads(registro.detalhes)
            self.assertEqual(dados["pk"], pk)
            self.assertEqual(dados["sei_numero"], original)
        for pk, sei in self.validas:
            self.assertEqual(PendenciaExtra.objects.get(pk=pk).sei_numero, sei)
        item = OrientacaoTCC.objects.get(pk=self.item_id)
        self.assertEqual(item.parecer_desup, "APROVADO")
        self.assertEqual(item.horas_aprovadas, 1)
        self.assertEqual(AuditoriaGlobal.objects.filter(acao="SEI_LEGADO_INVALIDO").count(), 2)
        self._regularizar()
        self.assertEqual(AuditoriaGlobal.objects.filter(acao="SEI_LEGADO_INVALIDO").count(), 2)
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT convalidated FROM pg_constraint "
                    "WHERE conrelid = 'harpiadb_extracurricular_pendencia'::regclass "
                    "AND conname = 'chk_sei_formato'"
                )
                self.assertEqual(cursor.fetchone(), (True,))

    def test_exclusao_em_lote_no_admin_preserva_pendencias_e_justificativas(self):
        self._regularizar()
        self._login_admin()
        outro = User.objects.create_user(email="outro-sei@teste.com")
        url = reverse("alloc_admin:accounts_user_changelist")
        selecao = {"action": "delete_selected", "_selected_action": [self.usuario_id, outro.pk]}
        confirmacao = self.client.post(url, selecao)
        self.assertEqual(confirmacao.status_code, 200)
        resposta = self.client.post(url, {**selecao, "post": "yes"})
        self.assertRedirects(resposta, url, fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk__in=[self.usuario_id, outro.pk]).exists())
        for pk, _, _ in self.invalidas:
            pendencia = PendenciaExtra.objects.get(pk=pk)
            self.assertIsNone(pendencia.criado_por_id)
            self.assertEqual(pendencia.status, "ENVIADO")
        self.assertTrue(OrientacaoTCC.objects.filter(pk=self.item_id).exists())

    def test_exclusao_individual_no_admin(self):
        self._regularizar()
        self._login_admin()
        resposta = self.client.post(
            reverse("alloc_admin:accounts_user_delete", args=[self.usuario_id]), {"post": "yes"},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.usuario_id).exists())
        self.assertTrue(PendenciaExtra.objects.filter(pk=self.invalidas[0][0]).exists())

    def test_constraint_impede_novo_sei_invalido_inclusive_em_update_direto(self):
        self._regularizar()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PendenciaExtra.objects.filter(pk=self.invalidas[0][0]).update(
                    sei_numero="2254646565626262323"
                )
