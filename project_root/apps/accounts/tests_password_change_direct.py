from django.test import TestCase

from apps.core.models import AuditoriaGlobal

from .models import User


class DirectPasswordChangeTests(TestCase):
    def setUp(self):
        self.current_password = 'SenhaAtual@2026'
        self.new_password = 'SenhaNova@2026'
        self.user = User.objects.create_user(
            email='troca-direta@teste.com',
            password=self.current_password,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.client.login(email=self.user.email, password=self.current_password)

    def test_formulario_exige_atual_nova_e_confirmacao(self):
        response = self.client.get('/accounts/password_change/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="old_password"')
        self.assertContains(response, 'name="new_password1"')
        self.assertContains(response, 'name="new_password2"')

    def test_senha_atual_incorreta_nao_altera_a_conta(self):
        response = self.client.post('/accounts/password_change/', {
            'old_password': 'SenhaErrada@2026',
            'new_password1': self.new_password,
            'new_password2': self.new_password,
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.current_password))
        self.assertFalse(self.user.check_password(self.new_password))

    def test_confirmacao_diferente_nao_altera_a_conta(self):
        response = self.client.post('/accounts/password_change/', {
            'old_password': self.current_password,
            'new_password1': self.new_password,
            'new_password2': 'OutraSenha@2026',
        })

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.current_password))

    def test_usuario_altera_senha_e_permanece_autenticado(self):
        response = self.client.post('/accounts/password_change/', {
            'old_password': self.current_password,
            'new_password1': self.new_password,
            'new_password2': self.new_password,
        })

        self.assertRedirects(response, '/accounts/perfil/')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.forcar_troca_senha)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertTrue(
            AuditoriaGlobal.objects.filter(
                usuario=self.user,
                acao='PASSWORD_CHANGED_BY_USER',
            ).exists()
        )

    def test_primeiro_acesso_tambem_exige_a_senha_atual(self):
        self.user.forcar_troca_senha = True
        self.user.save(update_fields=['forcar_troca_senha'])

        response = self.client.post('/accounts/password_change/', {
            'old_password': self.current_password,
            'new_password1': self.new_password,
            'new_password2': self.new_password,
        })

        self.assertRedirects(response, '/accounts/perfil/')
        self.user.refresh_from_db()
        self.assertFalse(self.user.forcar_troca_senha)


class SupportButtonsRemovedTests(TestCase):
    def test_login_nao_exibe_botao_de_suporte(self):
        response = self.client.get('/login/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'login-support')
        self.assertNotContains(response, '>Suporte<')
