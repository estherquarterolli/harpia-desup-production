import re
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import Unidade

from .models import DEFAULT_USER_PASSWORD, EmailPasswordResetToken, User
from .services import password_reset_token_hash


@override_settings(
    PASSWORD_RESET_TOKEN_TTL_SECONDS=3600,
    PASSWORD_RESET_COOLDOWN_SECONDS=900,
)
class EmailPasswordResetWorkflowTests(TestCase):
    def setUp(self):
        self.old_password = 'SenhaAntiga@2026'
        self.user = User.objects.create_user(
            email='recuperacao@teste.com',
            password=self.old_password,
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            forcar_troca_senha=False,
        )

    def _request_link(self, email=None):
        with patch('apps.accounts.services.send_email_task.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/accounts/forgot-password/', {
                    'email': email or self.user.email,
                })
        return response, delay

    def _raw_token_from_mock(self, delay):
        message = delay.call_args.kwargs['message']
        match = re.search(r'/accounts/redefinir-senha/([^/\s]+)/', message)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_envia_token_aleatorio_armazena_so_hash_e_redefine_senha(self):
        response, delay = self._request_link()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Se o e-mail estiver cadastrado e ativo')
        delay.assert_called_once()

        raw_token = self._raw_token_from_mock(delay)
        stored = EmailPasswordResetToken.objects.get(user=self.user)
        self.assertEqual(stored.token_hash, password_reset_token_hash(raw_token))
        self.assertNotEqual(stored.token_hash, raw_token)
        self.assertNotIn(raw_token, stored.token_hash)

        url = f'/accounts/redefinir-senha/{raw_token}/'
        form_page = self.client.get(url)
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(form_page, 'name="new_password1"')

        new_password = 'NovaSenha@2026'
        result = self.client.post(url, {
            'new_password1': new_password,
            'new_password2': new_password,
        })
        self.assertRedirects(result, '/login/?changed=1', fetch_redirect_response=False)

        self.user.refresh_from_db()
        stored.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.user.forcar_troca_senha)
        self.assertTrue(stored.usado)
        self.assertIsNotNone(stored.usado_em)

        reused = self.client.get(url)
        self.assertContains(reused, 'inválido, expirou ou já foi utilizado')

    def test_resposta_nao_revela_se_email_existe(self):
        existing_response, existing_delay = self._request_link()
        unknown_response, unknown_delay = self._request_link('nao-existe@teste.com')

        self.assertEqual(
            existing_response.context['success'],
            unknown_response.context['success'],
        )
        self.assertNotContains(unknown_response, 'não foi encontrado')
        existing_delay.assert_called_once()
        unknown_delay.assert_not_called()

    def test_cooldown_nao_dispara_varios_emails(self):
        first_response, first_delay = self._request_link()
        second_response, second_delay = self._request_link()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_delay.assert_called_once()
        second_delay.assert_not_called()
        self.assertEqual(EmailPasswordResetToken.objects.filter(user=self.user).count(), 1)

    def test_token_expirado_nao_abre_formulario(self):
        raw_token = 'token-expirado-seguro'
        EmailPasswordResetToken.objects.create(
            user=self.user,
            token_hash=password_reset_token_hash(raw_token),
            expira_em=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get(f'/accounts/redefinir-senha/{raw_token}/')

        self.assertContains(response, 'inválido, expirou ou já foi utilizado')
        self.assertNotContains(response, 'name="new_password1"')


@override_settings(PASSWORD_RESET_COOLDOWN_SECONDS=900)
class DesupUserManagementTests(TestCase):
    def setUp(self):
        self.password = 'Senha@2026'
        self.unidade = Unidade.objects.create(
            nome='Unidade Gestão de Usuários',
            sigla='UGU',
        )
        self.desup = User.objects.create_user(
            email='desup-usuarios@teste.com',
            password=self.password,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        self.target = User.objects.create_user(
            email='coord-alvo@teste.com',
            password=self.password,
            perfil=User.Perfil.COORDENADOR_UNIDADE,
            forcar_troca_senha=False,
            last_login=timezone.now(),
        )
        self.client.login(email=self.desup.email, password=self.password)

    def test_lista_exibe_ultimo_acesso_e_botao(self):
        response = self.client.get('/accounts/usuarios/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.target.email)
        expected_last_login = timezone.localtime(self.target.last_login).strftime('%d/%m/%Y %H:%M')
        self.assertContains(response, expected_last_login)
        self.assertContains(
            response,
            f'/accounts/usuarios/{self.target.pk}/redefinir-senha/',
        )
        self.assertContains(response, '/accounts/usuarios/criar/')
        self.assertContains(response, 'Criar usuário')

    def test_formulario_oferece_apenas_desup_e_coordenador(self):
        response = self.client.get('/accounts/usuarios/criar/')

        self.assertEqual(response.status_code, 200)
        choices = dict(response.context['form'].fields['perfil'].choices)
        self.assertEqual(
            choices,
            {
                User.Perfil.DESUP: 'Administrador DESUP',
                User.Perfil.COORDENADOR_UNIDADE: 'Coordenador de Unidade',
            },
        )
        self.assertContains(response, 'Confirmo que os dados e o perfil estão corretos')

    def test_cria_coordenador_com_unidade_e_envia_link_de_senha(self):
        with patch('apps.accounts.services.send_email_task.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/accounts/usuarios/criar/', {
                    'first_name': 'Maria',
                    'last_name': 'Coordenadora',
                    'email': 'nova-coordenadora@teste.com',
                    'perfil': User.Perfil.COORDENADOR_UNIDADE,
                    'unidade': self.unidade.pk,
                    'confirmar': 'sim',
                })

        self.assertRedirects(response, '/accounts/usuarios/')
        created = User.objects.get(email='nova-coordenadora@teste.com')
        self.assertEqual(created.perfil, User.Perfil.COORDENADOR_UNIDADE)
        self.assertEqual(created.unidade, self.unidade)
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(created.forcar_troca_senha)
        self.assertTrue(created.has_usable_password())
        self.assertFalse(created.check_password(DEFAULT_USER_PASSWORD))
        self.assertTrue(EmailPasswordResetToken.objects.filter(user=created).exists())
        delay.assert_called_once()

    def test_cria_administrador_desup_sem_unidade_e_sem_superpoderes(self):
        with patch('apps.accounts.services.send_email_task.delay'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/accounts/usuarios/criar/', {
                    'email': 'novo-desup@teste.com',
                    'perfil': User.Perfil.DESUP,
                    # Mesmo manipulado no POST, unidade não se aplica a DESUP.
                    'unidade': self.unidade.pk,
                    'confirmar': 'sim',
                })

        self.assertRedirects(response, '/accounts/usuarios/')
        created = User.objects.get(email='novo-desup@teste.com')
        self.assertEqual(created.perfil, User.Perfil.DESUP)
        self.assertIsNone(created.unidade)
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_coordenador_exige_unidade(self):
        response = self.client.post('/accounts/usuarios/criar/', {
            'email': 'sem-unidade@teste.com',
            'perfil': User.Perfil.COORDENADOR_UNIDADE,
            'confirmar': 'sim',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selecione a unidade do coordenador.')
        self.assertFalse(User.objects.filter(email='sem-unidade@teste.com').exists())

    def test_criacao_exige_confirmacao(self):
        response = self.client.post('/accounts/usuarios/criar/', {
            'email': 'sem-confirmacao@teste.com',
            'perfil': User.Perfil.DESUP,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Marque a confirmação antes de criar o usuário.')
        self.assertFalse(User.objects.filter(email='sem-confirmacao@teste.com').exists())

    def test_reset_exige_tela_e_checkbox_de_confirmacao(self):
        url = f'/accounts/usuarios/{self.target.pk}/redefinir-senha/'

        confirm_page = self.client.get(url)
        self.assertEqual(confirm_page.status_code, 200)
        self.assertContains(confirm_page, 'Confirmo que desejo enviar')

        with patch('apps.accounts.services.send_email_task.delay') as delay:
            missing_confirmation = self.client.post(url, {})
        self.assertEqual(missing_confirmation.status_code, 200)
        self.assertContains(missing_confirmation, 'Marque a confirmação')
        delay.assert_not_called()

        with patch('apps.accounts.services.send_email_task.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                confirmed = self.client.post(url, {'confirmar': 'sim'})
        self.assertRedirects(confirmed, '/accounts/usuarios/')
        delay.assert_called_once()

    def test_coordenador_nao_acessa_gestao_de_usuarios(self):
        self.client.logout()
        self.client.login(email=self.target.email, password=self.password)

        self.assertEqual(self.client.get('/accounts/usuarios/').status_code, 403)
        self.assertEqual(self.client.get('/accounts/usuarios/criar/').status_code, 403)

    def test_desup_nao_pode_resetar_superadmin(self):
        superadmin = User.objects.create_superuser(
            email='superadmin-alvo@teste.com',
            password=self.password,
        )

        response = self.client.get(
            f'/accounts/usuarios/{superadmin.pk}/redefinir-senha/'
        )

        self.assertEqual(response.status_code, 404)
