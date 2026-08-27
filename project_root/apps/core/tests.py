from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.core.models import Unidade, JanelaEntrega, Notificacao
from apps.professors.models import Professor, ContractType

User = get_user_model()


class DashboardRoutingTests(TestCase):
    def setUp(self):
        self.password = "password"
        self.desup_user = User.objects.create_user(
            email="dashboard_desup@teste.com",
            password=self.password,
            perfil='DESUP',
            forcar_troca_senha=False
        )
        self.unidade_user = User.objects.create_user(
            email="dashboard_unidade@teste.com",
            password=self.password,
            perfil='COORDENADOR_UNIDADE',
            forcar_troca_senha=False
        )
        self.superuser = User.objects.create_superuser(
            email="dashboard_admin@teste.com",
            password=self.password,
            forcar_troca_senha=False
        )

    def test_dashboard_redirects_desup_to_desup_dashboard(self):
        self.client.force_login(self.desup_user)
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/dashboard/desup/')

    def test_dashboard_redirects_unidade_to_unidade_dashboard(self):
        self.client.force_login(self.unidade_user)
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/dashboard/unidade/')

    def test_dashboard_redirects_superuser_to_desup_dashboard(self):
        self.client.force_login(self.superuser)
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/dashboard/desup/')

    def test_desup_dashboard_template_is_reachable(self):
        self.client.force_login(self.desup_user)
        response = self.client.get('/dashboard/desup/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/desup.html')

class UnitBoundManagerTests(TestCase):
    def setUp(self):
        # Criar unidades
        self.unidade_a = Unidade.objects.create(nome="Unidade A", sigla="UA")
        self.unidade_b = Unidade.objects.create(nome="Unidade B", sigla="UB")

        # Criar usuários
        self.coord_desup = User.objects.create_user(
            email="desup@teste.com",
            password="password",
            perfil='DESUP'
        )
        self.coord_unidade_a = User.objects.create_user(
            email="unidade_a@teste.com",
            password="password",
            perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade_a
        )
        self.coord_unidade_b = User.objects.create_user(
            email="unidade_b@teste.com",
            password="password",
            perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade_b
        )

        # Criar tipo de contrato (obrigatório)
        self.tipo_contrato = ContractType.objects.create(
            nome="Superior",
            max_class_hours=20,
            max_classes=4
        )

        # Criar professores em diferentes unidades
        Professor.objects.create(
            id_funcional="IDF001",
            rh_nome="Prof A", 
            rh_matricula="M001",
            rh_email="prof_a@teste.com",
            unidade_principal=self.unidade_a,
            tipo_contrato=self.tipo_contrato
        )
        Professor.objects.create(
            id_funcional="IDF002",
            rh_nome="Prof B", 
            rh_matricula="M002",
            rh_email="prof_b@teste.com",
            unidade_principal=self.unidade_b,
            tipo_contrato=self.tipo_contrato
        )


    def test_desup_can_see_all_professors(self):
        """Coordenador DESUP deve ver todos os professores."""
        queryset = Professor.objects.for_user(self.coord_desup)
        self.assertEqual(queryset.count(), 2)

    def test_unidade_coord_can_only_see_their_unit(self):
        """Coordenador de Unidade deve ver apenas professores da sua unidade."""
        queryset_a = Professor.objects.for_user(self.coord_unidade_a)
        self.assertEqual(queryset_a.count(), 1)
        self.assertEqual(queryset_a.first().nome, "Prof A")

        queryset_b = Professor.objects.for_user(self.coord_unidade_b)
        self.assertEqual(queryset_b.count(), 1)
        self.assertEqual(queryset_b.first().nome, "Prof B")

    def test_superuser_can_see_all_professors(self):
        """Superuser deve ver todos os professores."""
        superuser = User.objects.create_superuser(
            email="admin@teste.com",
            password="password",
        )
        queryset = Professor.objects.for_user(superuser)
        self.assertEqual(queryset.count(), 2)

class DomainRulesTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade X", sigla="UX")
        self.tipo = ContractType.objects.create(nome="Superior", max_class_hours=20, max_classes=4)
        self.prof = Professor.objects.create(
            id_funcional="IDF123",
            rh_nome="Nome RH",
            rh_matricula="M123",
            rh_email="rh@teste.com",
            unidade_principal=self.unidade,
            tipo_contrato=self.tipo
        )

    def test_professor_override_logic(self):
        """Regra #3: Se houver ajuste DESUP, ele deve prevalecer sobre o RH."""
        # Sem override
        self.assertEqual(self.prof.nome, "Nome RH")
        self.assertEqual(self.prof.email, "rh@teste.com")

        # Com override
        self.prof.desup_nome = "Nome Ajustado"
        self.prof.desup_email = "ajuste@teste.com"
        self.prof.save()

        self.assertEqual(self.prof.nome, "Nome Ajustado")
        self.assertEqual(self.prof.email, "ajuste@teste.com")
        self.assertEqual(self.prof.rh_nome, "Nome RH") # Original preservado

    def test_janela_entrega_status(self):
        """Regra #2: Janela deve refletir status ativa/inativa corretamente."""
        from django.utils import timezone
        hoje = timezone.now().date()
        
        janela = JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje,
            data_fim=hoje + timezone.timedelta(days=15),
            status=JanelaEntrega.StatusChoices.ABERTO
        )
        self.assertTrue(janela.is_ativa)

        janela.status = JanelaEntrega.StatusChoices.FECHADO
        self.assertFalse(janela.is_ativa)


class JanelaEntregaFormTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Test Unit", sigla="TU")
        from django.utils import timezone
        self.hoje = timezone.now().date()

    def test_new_janela_saves_as_aberto(self):
        # Quando criamos uma nova janela (sem pk), se colocamos status Aberto, salva como Aberto
        from apps.core.forms import JanelaEntregaForm
        from django.utils import timezone
        form_data = {
            'semestre': '2026.1',
            'data_inicio': self.hoje,
            'data_fim': self.hoje + timezone.timedelta(days=10),
            'status': JanelaEntrega.StatusChoices.ABERTO,
            'unidade': '',
        }
        form = JanelaEntregaForm(data=form_data)
        self.assertTrue(form.is_valid())
        janela = form.save()
        self.assertEqual(janela.status, JanelaEntrega.StatusChoices.ABERTO)

    def test_edit_janela_reaberto_logic(self):
        from apps.core.forms import JanelaEntregaForm
        from django.utils import timezone
        # Criamos uma janela fechada
        janela = JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje,
            data_fim=self.hoje + timezone.timedelta(days=10),
            status=JanelaEntrega.StatusChoices.FECHADO
        )
        
        # Test 1: Ao carregar a edição de uma janela que é REABERTO, exibe como ABERTO no form
        janela.status = JanelaEntrega.StatusChoices.REABERTO
        janela.save()
        form = JanelaEntregaForm(instance=janela)
        self.assertEqual(form.initial.get('status'), JanelaEntrega.StatusChoices.ABERTO)
        self.assertNotIn(JanelaEntrega.StatusChoices.REABERTO, [c[0] for c in form.fields['status'].choices])
        
        # Test 2: Ao salvar a janela editada com status Aberto, vira Reaberto
        form_data = {
            'semestre': '2026.1',
            'data_inicio': self.hoje,
            'data_fim': self.hoje + timezone.timedelta(days=15), # editado
            'status': JanelaEntrega.StatusChoices.ABERTO,
            'unidade': '',
        }
        form = JanelaEntregaForm(data=form_data, instance=janela)
        self.assertTrue(form.is_valid())
        saved_janela = form.save()
        self.assertEqual(saved_janela.status, JanelaEntrega.StatusChoices.REABERTO)

    def test_frontend_update_form_reaberto_logic(self):
        from apps.core.views import JanelaEntregaUpdateForm
        from django.utils import timezone
        # Criamos uma janela fechada
        janela = JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje,
            data_fim=self.hoje + timezone.timedelta(days=10),
            status=JanelaEntrega.StatusChoices.FECHADO
        )
        
        # Test 1: Ao carregar o formulário de update para REABERTO, exibe como ABERTO
        janela.status = JanelaEntrega.StatusChoices.REABERTO
        janela.save()
        form = JanelaEntregaUpdateForm(instance=janela)
        self.assertEqual(form.initial.get('status'), JanelaEntrega.StatusChoices.ABERTO)
        self.assertNotIn(JanelaEntrega.StatusChoices.REABERTO, [c[0] for c in form.fields['status'].choices])
        
        # Test 2: Ao salvar via frontend update form com status Aberto, vira Reaberto
        form_data = {
            'semestre': '2026.1',
            'data_inicio': self.hoje,
            'data_fim': self.hoje + timezone.timedelta(days=15),
            'status': JanelaEntrega.StatusChoices.ABERTO,
            'unidade': '',
        }
        form = JanelaEntregaUpdateForm(data=form_data, instance=janela)
        self.assertTrue(form.is_valid())
        saved_janela = form.save()
        self.assertEqual(saved_janela.status, JanelaEntrega.StatusChoices.REABERTO)


