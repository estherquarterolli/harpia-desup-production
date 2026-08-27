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
        self.assertEqual(user.get_perfil_display(), 'DESUP')
        
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

    def test_superuser_dashboard_url_points_to_desup_dashboard(self):
        from apps.accounts.views import get_dashboard_url_for_user
        url = get_dashboard_url_for_user(self.admin_user)
        self.assertEqual(url, '/dashboard/desup/')

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


from django.core import mail
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

    def test_password_change_email_mismatch(self):
        """Simular um usuário autenticado enviando um e-mail diferente do dele."""
        response = self.client.post('/accounts/password_change/', {
            'email': 'errado@teste.com'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe o mesmo e-mail utilizado no seu login.')
        
        # Verificar auditoria
        audit = AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_EMAIL_MISMATCH").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.email, 'errado@teste.com')

    def test_password_change_link_sent(self):
        """Simular o envio do e-mail correto."""
        response = self.client.post('/accounts/password_change/', {
            'email': self.user.email
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enviamos um link de troca de senha para o seu e-mail.')
        
        # Verificar e-mail enviado
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Link para troca de senha', mail.outbox[0].subject)
        
        # Verificar auditoria
        self.assertTrue(AuditoriaGlobal.objects.filter(acao="PASSWORD_CHANGE_LINK_SENT").exists())
        
        # Verificar request criado
        self.assertTrue(SelfPasswordChangeRequest.objects.filter(user=self.user, usado=False).exists())

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

