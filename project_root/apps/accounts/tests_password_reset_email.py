import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.core.models import AuditoriaGlobal, Unidade

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

    def test_redefine_senha_em_https_com_csrf_ativo(self):
        _, delay = self._request_link()
        raw_token = self._raw_token_from_mock(delay)
        url = f'/accounts/redefinir-senha/{raw_token}/'
        client = Client(enforce_csrf_checks=True)

        page = client.get(url, secure=True)
        # Preserva o Referer no POST local, sem vazar o token para outros sites.
        self.assertContains(page, '<meta name="referrer" content="same-origin">')
        self.assertIn('no-store', page.headers['Cache-Control'])
        csrf_token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            page.content.decode(),
        ).group(1)
        new_password = 'NovaSenhaSegura@2026'

        invalid = client.post(url, {
            'csrfmiddlewaretoken': csrf_token,
            'new_password1': new_password,
            'new_password2': 'ConfirmacaoDiferente@2026',
        }, secure=True, HTTP_ORIGIN='https://testserver')
        self.assertEqual(invalid.status_code, 200)
        self.assertFormError(
            invalid.context['form'], 'new_password2',
            'Os dois campos de senha não correspondem.',
        )
        self.assertFalse(EmailPasswordResetToken.objects.get(user=self.user).usado)
        csrf_token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            invalid.content.decode(),
        ).group(1)

        response = client.post(url, {
            'csrfmiddlewaretoken': csrf_token,
            'new_password1': new_password,
            'new_password2': new_password,
        }, secure=True, HTTP_REFERER=f'https://testserver{url}')

        self.assertRedirects(response, '/login/?changed=1', fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertTrue(EmailPasswordResetToken.objects.get(user=self.user).usado)

    def test_redefinicao_mantem_protecao_csrf(self):
        _, delay = self._request_link()
        raw_token = self._raw_token_from_mock(delay)
        url = f'/accounts/redefinir-senha/{raw_token}/'
        client = Client(enforce_csrf_checks=True)
        client.get(url, secure=True)
        csrf_token = client.cookies['csrftoken'].value

        for token, headers in (
            ('', {'HTTP_REFERER': f'https://testserver{url}'}),
            ('x' * 32, {'HTTP_REFERER': f'https://testserver{url}'}),
            (csrf_token, {'HTTP_ORIGIN': 'https://outro-site.example'}),
            (csrf_token, {}),
        ):
            with self.subTest(token=bool(token), headers=headers):
                response = client.post(url, {
                    'csrfmiddlewaretoken': token,
                    'new_password1': 'NovaSenhaSegura@2026',
                    'new_password2': 'NovaSenhaSegura@2026',
                }, secure=True, **headers)

                self.assertEqual(response.status_code, 403)
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(self.old_password))
                self.assertFalse(EmailPasswordResetToken.objects.get(user=self.user).usado)

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