# ─────────────────────────────────────────────
# Testes da propriedade is_ativa nos 3 estados
# ─────────────────────────────────────────────

class JanelaEntregaIsAtivaTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.hoje = timezone.now().date()

    def _make_janela(self, status, dias_inicio=0, dias_fim=15):
        from django.utils import timezone
        return JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje + timezone.timedelta(days=dias_inicio),
            data_fim=self.hoje + timezone.timedelta(days=dias_fim),
            status=status,
        )

    # Estado ABERTO
    def test_aberto_dentro_prazo_is_ativa(self):
        janela = self._make_janela(JanelaEntrega.StatusChoices.ABERTO)
        self.assertTrue(janela.is_ativa)

    def test_aberto_fora_prazo_nao_is_ativa(self):
        from django.utils import timezone
        janela = JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje - timezone.timedelta(days=30),
            data_fim=self.hoje - timezone.timedelta(days=1),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        self.assertFalse(janela.is_ativa)

    # Estado FECHADO
    def test_fechado_dentro_prazo_nao_is_ativa(self):
        janela = self._make_janela(JanelaEntrega.StatusChoices.FECHADO)
        self.assertFalse(janela.is_ativa)

    def test_fechado_fora_prazo_nao_is_ativa(self):
        from django.utils import timezone
        janela = JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje - timezone.timedelta(days=20),
            data_fim=self.hoje - timezone.timedelta(days=1),
            status=JanelaEntrega.StatusChoices.FECHADO,
        )
        self.assertFalse(janela.is_ativa)

    # Estado REABERTO
    def test_reaberto_dentro_prazo_is_ativa(self):
        janela = self._make_janela(JanelaEntrega.StatusChoices.REABERTO)
        self.assertTrue(janela.is_ativa)

    def test_reaberto_fora_prazo_nao_is_ativa(self):
        from django.utils import timezone
        janela = JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje - timezone.timedelta(days=20),
            data_fim=self.hoje - timezone.timedelta(days=1),
            status=JanelaEntrega.StatusChoices.REABERTO,
        )
        self.assertFalse(janela.is_ativa)


# ─────────────────────────────────────────────
# Testes do serviço get_delivery_window
# ─────────────────────────────────────────────

class GetDeliveryWindowTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.hoje = timezone.now().date()
        self.unidade = Unidade.objects.create(nome="Unidade W", sigla="UW")

    def _make_janela(self, status, unidade=None, dias_inicio=0, dias_fim=15):
        from django.utils import timezone
        return JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje + timezone.timedelta(days=dias_inicio),
            data_fim=self.hoje + timezone.timedelta(days=dias_fim),
            status=status,
            unidade=unidade,
        )

    def test_aberto_dentro_prazo_retorna_janela(self):
        from apps.core.services import get_delivery_window
        janela = self._make_janela(JanelaEntrega.StatusChoices.ABERTO)
        self.assertEqual(get_delivery_window(), janela)

    def test_fechado_retorna_none(self):
        from apps.core.services import get_delivery_window
        self._make_janela(JanelaEntrega.StatusChoices.FECHADO)
        self.assertIsNone(get_delivery_window())

    def test_reaberto_dentro_prazo_retorna_janela(self):
        from apps.core.services import get_delivery_window
        janela = self._make_janela(JanelaEntrega.StatusChoices.REABERTO)
        self.assertEqual(get_delivery_window(), janela)

    def test_aberto_fora_prazo_retorna_none(self):
        from apps.core.services import get_delivery_window
        from django.utils import timezone
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje - timezone.timedelta(days=20),
            data_fim=self.hoje - timezone.timedelta(days=1),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        self.assertIsNone(get_delivery_window())

    def test_janela_especifica_da_unidade_tem_prioridade_sobre_global(self):
        from apps.core.services import get_delivery_window
        # Global aberta
        self._make_janela(JanelaEntrega.StatusChoices.ABERTO)
        # Unidade também aberta — deve retornar a da unidade
        janela_unidade = self._make_janela(JanelaEntrega.StatusChoices.ABERTO, unidade=self.unidade)
        resultado = get_delivery_window(unidade=self.unidade)
        self.assertEqual(resultado, janela_unidade)

    def test_sem_janela_alguma_retorna_none(self):
        from apps.core.services import get_delivery_window
        self.assertIsNone(get_delivery_window())


# ─────────────────────────────────────────────
# Testes de can_user_edit_within_window
# ─────────────────────────────────────────────

class CanUserEditWithinWindowTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.hoje = timezone.now().date()
        self.unidade = Unidade.objects.create(nome="Unidade E", sigla="UE")
        self.coord = User.objects.create_user(
            email="coord@teste.com", password="pw",
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup@edit.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )

    def _make_janela_ativa(self):
        from django.utils import timezone
        return JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje,
            data_fim=self.hoje + timezone.timedelta(days=15),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )

    def test_desup_pode_editar_sem_janela(self):
        from apps.core.services import can_user_edit_within_window
        self.assertTrue(can_user_edit_within_window(self.desup))

    def test_desup_pode_editar_com_janela_fechada(self):
        from apps.core.services import can_user_edit_within_window
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje,
            data_fim=self.hoje,
            status=JanelaEntrega.StatusChoices.FECHADO,
        )
        self.assertTrue(can_user_edit_within_window(self.desup))

    def test_coord_pode_editar_com_janela_aberta(self):
        from apps.core.services import can_user_edit_within_window
        self._make_janela_ativa()
        self.assertTrue(can_user_edit_within_window(self.coord, self.unidade))

    def test_coord_nao_pode_editar_sem_janela(self):
        from apps.core.services import can_user_edit_within_window
        self.assertFalse(can_user_edit_within_window(self.coord, self.unidade))

    def test_coord_nao_pode_editar_com_janela_fechada(self):
        from apps.core.services import can_user_edit_within_window
        from django.utils import timezone
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje - timezone.timedelta(days=10),
            data_fim=self.hoje - timezone.timedelta(days=1),
            status=JanelaEntrega.StatusChoices.FECHADO,
        )
        self.assertFalse(can_user_edit_within_window(self.coord, self.unidade))

    def test_coord_pode_editar_com_janela_reaberta(self):
        from apps.core.services import can_user_edit_within_window
        from django.utils import timezone
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=self.hoje,
            data_fim=self.hoje + timezone.timedelta(days=10),
            status=JanelaEntrega.StatusChoices.REABERTO,
        )
        self.assertTrue(can_user_edit_within_window(self.coord, self.unidade))


