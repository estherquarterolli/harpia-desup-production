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

    def test_dashboard_redireciona_superuser_para_o_admin(self):
        """CORR-019: /dashboard/ não pode mais jogar o superuser no dashboard DESUP."""
        self.client.force_login(self.superuser)
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/admin/', target_status_code=200)

    def test_raiz_redireciona_superuser_para_o_admin(self):
        """CORR-019: a raiz '/' passa por DashboardView — mesmo destino."""
        self.client.force_login(self.superuser)
        response = self.client.get('/', follow=True)
        self.assertEqual(response.redirect_chain[-1][0], '/admin/')

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
# Datas da janela não podem ser anteriores a hoje (início == fim é permitido)
# ─────────────────────────────────────────────

class JanelaEntregaDataValidacaoTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        self.hoje = timezone.now().date()
        self.ontem = self.hoje - timezone.timedelta(days=1)
        self.amanha = self.hoje + timezone.timedelta(days=1)
        self.status = JanelaEntrega.StatusChoices.ABERTO.value

    def _create_form(self, inicio, fim):
        from apps.core.views import JanelaEntregaCreateForm
        return JanelaEntregaCreateForm(data={
            'semestre': '2026.1',
            'data_inicio': inicio,
            'data_fim': fim,
            'status': self.status,
            'unidade': '',
        })

    def test_inicio_no_passado_invalido(self):
        form = self._create_form(self.ontem, self.amanha)
        self.assertFalse(form.is_valid())
        self.assertIn('data_inicio', form.errors)

    def test_fim_no_passado_invalido(self):
        form = self._create_form(self.hoje, self.ontem)
        self.assertFalse(form.is_valid())
        self.assertIn('data_fim', form.errors)

    def test_inicio_igual_fim_hoje_valido(self):
        # Abertura/reabertura de 24h: início == fim é permitido.
        form = self._create_form(self.hoje, self.hoje)
        self.assertTrue(form.is_valid(), form.errors)

    def test_fim_antes_do_inicio_invalido(self):
        form = self._create_form(self.amanha, self.hoje)
        self.assertFalse(form.is_valid())
        self.assertIn('data_fim', form.errors)

    def test_datas_futuras_validas(self):
        form = self._create_form(self.hoje, self.amanha)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_mantendo_inicio_passado_permitido(self):
        # Editar (ex.: status) uma janela já em andamento não deve barrar o início
        # passado que não foi alterado.
        from apps.core.views import JanelaEntregaUpdateForm
        janela = JanelaEntrega.objects.create(
            semestre="2026.1", data_inicio=self.ontem, data_fim=self.amanha,
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        form = JanelaEntregaUpdateForm(instance=janela, data={
            'semestre': '2026.1',
            'data_inicio': self.ontem,
            'data_fim': self.amanha,
            'status': self.status,
            'unidade': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_mudando_inicio_para_passado_invalido(self):
        from apps.core.views import JanelaEntregaUpdateForm
        from django.utils import timezone
        janela = JanelaEntrega.objects.create(
            semestre="2026.1", data_inicio=self.ontem, data_fim=self.amanha,
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        form = JanelaEntregaUpdateForm(instance=janela, data={
            'semestre': '2026.1',
            'data_inicio': self.hoje - timezone.timedelta(days=3),  # nova data no passado
            'data_fim': self.amanha,
            'status': self.status,
            'unidade': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('data_inicio', form.errors)


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


class AtalhoDashboardTests(TestCase):
    """Feature: atalhos configuráveis do dashboard DESUP (por usuário)."""

    def setUp(self):
        from django.urls import reverse
        self.reverse = reverse
        self.desup = User.objects.create_user(
            email='atalho_desup@teste.com', password='x', perfil='DESUP', forcar_troca_senha=False,
        )
        self.desup2 = User.objects.create_user(
            email='atalho_desup2@teste.com', password='x', perfil='DESUP', forcar_troca_senha=False,
        )
        self.coord = User.objects.create_user(
            email='atalho_coord@teste.com', password='x', perfil='COORDENADOR_UNIDADE',
            forcar_troca_senha=False,
        )

    def test_desup_adiciona_atalho(self):
        from apps.core.models import AtalhoDashboard
        self.client.force_login(self.desup)
        resp = self.client.post(self.reverse('core:atalho_add'), {'chave': 'matrix_list'})
        self.assertRedirects(resp, self.reverse('dashboard_desup'))
        self.assertTrue(AtalhoDashboard.objects.filter(user=self.desup, chave='matrix_list').exists())

    def test_adiciona_multiplos_atalhos(self):
        from apps.core.models import AtalhoDashboard
        self.client.force_login(self.desup)
        resp = self.client.post(
            self.reverse('core:atalho_add'),
            {'chave': ['matrix_list', 'professor_list', 'adicionar_curso']},
        )
        self.assertRedirects(resp, self.reverse('dashboard_desup'))
        self.assertEqual(AtalhoDashboard.objects.filter(user=self.desup).count(), 3)

    def test_multiplos_ignora_invalidas_e_mantem_validas(self):
        from apps.core.models import AtalhoDashboard
        self.client.force_login(self.desup)
        self.client.post(
            self.reverse('core:atalho_add'),
            {'chave': ['matrix_list', 'rota_maliciosa']},
        )
        chaves = set(AtalhoDashboard.objects.filter(user=self.desup).values_list('chave', flat=True))
        self.assertEqual(chaves, {'matrix_list'})

    def test_chave_invalida_rejeitada(self):
        from apps.core.models import AtalhoDashboard
        self.client.force_login(self.desup)
        self.client.post(self.reverse('core:atalho_add'), {'chave': 'rota_maliciosa'})
        self.assertEqual(AtalhoDashboard.objects.filter(user=self.desup).count(), 0)

    def test_get_or_create_nao_duplica(self):
        from apps.core.models import AtalhoDashboard
        self.client.force_login(self.desup)
        self.client.post(self.reverse('core:atalho_add'), {'chave': 'matrix_list'})
        self.client.post(self.reverse('core:atalho_add'), {'chave': 'matrix_list'})
        self.assertEqual(AtalhoDashboard.objects.filter(user=self.desup, chave='matrix_list').count(), 1)

    def test_coord_bloqueado(self):
        from apps.core.models import AtalhoDashboard
        self.client.force_login(self.coord)
        resp = self.client.post(self.reverse('core:atalho_add'), {'chave': 'matrix_list'})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(AtalhoDashboard.objects.count(), 0)

    def test_remove_apenas_do_proprio_usuario(self):
        from apps.core.models import AtalhoDashboard
        atalho = AtalhoDashboard.objects.create(user=self.desup, chave='matrix_list')
        # desup2 (outro DESUP) não consegue remover atalho alheio → 404
        self.client.force_login(self.desup2)
        resp = self.client.post(self.reverse('core:atalho_remove', kwargs={'pk': atalho.pk}))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(AtalhoDashboard.objects.filter(pk=atalho.pk).exists())
        # dono remove com sucesso
        self.client.force_login(self.desup)
        resp2 = self.client.post(self.reverse('core:atalho_remove', kwargs={'pk': atalho.pk}))
        self.assertRedirects(resp2, self.reverse('dashboard_desup'))
        self.assertFalse(AtalhoDashboard.objects.filter(pk=atalho.pk).exists())

    def test_contexto_dashboard_traz_atalhos(self):
        from apps.core.models import AtalhoDashboard
        AtalhoDashboard.objects.create(user=self.desup, chave='matrix_list')
        self.client.force_login(self.desup)
        resp = self.client.get(self.reverse('dashboard_desup'))
        self.assertEqual(resp.status_code, 200)
        chaves_user = {a['label'] for a in resp.context['atalhos_user']}
        self.assertIn('Matrizes Curriculares', chaves_user)
        # a chave já adicionada não aparece nas disponíveis
        disponiveis = {op['chave'] for op in resp.context['atalhos_disponiveis']}
        self.assertNotIn('matrix_list', disponiveis)
        self.assertIn('professor_list', disponiveis)


# ══════════════════════════════════════════════════════════════════════════════
# CORR-014 / CORR-016 / CORR-010 — avisos duplicados, títulos e sidebar
# ══════════════════════════════════════════════════════════════════════════════
class AvisoJanelaFechadaUnicoTests(TestCase):
    """
    CORR-014: com a janela fechada e perfil de unidade, o aviso "Janela de entrega
    fechada" aparecia **duas vezes** — o banner do `base.html` (com o botão
    "Solicitar abertura") e um banner inline no template da tela. O inline foi
    removido; só o do `base.html` permanece.

    Observação: a frase "Janela de entrega fechada" também aparece 3× de forma fixa
    no `base.html` (o `<h2>` do modal `#windowLockModal`, sempre no DOM porém oculto,
    e dois defaults em JS). Por isso a contagem é feita sobre o **parágrafo do banner
    visível** (`<p class="font-black">…</p>`), que deve ser exatamente 1.
    """

    BANNER = '<p class="font-black">Janela de entrega fechada</p>'

    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade CORR014", sigla="U14")
        self.coord = User.objects.create_user(
            email="coord_corr014@teste.com", password="pw",
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade, forcar_troca_senha=False,
        )
        # Nenhuma JanelaEntrega criada => janela fechada para a unidade.
        self.client.force_login(self.coord)

    def _html(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_alocacao_curricular_mostra_um_unico_aviso(self):
        html = self._html('/alocacao-curricular/')

        self.assertEqual(html.count(self.BANNER), 1)          # antes eram 2
        self.assertEqual(html.count('windowClosedNotice'), 1)  # banner canônico do base
        self.assertIn('Solicitar abertura', html)              # o que tem o botão

    def test_extracurriculares_mostra_um_unico_aviso(self):
        html = self._html('/extracurriculares/pendencias/')

        self.assertEqual(html.count(self.BANNER), 1)
        self.assertEqual(html.count('windowClosedNotice'), 1)
        self.assertIn('Solicitar abertura', html)
        # Texto exclusivo do banner inline removido.
        self.assertNotIn(
            'O período de registro de justificativas extracurriculares está encerrado',
            html,
        )

    def test_desup_nao_ve_aviso_de_janela_fechada(self):
        """DESUP faz bypass da janela — nenhum banner (nem o do base) deve aparecer."""
        desup = User.objects.create_user(
            email="desup_corr014@teste.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.client.force_login(desup)

        html = self._html('/alocacao-curricular/')

        self.assertNotIn('windowClosedNotice', html)
        self.assertEqual(html.count(self.BANNER), 0)   # nenhum banner visível


class TituloDasTelasTests(TestCase):
    """CORR-016: telas que não definiam {% block title %}/{% block header_title %}
    caíam no default "HARPIA" do base.html."""

    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade CORR016", sigla="U16")
        self.desup = User.objects.create_user(
            email="desup_corr016@teste.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.client.force_login(self.desup)

    def test_alocacao_curricular_tem_titulo_proprio(self):
        html = self.client.get('/alocacao-curricular/').content.decode()

        self.assertIn('<title>Alocação Curricular — Harpia-DESUP</title>', html)
        self.assertIn('Alocação Curricular', html)
        self.assertNotIn('<title>HARPIA</title>', html)

    def test_demais_telas_sem_titulo_foram_corrigidas(self):
        casos = {
            '/core/unidades/': 'Unidades de Ensino — Harpia-DESUP',
            '/core/entregas/': 'Janelas de Entrega — Harpia-DESUP',
        }
        for url, titulo in casos.items():
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                html = resp.content.decode()
                self.assertIn(f'<title>{titulo}</title>', html)
                self.assertNotIn('<title>HARPIA</title>', html)


class SidebarIconesCentralizadosTests(TestCase):
    """CORR-010: no rail recolhido (w-20) os ícones ficavam encostados à esquerda."""

    def setUp(self):
        self.desup = User.objects.create_user(
            email="desup_corr010@teste.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.client.force_login(self.desup)

    def test_links_da_sidebar_centralizam_quando_recolhido(self):
        html = self.client.get('/core/unidades/').content.decode()

        # Todo .sidebar-link centraliza recolhido e alinha à esquerda no hover.
        total_links = html.count('class="sidebar-link')
        self.assertGreater(total_links, 0)
        self.assertEqual(
            html.count('justify-center group-hover:justify-start'), total_links,
        )
        # O botão "Sair" também virou .sidebar-link (antes ficava de fora).
        self.assertIn('sidebar-link w-full flex items-center justify-center', html)


# ══════════════════════════════════════════════════════════════════════════════
# JANELA DE ENTREGA — regressões da auditoria (BUG-1 a BUG-6)
# ══════════════════════════════════════════════════════════════════════════════

class _JanelaRegressaoBase(TestCase):
    """Fixtures comuns às regressões da janela de entrega."""

    def setUp(self):
        from django.utils import timezone
        self.hoje = timezone.localdate()
        self.unidade = Unidade.objects.create(nome="Unidade Regressão", sigla="URG")

    def janela(self, *, status=JanelaEntrega.StatusChoices.ABERTO, unidade=None,
               dias_inicio=0, dias_fim=15, semestre="2026.1"):
        from django.utils import timezone
        return JanelaEntrega.objects.create(
            semestre=semestre,
            data_inicio=self.hoje + timezone.timedelta(days=dias_inicio),
            data_fim=self.hoje + timezone.timedelta(days=dias_fim),
            status=status,
            unidade=unidade,
        )


class JanelaOverrideFechadoRecortadoPorDataTests(_JanelaRegressaoBase):
    """
    BUG-1: `get_delivery_window` tratava QUALQUER janela Fechado da unidade como
    override absoluto, sem recorte de data. Como `fechar_janelas_expiradas` grava
    Fechado em toda janela vencida, a primeira janela da unidade que expirava virava
    um bloqueio eterno — a DESUP abria janela nova e a unidade seguia travada.
    """

    def test_janela_fechada_vencida_nao_bloqueia_nova_janela_da_unidade(self):
        from apps.core.services import fechar_janelas_expiradas, get_delivery_window

        # Janela antiga da unidade, já vencida: o fechamento automático a marca Fechado.
        antiga = self.janela(unidade=self.unidade, dias_inicio=-60, dias_fim=-30,
                             semestre="2025.1")
        fechar_janelas_expiradas()
        antiga.refresh_from_db()
        self.assertEqual(antiga.status, JanelaEntrega.StatusChoices.FECHADO)

        nova = self.janela(unidade=self.unidade, dias_inicio=0, dias_fim=10)

        self.assertEqual(get_delivery_window(unidade=self.unidade), nova)

    def test_janela_fechada_vencida_nao_bloqueia_janela_global_aberta(self):
        from apps.core.services import get_delivery_window

        self.janela(status=JanelaEntrega.StatusChoices.FECHADO, unidade=self.unidade,
                    dias_inicio=-60, dias_fim=-30, semestre="2025.1")
        global_aberta = self.janela(unidade=None, dias_inicio=0, dias_fim=10)

        self.assertEqual(get_delivery_window(unidade=self.unidade), global_aberta)

    def test_janela_fechada_vigente_continua_bloqueando(self):
        """O override não foi removido: enquanto a janela Fechado cobrir hoje, vale."""
        from apps.core.services import get_delivery_window

        self.janela(unidade=None, dias_inicio=0, dias_fim=10)  # global aberta
        self.janela(status=JanelaEntrega.StatusChoices.FECHADO, unidade=self.unidade,
                    dias_inicio=-1, dias_fim=5, semestre="2026.2")

        self.assertIsNone(get_delivery_window(unidade=self.unidade))

    def test_janela_fechada_ainda_futura_nao_bloqueia_hoje(self):
        from apps.core.services import get_delivery_window

        vigente = self.janela(unidade=self.unidade, dias_inicio=0, dias_fim=10)
        # Fechamento programado para daqui a um mês não pode valer hoje.
        self.janela(status=JanelaEntrega.StatusChoices.FECHADO, unidade=self.unidade,
                    dias_inicio=30, dias_fim=40, semestre="2026.2")

        self.assertEqual(get_delivery_window(unidade=self.unidade), vigente)


class JanelaFuturaNaoMataVigenteTests(_JanelaRegressaoBase):
    """
    BUG-2: o service pegava só a janela de `data_inicio` mais recente da unidade
    (`order_by('-data_inicio')`) e, se ela não estivesse valendo hoje, desistia das
    demais janelas da unidade. Uma janela FUTURA criada depois derrubava a vigente.
    """

    def test_janela_futura_criada_depois_nao_derruba_a_vigente(self):
        from apps.core.services import get_delivery_window

        vigente = self.janela(unidade=self.unidade, dias_inicio=-1, dias_fim=20)
        # Criada depois e com data_inicio maior: era ela que o order_by escolhia.
        self.janela(unidade=self.unidade, dias_inicio=5, dias_fim=10, semestre="2026.2")

        self.assertEqual(get_delivery_window(unidade=self.unidade), vigente)

    def test_janela_futura_da_unidade_nao_bloqueia_nem_cai_na_global(self):
        """Sem janela global nenhuma, a unidade tem que continuar liberada."""
        from apps.core.services import can_user_edit_within_window

        coord = User.objects.create_user(
            email="coord_bug2@teste.com", password="pw",
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade, forcar_troca_senha=False,
        )
        self.janela(unidade=self.unidade, dias_inicio=-1, dias_fim=20)
        self.janela(unidade=self.unidade, dias_inicio=5, dias_fim=10, semestre="2026.2")

        self.assertTrue(can_user_edit_within_window(coord, self.unidade))

    def test_janela_global_futura_nao_derruba_a_global_vigente(self):
        from apps.core.services import get_delivery_window

        vigente = self.janela(unidade=None, dias_inicio=-1, dias_fim=20)
        self.janela(unidade=None, dias_inicio=5, dias_fim=10, semestre="2026.2")

        self.assertEqual(get_delivery_window(), vigente)


class JanelaUsaDataLocalTests(_JanelaRegressaoBase):
    """
    BUG-3: `timezone.now().date()` devolve a data em UTC. Com USE_TZ=True e
    TIME_ZONE=America/Sao_Paulo (UTC-3), das 21h à meia-noite o sistema já estava
    "no dia seguinte": a janela fechava 3h cedo e `fechar_janelas_expiradas` gravava
    Fechado — o que, somado ao BUG-1, era irreversível.

    Os testes congelam o relógio às 23h de Brasília (02h UTC do dia seguinte).
    """

    def _as_23h_de_brasilia(self):
        """
        Instante em que o UTC já virou o dia, mas São Paulo não.

        Devolvido em UTC de propósito: é assim que `timezone.now()` responde com
        USE_TZ=True, e é justamente por isso que `now().date()` adiantava o dia.
        """
        import datetime
        from django.utils import timezone

        instante = datetime.datetime.combine(
            self.hoje, datetime.time(23, 0), tzinfo=timezone.get_current_timezone(),
        )
        return instante.astimezone(datetime.timezone.utc)

    def test_is_ativa_no_ultimo_dia_as_23h(self):
        from unittest import mock
        from django.utils import timezone

        janela = self.janela(dias_inicio=-5, dias_fim=0)  # último dia é hoje
        with mock.patch.object(timezone, 'now', return_value=self._as_23h_de_brasilia()):
            # Sanidade do cenário: em UTC já é amanhã.
            self.assertEqual(timezone.now().date(), self.hoje + timezone.timedelta(days=1))
            self.assertTrue(janela.is_ativa)

    def test_fechar_janelas_expiradas_nao_fecha_a_do_ultimo_dia_as_23h(self):
        from unittest import mock
        from django.utils import timezone
        from apps.core.services import fechar_janelas_expiradas

        janela = self.janela(dias_inicio=-5, dias_fim=0)
        with mock.patch.object(timezone, 'now', return_value=self._as_23h_de_brasilia()):
            fechar_janelas_expiradas()

        janela.refresh_from_db()
        self.assertEqual(janela.status, JanelaEntrega.StatusChoices.ABERTO)

    def test_get_delivery_window_devolve_a_janela_do_ultimo_dia_as_23h(self):
        from unittest import mock
        from django.utils import timezone
        from apps.core.services import get_delivery_window

        janela = self.janela(dias_inicio=-5, dias_fim=0)
        with mock.patch.object(timezone, 'now', return_value=self._as_23h_de_brasilia()):
            self.assertEqual(get_delivery_window(), janela)

    def test_create_form_aceita_janela_comecando_hoje_as_23h(self):
        from unittest import mock
        from django.utils import timezone
        from apps.core.views import JanelaEntregaCreateForm

        with mock.patch.object(timezone, 'now', return_value=self._as_23h_de_brasilia()):
            form = JanelaEntregaCreateForm(data={
                'semestre': '2026.1',
                'data_inicio': self.hoje,
                'data_fim': self.hoje + timezone.timedelta(days=5),
                'status': JanelaEntrega.StatusChoices.ABERTO.value,
                'unidade': '',
            })
            self.assertTrue(form.is_valid(), form.errors)


class JanelaBannerUsaAJanelaDaUnidadeTests(_JanelaRegressaoBase):
    """
    BUG-4 / BUG-5: o context processor tinha query própria, com
    `order_by('-unidade')` — que, por causa de `Unidade.Meta.ordering = ['nome']`,
    vira `ORDER BY core_unidade.nome DESC` e não "específica antes de global"
    (o PostgreSQL 16 devolvia a global primeiro). Agora ele delega a
    `get_delivery_window`, que consulta a janela da unidade ANTES da global —
    resultado independente do backend do banco.
    """

    URL_COM_JANELA = '/alocacao-curricular/'

    def setUp(self):
        super().setUp()
        self.coord = User.objects.create_user(
            email="coord_banner@teste.com", password="pw",
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_banner@teste.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )

    def test_banner_mostra_a_data_fim_da_janela_da_unidade_e_nao_da_global(self):
        self.janela(unidade=None, dias_inicio=-1, dias_fim=30)          # global
        da_unidade = self.janela(unidade=self.unidade, dias_inicio=-1, dias_fim=7,
                                 semestre="2026.2")
        self.client.force_login(self.coord)

        resp = self.client.get(self.URL_COM_JANELA)

        self.assertEqual(resp.context['janela_ativa'], da_unidade)
        self.assertEqual(
            resp.context['janela_data_fim'], da_unidade.data_fim.strftime('%d/%m/%Y'),
        )

    def test_banner_e_bloqueio_concordam_com_override_fechado_vigente(self):
        """BUG-5: antes dava 'banner verde + POST bloqueado' (e vice-versa)."""
        from apps.core.services import can_user_edit_within_window

        self.janela(unidade=None, dias_inicio=-1, dias_fim=30)
        self.janela(status=JanelaEntrega.StatusChoices.FECHADO, unidade=self.unidade,
                    dias_inicio=-1, dias_fim=7, semestre="2026.2")
        self.client.force_login(self.coord)

        resp = self.client.get(self.URL_COM_JANELA)

        self.assertTrue(resp.context.get('janela_fechada'))
        self.assertIsNone(resp.context.get('janela_ativa'))
        self.assertFalse(can_user_edit_within_window(self.coord, self.unidade))

    def test_banner_verde_com_janela_futura_da_unidade_concorda_com_o_bloqueio(self):
        """
        BUG-2 + BUG-5: com janela vigente + janela futura da unidade, o processor
        dizia "aberta até <data da vigente>" enquanto o service devolvia None.
        """
        from apps.core.services import can_user_edit_within_window

        vigente = self.janela(unidade=self.unidade, dias_inicio=-1, dias_fim=20)
        self.janela(unidade=self.unidade, dias_inicio=5, dias_fim=10, semestre="2026.2")
        self.client.force_login(self.coord)

        resp = self.client.get(self.URL_COM_JANELA)

        self.assertEqual(resp.context['janela_ativa'], vigente)
        self.assertTrue(can_user_edit_within_window(self.coord, self.unidade))

    def test_desup_nunca_recebe_janela_fechada_no_contexto(self):
        """Bypass preservado: a DESUP não vê o aviso de janela fechada."""
        self.client.force_login(self.desup)

        resp = self.client.get(self.URL_COM_JANELA)

        self.assertIsNone(resp.context.get('janela_fechada'))

    def test_processor_so_atua_nas_areas_com_janela(self):
        """Escopo preservado: fora de alocação/extracurriculares não há contexto."""
        self.janela(unidade=self.unidade, dias_inicio=-1, dias_fim=20)
        self.client.force_login(self.coord)

        resp = self.client.get('/dashboard/unidade/')

        self.assertIsNone(resp.context.get('janela_ativa'))
        self.assertIsNone(resp.context.get('janela_fechada'))


class JanelaEntregaFormValidacaoTests(_JanelaRegressaoBase):
    """
    BUG-6: `JanelaEntregaForm` (o form do admin) não tinha `clean()` — aceitava
    `data_fim < data_inicio` e semestre livre. Sobreposição de janelas no mesmo
    escopo não era validada em form nenhum, e é justamente o gatilho do BUG-2.
    As regras agora moram em `JanelaEntregaValidacaoMixin` e valem nos três forms.
    """

    def _dados(self, **overrides):
        from django.utils import timezone
        dados = {
            'semestre': '2026.1',
            'data_inicio': self.hoje,
            'data_fim': self.hoje + timezone.timedelta(days=10),
            'status': JanelaEntrega.StatusChoices.ABERTO.value,
            'unidade': '',
        }
        dados.update(overrides)
        return dados

    def _admin_form(self, **overrides):
        from apps.core.forms import JanelaEntregaForm
        return JanelaEntregaForm(data=self._dados(**overrides))

    def test_admin_form_rejeita_fim_antes_do_inicio(self):
        from django.utils import timezone
        form = self._admin_form(data_fim=self.hoje - timezone.timedelta(days=1))
        self.assertFalse(form.is_valid())
        self.assertIn('data_fim', form.errors)

    def test_admin_form_rejeita_semestre_invalido(self):
        for valor in ('banana!!', '2026', '2026.3', '26.1', '2026/1'):
            with self.subTest(semestre=valor):
                form = self._admin_form(semestre=valor)
                self.assertFalse(form.is_valid())
                self.assertIn('semestre', form.errors)

    def test_admin_form_aceita_semestre_valido(self):
        for valor in ('2026.1', '2026.2'):
            with self.subTest(semestre=valor):
                form = self._admin_form(semestre=valor)
                self.assertTrue(form.is_valid(), form.errors)

    def test_admin_form_rejeita_janela_sobreposta_no_mesmo_escopo(self):
        from django.utils import timezone
        self.janela(unidade=None, dias_inicio=0, dias_fim=10)

        form = self._admin_form(
            semestre='2026.2',
            data_inicio=self.hoje + timezone.timedelta(days=5),
            data_fim=self.hoje + timezone.timedelta(days=20),
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_admin_form_aceita_janela_de_outro_escopo_no_mesmo_periodo(self):
        """Global e específica podem coexistir — a específica é que tem prioridade."""
        self.janela(unidade=None, dias_inicio=0, dias_fim=10)

        form = self._admin_form(semestre='2026.2', unidade=self.unidade.pk)

        self.assertTrue(form.is_valid(), form.errors)

    def test_admin_form_permite_editar_a_propria_janela(self):
        """A checagem de sobreposição não pode acusar a própria instância."""
        from apps.core.forms import JanelaEntregaForm
        janela = self.janela(unidade=None, dias_inicio=0, dias_fim=10)

        form = JanelaEntregaForm(data=self._dados(), instance=janela)

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_da_tela_rejeita_semestre_invalido(self):
        from apps.core.views import JanelaEntregaCreateForm
        form = JanelaEntregaCreateForm(data=self._dados(semestre='banana!!'))
        self.assertFalse(form.is_valid())
        self.assertIn('semestre', form.errors)

    def test_create_form_da_tela_rejeita_sobreposicao(self):
        """Sobreposição é o gatilho do BUG-2: a tela da DESUP também tem que barrar."""
        from django.utils import timezone
        from apps.core.views import JanelaEntregaCreateForm
        self.janela(unidade=self.unidade, dias_inicio=0, dias_fim=20)

        form = JanelaEntregaCreateForm(data=self._dados(
            semestre='2026.2',
            data_inicio=self.hoje + timezone.timedelta(days=5),
            data_fim=self.hoje + timezone.timedelta(days=10),
            unidade=self.unidade.pk,
        ))

        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_update_form_da_tela_rejeita_semestre_invalido(self):
        from apps.core.views import JanelaEntregaUpdateForm
        janela = self.janela(unidade=None, dias_inicio=0, dias_fim=10)

        form = JanelaEntregaUpdateForm(instance=janela, data=self._dados(semestre='2026'))

        self.assertFalse(form.is_valid())
        self.assertIn('semestre', form.errors)


class JanelaConfirmDeleteTemplateTests(_JanelaRegressaoBase):
    """BUG-7: o GET da confirmação de exclusão estourava TemplateDoesNotExist."""

    def test_get_da_confirmacao_de_exclusao_renderiza(self):
        from django.urls import reverse
        desup = User.objects.create_user(
            email="desup_delete@teste.com", password="pw",
            perfil='DESUP', forcar_troca_senha=False,
        )
        janela = self.janela(unidade=self.unidade)
        self.client.force_login(desup)

        resp = self.client.get(reverse('core:janela_delete', kwargs={'pk': janela.pk}))

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'core/janela_confirm_delete.html')
        self.assertContains(resp, 'Sim, excluir')
