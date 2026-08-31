from django.test import Client, TestCase
from django.contrib.auth import get_user_model, authenticate
from django.db import IntegrityError
from apps.accounts.forms import CustomUserCreationForm

User = get_user_model()

class UserAuthenticationTests(TestCase):
    def setUp(self):
        self.email = "coordenador@desup.com"
        self.password = "senha_segura_123"
        self.user_data = {
            "email": self.email,
            "password": self.password,
            "perfil": User.Perfil.DESUP
        }

    def test_create_user_with_email_success(self):
        """Verifica se um usuário pode ser criado com e-mail corretamente."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, self.email)
        self.assertTrue(user.check_password(self.password))
        self.assertEqual(user.get_username(), self.email)

    def test_authentication_works_using_email(self):
        """Garante que a autenticação (login) funciona utilizando o campo de e-mail."""
        User.objects.create_user(**self.user_data)
        # Note que o Django usa 'username' como argumento no authenticate, 
        # mas ele mapeia para o USERNAME_FIELD (que definimos como email)
        user = authenticate(username=self.email, password=self.password)
        self.assertIsNotNone(user, "Autenticação falhou para o e-mail fornecido.")
        self.assertEqual(user.email, self.email)

    def test_duplicate_email_raises_error(self):
        """Garante que o sistema impede a criação de dois usuários com o mesmo e-mail."""
        User.objects.create_user(**self.user_data)
        
        with self.assertRaises(IntegrityError):
            # Tenta criar outro usuário com o mesmo e-mail
            User.objects.create_user(
                email=self.email,
                password="outra_senha"
            )

    def test_admin_creation_form_handles_username_collision(self):
        """Garante que o admin não quebra quando o e-mail novo colide com um username legado."""
        User.objects.create(
            username=self.email,
            email="legacy@teste.com",
            perfil=User.Perfil.DESUP,
        )

        form = CustomUserCreationForm(data={
            "email": self.email,
            "perfil": User.Perfil.COORDENADOR_UNIDADE,
            "forcar_troca_senha": "on",
        })

        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()
        self.assertEqual(user.email, self.email)
        self.assertNotEqual(user.username, self.email)
        self.assertTrue(user.username.startswith(self.email))

    def test_role_field_works_as_expected(self):
        """Verifica se o campo de perfil (role) armazena os valores e escolhas corretamente."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.perfil, User.Perfil.DESUP)
        # CORR-021: rótulo passou a distinguir a Coordenação DESUP do perfil ADMIN (TI).
        self.assertEqual(user.get_perfil_display(), 'Coordenador DESUP')
        
        # Testa o valor default (que agora deve ser COORDENADOR_UNIDADE)
        user_default = User.objects.create_user(
            email="coordenador_unidade@teste.com",
            password="password"
        )
        self.assertEqual(user_default.perfil, User.Perfil.COORDENADOR_UNIDADE)