# ─────────────────────────────────────────────
# Testes de bloqueio — manipulação direta de rota
# ─────────────────────────────────────────────

class EnforceWindowBlockingTests(TestCase):
    """
    Garante que um POST direto à rota (tentativa de burlar o bloqueio)
    é rejeitado pela camada de serviço quando a janela está fechada.
    """

    def setUp(self):
        from django.utils import timezone
        self.unidade = Unidade.objects.create(nome="Unidade B", sigla="UB")
        self.coord = User.objects.create_user(
            email="coord_block@teste.com", password="pw",
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_block@teste.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.factory = RequestFactory()

    def _make_request(self, user, method='post', path='/fake/'):
        from django.contrib.messages.storage.fallback import FallbackStorage
        req = getattr(self.factory, method)(path)
        req.user = user
        req.META['HTTP_REFERER'] = path
        req.session = {}
        req._messages = FallbackStorage(req)
        return req

    def test_enforce_retorna_none_quando_janela_aberta(self):
        """enforce_window_or_redirect deve retornar None (permitir) quando a janela está ativa."""
        from django.utils import timezone
        from apps.core.services import enforce_window_or_redirect
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje,
            data_fim=hoje + timezone.timedelta(days=10),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        req = self._make_request(self.coord)
        resultado = enforce_window_or_redirect(
            req, area_label="Matrizes", action_label="salvar matriz",
            unidade=self.unidade,
        )
        self.assertIsNone(resultado)

    def test_enforce_bloqueia_e_cria_notificacao_quando_janela_fechada(self):
        """POST direto sem janela ativa deve ser bloqueado e gerar notificação."""
        from apps.core.services import enforce_window_or_redirect
        req = self._make_request(self.coord)
        resultado = enforce_window_or_redirect(
            req, area_label="Matrizes", action_label="salvar matriz",
            unidade=self.unidade, fallback_url='/courses/matrices/',
        )
        # Deve retornar um redirect (não None)
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.status_code, 302)
        # Deve ter criado notificação de tentativa bloqueada
        self.assertTrue(
            Notificacao.objects.filter(titulo__icontains="Tentativa bloqueada").exists()
        )

    def test_enforce_nao_bloqueia_desup_mesmo_sem_janela(self):
        """DESUP nunca é bloqueada, independente do estado da janela."""
        from apps.core.services import enforce_window_or_redirect
        req = self._make_request(self.desup)
        resultado = enforce_window_or_redirect(
            req, area_label="Matrizes", action_label="salvar matriz",
            unidade=self.unidade,
        )
        self.assertIsNone(resultado)
        # Sem notificação para DESUP
        self.assertFalse(
            Notificacao.objects.filter(titulo__icontains="Tentativa bloqueada").exists()
        )

    def test_post_direto_coord_janela_reaberta_e_permitido(self):
        """Janela REABERTO dentro do prazo deve permitir edição para COORDENADOR."""
        from django.utils import timezone
        from apps.core.services import enforce_window_or_redirect
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje,
            data_fim=hoje + timezone.timedelta(days=5),
            status=JanelaEntrega.StatusChoices.REABERTO,
        )
        req = self._make_request(self.coord)
        resultado = enforce_window_or_redirect(
            req, area_label="Matrizes", action_label="salvar matriz",
            unidade=self.unidade,
        )
        self.assertIsNone(resultado)

    def test_post_direto_coord_janela_fora_prazo_e_bloqueado(self):
        """Janela ABERTO mas fora do prazo (data_fim no passado) deve bloquear."""
        from django.utils import timezone
        from apps.core.services import enforce_window_or_redirect
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje - timezone.timedelta(days=30),
            data_fim=hoje - timezone.timedelta(days=1),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        req = self._make_request(self.coord)
        resultado = enforce_window_or_redirect(
            req, area_label="Matrizes", action_label="salvar matriz",
            unidade=self.unidade, fallback_url='/courses/matrices/',
        )
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.status_code, 302)