@override_settings(
    PASSWORD_RESET_COOLDOWN_SECONDS=900,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='desup@harpia.test',
    SITE_URL='https://harpia.test/',
)
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
        self.assertNotContains(
            response,
            'Crie contas, consulte o último acesso e envie links seguros',
        )

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
        self.assertIn('first_name', response.context['form'].fields)
        self.assertNotIn('last_name', response.context['form'].fields)
        self.assertTrue(response.context['form'].fields['first_name'].required)
        self.assertNotContains(response, 'Confirmo que os dados e o perfil estão corretos')
        self.assertNotContains(response, 'A senha não será exibida para a DESUP')
        self.assertNotContains(response, 'Sobrenome')
        self.assertContains(response, 'Acessa todas as unidades')
        self.assertContains(response, 'Acessa somente a unidade vinculada')

    def test_cria_coordenador_com_senha_padrao_e_troca_obrigatoria(self):
        with patch('apps.accounts.services.send_email_task.delay') as delay:
            response = self.client.post('/accounts/usuarios/criar/', {
                'first_name': 'Maria',
                'email': 'nova-coordenadora@teste.com',
                'perfil': User.Perfil.COORDENADOR_UNIDADE,
                'unidade': self.unidade.pk,
            }, follow=True)

        self.assertRedirects(response, '/accounts/usuarios/')
        created = User.objects.get(email='nova-coordenadora@teste.com')
        self.assertEqual(created.perfil, User.Perfil.COORDENADOR_UNIDADE)
        self.assertEqual(created.first_name, 'Maria')
        self.assertEqual(created.last_name, '')
        self.assertEqual(created.unidade, self.unidade)
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(created.forcar_troca_senha)
        self.assertTrue(created.has_usable_password())
        self.assertTrue(created.check_password(DEFAULT_USER_PASSWORD))
        self.assertFalse(EmailPasswordResetToken.objects.filter(user=created).exists())
        delay.assert_not_called()
        self.assertContains(response, 'Usuário criado com sucesso.')

    def test_cria_administrador_desup_sem_unidade_e_sem_superpoderes(self):
        with patch('apps.accounts.services.send_email_task.delay') as delay:
            response = self.client.post('/accounts/usuarios/criar/', {
                'email': 'novo-desup@teste.com',
                'first_name': 'Joana',
                'perfil': User.Perfil.DESUP,
                # Mesmo manipulado no POST, unidade não se aplica a DESUP.
                'unidade': self.unidade.pk,
            })

        self.assertRedirects(response, '/accounts/usuarios/')
        created = User.objects.get(email='novo-desup@teste.com')
        self.assertEqual(created.perfil, User.Perfil.DESUP)
        self.assertIsNone(created.unidade)
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(created.check_password(DEFAULT_USER_PASSWORD))
        delay.assert_not_called()

    def test_coordenador_exige_unidade(self):
        response = self.client.post('/accounts/usuarios/criar/', {
            'first_name': 'Sem Unidade',
            'email': 'sem-unidade@teste.com',
            'perfil': User.Perfil.COORDENADOR_UNIDADE,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Selecione a unidade do coordenador.')
        self.assertFalse(User.objects.filter(email='sem-unidade@teste.com').exists())

    def test_criacao_exige_nome(self):
        response = self.client.post('/accounts/usuarios/criar/', {
            'email': 'sem-nome@teste.com',
            'perfil': User.Perfil.DESUP,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'first_name',
            'Este campo é obrigatório.',
        )
        self.assertFalse(User.objects.filter(email='sem-nome@teste.com').exists())

    def test_reset_exige_tela_e_checkbox_de_confirmacao(self):
        url = f'/accounts/usuarios/{self.target.pk}/redefinir-senha/'

        confirm_page = self.client.get(url)
        self.assertEqual(confirm_page.status_code, 200)
        self.assertContains(confirm_page, 'Confirmo a redefinição da senha deste usuário.')
        self.assertEqual(len(mail.outbox), 0)

        missing_confirmation = self.client.post(url, {})
        self.assertEqual(missing_confirmation.status_code, 200)
        self.assertContains(missing_confirmation, 'Marque a confirmação')
        self.assertEqual(len(mail.outbox), 0)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(self.password))
        self.assertFalse(self.target.forcar_troca_senha)

        confirmed = self.client.post(url, {'confirmar': 'sim'})
        self.assertRedirects(confirmed, '/accounts/usuarios/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].body.startswith('Olá!\n'))
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(DEFAULT_USER_PASSWORD))
        self.assertTrue(self.target.forcar_troca_senha)

    def test_reset_envia_credenciais_personalizadas_e_confirma_para_desup(self):
        self.target.first_name = 'Maria'
        self.target.last_name = 'Silva'
        self.target.save(update_fields=['first_name', 'last_name'])

        response = self.client.post(
            f'/accounts/usuarios/{self.target.pk}/redefinir-senha/',
            {'confirmar': 'sim'},
        )

        self.assertRedirects(response, '/accounts/usuarios/')
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.target.email])
        self.assertEqual(email.from_email, 'desup@harpia.test')
        self.assertEqual(email.subject, 'HARPIA - Sua senha foi redefinida')
        self.assertEqual(email.content_subtype, 'plain')
        self.assertEqual(email.body, (
            'Olá, Maria Silva!\n\n'
            'Informamos que sua senha de acesso ao HARPIA foi redefinida.\n'
            'Seguem suas credenciais temporárias:\n\n'
            f'Acesso: {self.target.email}\n'
            f'Senha: {DEFAULT_USER_PASSWORD}\n\n'
            'Será necessário cadastrar uma nova senha no primeiro acesso à conta.\n'
            'A senha temporária diferencia maiúsculas e minúsculas.\n\n'
            'Acesse em: https://harpia.test/login/\n\n'
            'Para novas solicitações ou dúvidas, utilize a aba Suporte dentro da plataforma.'
        ))
        avisos = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn('E-mail com as credenciais temporárias enviado ao usuário.', avisos)
        self.assertTrue(any(DEFAULT_USER_PASSWORD in aviso for aviso in avisos))
        self.assertFalse(EmailPasswordResetToken.objects.filter(user=self.target).exists())
        auditoria = AuditoriaGlobal.objects.get(acao='DESUP_PASSWORD_FORCE_RESET')
        self.assertEqual(auditoria.objeto_id, str(self.target.pk))
        self.assertNotIn(DEFAULT_USER_PASSWORD, auditoria.detalhes)

    def test_reset_mantem_senha_e_auditoria_quando_email_falha(self):
        for resultado in (SMTPException('detalhe-sigiloso'), 0):
            with self.subTest(resultado=type(resultado).__name__):
                AuditoriaGlobal.objects.filter(acao='DESUP_PASSWORD_FORCE_RESET').delete()
                self.target.set_password(self.password)
                self.target.forcar_troca_senha = False
                self.target.save(update_fields=['password', 'forcar_troca_senha'])
                envio = (
                    {'side_effect': resultado} if isinstance(resultado, Exception)
                    else {'return_value': resultado}
                )
                with patch('apps.accounts.services.send_mail', **envio) as send:
                    with self.assertLogs('apps.accounts.services', level='ERROR') as logs:
                        response = self.client.post(
                            f'/accounts/usuarios/{self.target.pk}/redefinir-senha/',
                            {'confirmar': 'sim'},
                        )

                self.assertRedirects(response, '/accounts/usuarios/')
                send.assert_called_once()
                self.target.refresh_from_db()
                self.assertTrue(self.target.check_password(DEFAULT_USER_PASSWORD))
                self.assertTrue(self.target.forcar_troca_senha)
                self.assertTrue(AuditoriaGlobal.objects.filter(
                    acao='DESUP_PASSWORD_FORCE_RESET', objeto_id=str(self.target.pk),
                ).exists())
                avisos = [str(message) for message in get_messages(response.wsgi_request)]
                self.assertIn(
                    'Senha redefinida, mas não foi possível confirmar o envio do e-mail. '
                    'Avise o usuário por outro meio.',
                    avisos,
                )
                self.assertNotIn('E-mail com as credenciais temporárias enviado ao usuário.', avisos)
                self.assertEqual(len(mail.outbox), 0)
                texto_log = '\n'.join(logs.output)
                self.assertIn(f'user_id={self.target.pk}', texto_log)
                for segredo in ('detalhe-sigiloso', DEFAULT_USER_PASSWORD, self.target.email):
                    self.assertNotIn(segredo, texto_log)

    def test_reset_nao_envia_email_para_requisicoes_sem_permissao(self):
        url = f'/accounts/usuarios/{self.target.pk}/redefinir-senha/'
        self.client.logout()
        response = self.client.post(url, {'confirmar': 'sim'})
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.target)
        response = self.client.post(url, {'confirmar': 'sim'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(self.password))

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
        response = self.client.post(
            f'/accounts/usuarios/{superadmin.pk}/redefinir-senha/',
            {'confirmar': 'sim'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(mail.outbox), 0)