class UserRedirectTests(TestCase):
    def setUp(self):
        self.password = "senha123"
        self.desup_user = User.objects.create_user(
            email="desup@teste.com",
            password=self.password,
            perfil='DESUP'
        )
        self.unidade_user = User.objects.create_user(
            email="unidade@teste.com",
            password=self.password,
            perfil='COORDENADOR_UNIDADE'
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@teste.com",
            password=self.password,
        )

    def test_desup_redirects_to_correct_dashboard(self):
        from apps.accounts.views import get_redirect_url_for_user
        url = get_redirect_url_for_user(self.desup_user)
        self.assertEqual(url, '/dashboard/desup/')

    def test_unidade_redirects_to_correct_dashboard(self):
        from apps.accounts.views import get_redirect_url_for_user
        url = get_redirect_url_for_user(self.unidade_user)
        self.assertEqual(url, '/dashboard/unidade/')

    def test_superuser_redirects_to_admin(self):
        from apps.accounts.views import get_redirect_url_for_user
        url = get_redirect_url_for_user(self.admin_user)
        self.assertEqual(url, '/admin/')

    def test_superuser_dashboard_url_aponta_para_o_admin(self):
        """CORR-019: o superuser (DEV/ADMIN) não é operador DESUP — vai para o /admin/.

        Antes esta função devolvia '/dashboard/desup/', e como '/' e
        LOGIN_REDIRECT_URL passam por ela, o admin caía no dashboard da DESUP.
        """
        from apps.accounts.views import get_dashboard_url_for_user
        url = get_dashboard_url_for_user(self.admin_user)
        self.assertEqual(url, '/admin/')

    def test_superuser_tem_rota_unica_entre_as_duas_funcoes(self):
        """CORR-019: as duas funções de roteamento não podem mais divergir."""
        from apps.accounts.views import (
            get_dashboard_url_for_user,
            get_redirect_url_for_user,
        )
        self.assertEqual(
            get_redirect_url_for_user(self.admin_user),
            get_dashboard_url_for_user(self.admin_user),
        )

    def test_regular_post_login_redirects_without_blank_response(self):
        response = self.client.post('/login/', {
            'email': self.desup_user.email,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/dashboard/desup/')

    def test_htmx_post_login_uses_hx_redirect(self):
        client = Client(HTTP_HX_REQUEST='true')
        response = client.post('/login/', {
            'email': self.desup_user.email,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['HX-Redirect'], '/dashboard/desup/')
        self.assertEqual(response.content, b'')


from apps.core.models import Notificacao
from django.core.exceptions import ValidationError
from apps.accounts.validators import ComplexPasswordValidator
from apps.accounts.models import PasswordResetRequest, DEFAULT_USER_PASSWORD

class UserSecurityTests(TestCase):
    def setUp(self):
        self.password = "senha123"
        self.user = User.objects.create_user(
            email="forca@teste.com",
            password=self.password,
            perfil='COORDENADOR_UNIDADE'
        )
        self.desup = User.objects.create_user(
            email="desup_test_admin@teste.com",
            password=self.password,
            perfil='DESUP',
            forcar_troca_senha=False,
        )
        self.superuser = User.objects.create_superuser(
            email="super@teste.com",
            password=self.password,
        )

    def test_password_change_forced_on_login(self):
        # By default, forcar_troca_senha is True
        self.assertTrue(self.user.forcar_troca_senha)
        
        # Log in
        self.client.login(email=self.user.email, password=self.password)
        
        # Try accessing the dashboard, should be redirected to password_change
        response = self.client.get('/dashboard/unidade/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/accounts/password_change/' in response['Location'])

    def test_password_change_requires_authenticated_session(self):
        response = self.client.get('/accounts/password_change/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_password_change_updates_only_authenticated_user(self):
        new_password = "Senha@12345"
        self.client.login(email=self.user.email, password=self.password)

        response = self.client.post('/accounts/password_change/', {
            'new_password1': new_password,
            'new_password2': new_password,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/login/?changed=1')

        self.user.refresh_from_db()
        self.desup.refresh_from_db()
        self.assertFalse(self.user.forcar_troca_senha)
        self.assertTrue(self.user.check_password(new_password))
        self.assertTrue(self.desup.check_password(self.password))

    def test_superuser_is_not_forced_to_change_password(self):
        self.assertFalse(self.superuser.forcar_troca_senha)
        self.client.login(email=self.superuser.email, password=self.password)
        response = self.client.get('/admin/')
        self.assertNotEqual(response.status_code, 302)
        self.assertNotIn('/accounts/password_change/', response.get('Location', ''))

    def test_password_validator_complexity(self):
        validator = ComplexPasswordValidator()
        
        # Missing uppercase
        with self.assertRaises(ValidationError):
            validator.validate("senha@123")
            
        # Missing digit
        with self.assertRaises(ValidationError):
            validator.validate("Senha@abc")
            
        # Missing special character
        with self.assertRaises(ValidationError):
            validator.validate("Senha123")
            
        # Valid password
        try:
            validator.validate("Senha@123")
        except ValidationError:
            self.fail("ComplexPasswordValidator raised ValidationError unexpectedly!")

    def test_forgot_password_creates_notification(self):
        # Submit forgot password form
        response = self.client.post('/accounts/forgot-password/', {
            'email': self.user.email
        })
        self.assertEqual(response.status_code, 200)
        
        # Check if a Notificacao was created
        notif = Notificacao.objects.filter(titulo="Solicitação de Reset de Senha").first()
        self.assertIsNotNone(notif)
        self.assertTrue(self.user.email in notif.mensagem)

    def test_password_reset_approval_requires_valid_token_and_authorized_user(self):
        reset_request = PasswordResetRequest.objects.create(user=self.user)
        self.client.login(email=self.desup.email, password=self.password)

        response = self.client.post(f'/accounts/reset/aprovar/{reset_request.token}/')

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        reset_request.refresh_from_db()
        self.assertTrue(self.user.check_password(DEFAULT_USER_PASSWORD))
        self.assertTrue(self.user.forcar_troca_senha)
        self.assertTrue(reset_request.finalizado)
        self.assertEqual(reset_request.aprovado_por, self.desup)


from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from apps.accounts.models import SelfPasswordChangeRequest
from apps.core.models import AuditoriaGlobal

class PasswordChangeWorkflowTests(TestCase):
    def setUp(self):
        self.password = "Senha@123"
        self.user = User.objects.create_user(
            email="workflow@teste.com",
            password=self.password,
            perfil='COORDENADOR_UNIDADE',
            forcar_troca_senha=False
        )
        self.client.login(email=self.user.email, password=self.password)

    # ── CORR-018: o prompt de e-mail foi removido ───────────────────
    def test_tela_de_troca_nao_pede_email(self):
        """A tela não tem mais campo de e-mail — só mostra o do usuário logado."""
        response = self.client.get('/accounts/password_change/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="email"')
        self.assertNotContains(response, 'Confirme seu e-mail')
        self.assertContains(response, self.user.email)

    def test_email_do_post_e_ignorado(self):
        """Regressão CORR-018: mesmo forjando outro e-mail, o link vai para o do logado."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/accounts/password_change/', {
                'email': 'errado@teste.com',   # ignorado pela view
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        # O caminho de "e-mail divergente" deixou de existir.
        self.assertFalse(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_EMAIL_MISMATCH").exists()
        )

    def test_password_change_link_sent(self):
        """Envio do link sem informar e-mail algum.

        O envio roda em `transaction.on_commit`; sob `TestCase` a transação é
        revertida, então é preciso `captureOnCommitCallbacks(execute=True)` para
        que o callback dispare (era a causa do teste falhar com 0 != 1).
        """
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/accounts/password_change/', {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enviamos um link de troca de senha para')

        # Verificar e-mail enviado
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Link para troca de senha', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

        # Verificar auditoria
        self.assertTrue(AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_LINK_SENT").exists())
        
        # Verificar request criado
        self.assertTrue(SelfPasswordChangeRequest.objects.filter(user=self.user, usado=False).exists())

    # ── CORR-020: rate-limit de 1 pedido por dia ────────────────────
    def test_segundo_pedido_no_mesmo_dia_e_bloqueado(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/accounts/password_change/', {})
        self.assertEqual(SelfPasswordChangeRequest.objects.filter(user=self.user).count(), 1)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/accounts/password_change/', {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nas últimas 24 horas')
        # Nenhum token novo e nenhum e-mail novo.
        self.assertEqual(SelfPasswordChangeRequest.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_RATE_LIMITED").exists()
        )

    def test_novo_pedido_liberado_apos_24h(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/accounts/password_change/', {})

        # Envelhece o pedido para fora da janela de cooldown.
        SelfPasswordChangeRequest.objects.filter(user=self.user).update(
            criado_em=timezone.now() - timedelta(days=1, minutes=1)
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/accounts/password_change/', {})

        self.assertContains(response, 'Enviamos um link de troca de senha para')
        self.assertEqual(SelfPasswordChangeRequest.objects.filter(user=self.user).count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(DEBUG=True)
    def test_rate_limit_nao_se_aplica_em_debug(self):
        for _ in range(3):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/accounts/password_change/', {})
            self.assertContains(response, 'Enviamos um link de troca de senha para')

        self.assertEqual(SelfPasswordChangeRequest.objects.filter(user=self.user).count(), 3)

    def test_rate_limit_e_por_usuario(self):
        outro = User.objects.create_user(
            email="outro_corr020@teste.com", password=self.password,
            perfil='COORDENADOR_UNIDADE', forcar_troca_senha=False,
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/accounts/password_change/', {})

        self.client.force_login(outro)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/accounts/password_change/', {})

        self.assertContains(response, 'Enviamos um link de troca de senha para')
        self.assertEqual(SelfPasswordChangeRequest.objects.filter(user=outro).count(), 1)

    def test_password_change_token_invalid(self):
        """Tentar acessar o link com token inexistente ou já utilizado/expirado."""
        # Token inexistente -> deve dar 404 (get_object_or_404)
        import uuid
        fake_token = uuid.uuid4()
        response = self.client.get(f'/accounts/password_change/confirm/{fake_token}/')
        self.assertEqual(response.status_code, 404)
        
        # Token usado
        req = SelfPasswordChangeRequest.objects.create(user=self.user, usado=True)
        response = self.client.get(f'/accounts/password_change/confirm/{req.token}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este link de troca de senha expirou ou ja foi utilizado.')
        self.assertTrue(AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_TOKEN_INVALID").exists())

    def test_password_change_success(self):
        """Sucesso na troca de senha por e-mail."""
        req = SelfPasswordChangeRequest.objects.create(user=self.user)
        new_password = "NovaSenha@123"
        
        response = self.client.post(f'/accounts/password_change/confirm/{req.token}/', {
            'new_password1': new_password,
            'new_password2': new_password,
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login/?changed=1' in response['Location'])
        
        # Verificar senha atualizada
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        
        # Verificar token usado
        req.refresh_from_db()
        self.assertTrue(req.usado)
        self.assertIsNotNone(req.usado_em)
        
        # Verificar auditoria
        self.assertTrue(AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGED_BY_EMAIL_TOKEN").exists())



# ══════════════════════════════════════════════════════════════════════════════
# CORR-017 — Menu de usuário: e-mail visível e página de Perfil própria
# ══════════════════════════════════════════════════════════════════════════════
from django.urls import reverse
from apps.core.models import Unidade


class PerfilPageTests(TestCase):
    """
    Antes: o componente de usuário mostrava `get_full_name|default:email|upper` +
    `get_perfil_display` (rendendo "ADMIN Alberto" em conta legada) e o item
    "Meu Perfil" apontava para `password_change` — não existia tela de perfil.
    """

    def setUp(self):
        self.password = "Senha@123"
        self.unidade = Unidade.objects.create(nome="Unidade CORR017", sigla="U17")
        self.coord = User.objects.create_user(
            email="coord_corr017@teste.com",
            password=self.password,
            perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade,
            forcar_troca_senha=False,
            first_name="Alberto",
        )

    def test_pagina_de_perfil_existe_e_e_somente_leitura(self):
        self.client.force_login(self.coord)
        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')
        self.assertContains(response, self.coord.email)
        self.assertContains(response, 'Coordenador de Unidade')
        self.assertContains(response, self.unidade.sigla)
        # Somente leitura: nenhum formulário de edição de dados na página.
        self.assertNotContains(response, '<input type="text"')

    def test_perfil_exige_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_menu_mostra_email_e_nao_o_nome(self):
        self.client.force_login(self.coord)
        html = self.client.get(reverse('profile')).content.decode()

        self.assertIn(self.coord.email, html)
        # "ALBERTO" (get_full_name em caixa alta) não pode mais aparecer no menu.
        self.assertNotIn('>ALBERTO<', html)

    def test_meu_perfil_nao_aponta_mais_para_troca_de_senha(self):
        self.client.force_login(self.coord)
        html = self.client.get(reverse('profile')).content.decode()

        self.assertIn(f'href="{reverse("profile")}"', html)
        # Os dois itens coexistem no menu, cada um com seu destino.
        self.assertIn('Meu Perfil', html)
        self.assertIn('Alterar senha', html)

    def test_superuser_tambem_ve_meu_perfil(self):
        superuser = User.objects.create_superuser(
            email="admin_corr017@teste.com", password=self.password, forcar_troca_senha=False,
        )
        self.client.force_login(superuser)
        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, superuser.email)
        # CORR-021: o rótulo agora vem do próprio perfil oficial ADMIN.
        self.assertContains(response, 'Administrador (TI DESUP)')


# ══════════════════════════════════════════════════════════════════════════════
# CORR-021 — Perfil ADMIN (TI DESUP) oficial
# ══════════════════════════════════════════════════════════════════════════════
class PerfilAdminOficialTests(TestCase):
    """
    São três perfis oficiais: ADMIN (TI DESUP), DESUP (Coordenação) e
    COORDENADOR_UNIDADE. O ADMIN cuida do desenvolvimento e usa **só** o admin do
    Django — não é perfil operacional. A operação do dia a dia é dividida apenas
    entre Coord. DESUP e Coord. Unidade.
    """

    def setUp(self):
        self.password = "Senha@123"
        self.unidade = Unidade.objects.create(nome="Unidade CORR021", sigla="U21")
        self.admin = User.objects.create_user(
            email="ti_corr021@teste.com", password=self.password,
            perfil=User.Perfil.ADMIN, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_corr021@teste.com", password=self.password,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )

    # ── O perfil existe e é oficial ─────────────────────────────────
    def test_tres_perfis_oficiais(self):
        self.assertEqual(
            [p.value for p in User.Perfil],
            ['ADMIN', 'DESUP', 'COORDENADOR_UNIDADE'],
        )
        self.assertEqual(self.admin.get_perfil_display(), 'Administrador (TI DESUP)')
        self.assertEqual(self.desup.get_perfil_display(), 'Coordenador DESUP')

    def test_admin_ganha_is_staff_automaticamente(self):
        """Sem is_staff o ADMIN não entraria na única tela que usa."""
        self.assertTrue(self.admin.is_staff)

        # também ao promover uma conta existente
        self.desup.perfil = User.Perfil.ADMIN
        self.desup.save()
        self.desup.refresh_from_db()
        self.assertTrue(self.desup.is_staff)

    def test_create_superuser_nasce_como_admin(self):
        su = User.objects.create_superuser(email="su_corr021@teste.com", password=self.password)
        self.assertEqual(su.perfil, User.Perfil.ADMIN)

    def test_create_superuser_aceita_perfil_explicito(self):
        """Uma conta que também opera a DESUP continua possível."""
        su = User.objects.create_superuser(
            email="su_desup_corr021@teste.com", password=self.password,
            perfil=User.Perfil.DESUP,
        )
        self.assertEqual(su.perfil, User.Perfil.DESUP)

    # ── Roteamento ──────────────────────────────────────────────────
    def test_admin_e_roteado_para_o_admin_do_django(self):
        from apps.accounts.views import (
            get_dashboard_url_for_user,
            get_redirect_url_for_user,
        )
        self.assertEqual(get_redirect_url_for_user(self.admin), '/admin/')
        self.assertEqual(get_dashboard_url_for_user(self.admin), '/admin/')

    def test_desup_continua_indo_para_o_dashboard(self):
        from apps.accounts.views import get_dashboard_url_for_user
        self.assertEqual(get_dashboard_url_for_user(self.desup), '/dashboard/desup/')

    def test_login_do_admin_leva_ao_admin_do_django(self):
        response = self.client.post('/login/', {
            'email': self.admin.email, 'password': self.password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/admin/')

    # ── Telas operacionais ──────────────────────────────────────────
    def test_admin_nao_entra_em_tela_operacional(self):
        """Redirect (não 403): a tela certa para o perfil é outra."""
        self.client.force_login(self.admin)

        for url in ('/dashboard/desup/', '/core/unidades/', '/alocacao-curricular/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response['Location'], '/admin/')

    def test_redirect_do_admin_nao_entra_em_loop(self):
        """O destino (/admin/) não pode devolver o ADMIN para a rota operacional."""
        self.client.force_login(self.admin)
        response = self.client.get('/dashboard/', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], '/admin/')
        # Uma cadeia curta prova que ninguém devolve o ADMIN para trás.
        self.assertLessEqual(len(response.redirect_chain), 2)

    def test_admin_htmx_recebe_hx_redirect(self):
        self.client.force_login(self.admin)
        response = self.client.get('/dashboard/desup/', HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], '/admin/')

    def test_desup_nao_e_afetado_pelo_gate(self):
        self.client.force_login(self.desup)
        response = self.client.get('/dashboard/desup/')
        self.assertEqual(response.status_code, 200)

    def test_superuser_com_perfil_desup_mantem_acesso_operacional(self):
        """Instalações existentes: superuser com perfil DESUP não é trancado fora."""
        su = User.objects.create_superuser(
            email="su_legado_corr021@teste.com", password=self.password,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )
        self.client.force_login(su)
        response = self.client.get('/dashboard/desup/')
        self.assertEqual(response.status_code, 200)

    def test_perfil_admin_aparece_na_pagina_de_perfil(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administrador (TI DESUP)')
        # ADMIN não tem unidade — o bloco não deve aparecer.
        self.assertNotContains(response, 'Unidade</dt>')


# ══════════════════════════════════════════════════════════════════════════════
# SEC-001 / SEC-002 — cadeia de takeover via notificação + aprovação de reset
# ══════════════════════════════════════════════════════════════════════════════
class CadeiaTakeoverResetSenhaTests(TestCase):
    """
    Regressão da cadeia encontrada na auditoria adversarial de 2026-08-01:

      1. `ForgotPasswordView` cria uma `Notificacao` cujo `url_acao` carrega o
         token de aprovação do reset.
      2. `MarcarNotificacaoLidaView` carregava a notificação SEM escopo e fazia o
         `redirect(url_acao)` FORA do `if` de permissão — qualquer usuário logado
         lia o token de qualquer outra pessoa iterando o `pk`.
      3. `ApprovePasswordResetView` comparava `reset_req.user.unidade !=
         request.user.unidade`; com os dois lados `None` a checagem passava.
      4. A aprovação grava `DEFAULT_USER_PASSWORD` — senha conhecida.

    Resultado: coordenador sem unidade virava superusuário.
    """

    def setUp(self):
        self.password = "Senha@123"
        self.unidade_a = Unidade.objects.create(nome="Unidade SEC A", sigla="SGA")
        self.unidade_b = Unidade.objects.create(nome="Unidade SEC B", sigla="SGB")

        self.superuser = User.objects.create_superuser(
            email="root_sec@teste.com", password=self.password, forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_sec@teste.com", password=self.password,
            perfil=User.Perfil.DESUP, forcar_troca_senha=False,
        )
        # Coordenador SEM unidade — estado alcançável: `unidade` é null=True.
        self.coord_sem_unidade = User.objects.create_user(
            email="coord_sem_unidade@teste.com", password=self.password,
            perfil=User.Perfil.COORDENADOR_UNIDADE, forcar_troca_senha=False,
        )
        self.coord_a = User.objects.create_user(
            email="coord_a_sec@teste.com", password=self.password,
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=self.unidade_a,
            forcar_troca_senha=False,
        )
        self.coord_a2 = User.objects.create_user(
            email="coord_a2_sec@teste.com", password=self.password,
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=self.unidade_a,
            forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email="coord_b_sec@teste.com", password=self.password,
            perfil=User.Perfil.COORDENADOR_UNIDADE, unidade=self.unidade_b,
            forcar_troca_senha=False,
        )

    def _pedir_reset(self, alvo):
        self.client.post('/accounts/forgot-password/', {'email': alvo.email})
        return PasswordResetRequest.objects.filter(user=alvo).latest('criado_em')

    # ── SEC-001: vazamento do token pela notificação ────────────────
    def test_notificacao_alheia_nao_vaza_url_acao(self):
        reset = self._pedir_reset(self.superuser)
        notif = Notificacao.objects.filter(url_acao__contains=str(reset.token)).first()
        self.assertIsNotNone(notif, "pré-condição: o token vai no url_acao da notificação")

        self.client.force_login(self.coord_sem_unidade)
        resp = self.client.get(f'/core/notificacoes/{notif.pk}/lida/')

        # 404 e não 403: 403 confirmaria que a notificação existe.
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Location', resp)
        notif.refresh_from_db()
        self.assertFalse(notif.lida, "não pode nem marcar como lida a notificação alheia")

    def test_destinatario_continua_acessando_a_propria_notificacao(self):
        notif = Notificacao.objects.create(
            destinatario=self.coord_a, titulo="t", mensagem="m", url_acao="/dashboard/",
        )
        self.client.force_login(self.coord_a)
        resp = self.client.get(f'/core/notificacoes/{notif.pk}/lida/')

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/dashboard/')
        notif.refresh_from_db()
        self.assertTrue(notif.lida)

    def test_url_acao_externa_nao_redireciona_para_fora(self):
        notif = Notificacao.objects.create(
            destinatario=self.coord_a, titulo="t", mensagem="m",
            url_acao="https://exemplo-malicioso.test/phishing",
        )
        self.client.force_login(self.coord_a)
        resp = self.client.get(f'/core/notificacoes/{notif.pk}/lida/')

        self.assertEqual(resp['Location'], '/')

    # ── SEC-002: guard da aprovação ─────────────────────────────────
    def test_coordenador_sem_unidade_nao_aprova_reset_de_superusuario(self):
        reset = self._pedir_reset(self.superuser)
        self.client.force_login(self.coord_sem_unidade)

        resp = self.client.post(f'/accounts/reset/aprovar/{reset.token}/')

        self.assertEqual(resp.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertFalse(self.superuser.check_password(DEFAULT_USER_PASSWORD))
        reset.refresh_from_db()
        self.assertFalse(reset.finalizado)

    def test_coordenador_nao_aprova_reset_de_desup_da_propria_unidade(self):
        desup_com_unidade = User.objects.create_user(
            email="desup_ua_sec@teste.com", password=self.password,
            perfil=User.Perfil.DESUP, unidade=self.unidade_a, forcar_troca_senha=False,
        )
        reset = self._pedir_reset(desup_com_unidade)
        self.client.force_login(self.coord_a)

        resp = self.client.post(f'/accounts/reset/aprovar/{reset.token}/')

        self.assertEqual(resp.status_code, 403)
        desup_com_unidade.refresh_from_db()
        self.assertFalse(desup_com_unidade.check_password(DEFAULT_USER_PASSWORD))

    def test_coordenador_nao_aprova_reset_de_outra_unidade(self):
        reset = self._pedir_reset(self.coord_b)
        self.client.force_login(self.coord_a)

        resp = self.client.post(f'/accounts/reset/aprovar/{reset.token}/')

        self.assertEqual(resp.status_code, 403)

    def test_coordenador_aprova_par_da_mesma_unidade(self):
        """O caso legítimo tem que continuar funcionando."""
        reset = self._pedir_reset(self.coord_a2)
        self.client.force_login(self.coord_a)

        resp = self.client.post(f'/accounts/reset/aprovar/{reset.token}/')

        self.assertEqual(resp.status_code, 200)
        self.coord_a2.refresh_from_db()
        self.assertTrue(self.coord_a2.check_password(DEFAULT_USER_PASSWORD))
        self.assertTrue(self.coord_a2.forcar_troca_senha)

    def test_desup_aprova_qualquer_um(self):
        reset = self._pedir_reset(self.coord_b)
        self.client.force_login(self.desup)

        resp = self.client.post(f'/accounts/reset/aprovar/{reset.token}/')

        self.assertEqual(resp.status_code, 200)
        self.coord_b.refresh_from_db()
        self.assertTrue(self.coord_b.check_password(DEFAULT_USER_PASSWORD))

    def test_tentativa_negada_fica_na_auditoria(self):
        reset = self._pedir_reset(self.superuser)
        self.client.force_login(self.coord_sem_unidade)

        self.client.post(f'/accounts/reset/aprovar/{reset.token}/')

        self.assertTrue(
            AuditoriaGlobal.objects.filter(acao="PASSWORD_RESET_APPROVAL_DENIED").exists()
        )

    # ── Token não vai mais para quem não pode aprovar ───────────────
    def test_reset_de_desup_nao_notifica_coordenadores(self):
        desup_com_unidade = User.objects.create_user(
            email="desup_ua2_sec@teste.com", password=self.password,
            perfil=User.Perfil.DESUP, unidade=self.unidade_a, forcar_troca_senha=False,
        )
        self._pedir_reset(desup_com_unidade)

        destinatarios = set(
            Notificacao.objects.filter(titulo="Solicitação de Reset de Senha")
            .values_list('destinatario__email', flat=True)
        )
        self.assertNotIn(self.coord_a.email, destinatarios)
        self.assertIn(self.desup.email, destinatarios)

    def test_reset_de_coordenador_ainda_notifica_a_unidade(self):
        self._pedir_reset(self.coord_a2)

        destinatarios = set(
            Notificacao.objects.filter(titulo="Solicitação de Reset de Senha")
            .values_list('destinatario__email', flat=True)
        )
        self.assertIn(self.coord_a.email, destinatarios)
