from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail, signing
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from .models import SolicitacaoSuporte, Unidade
from .support import SALT, ler_contexto, novo_contexto


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='harpia@example.test', HARPIA_SUPPORT_EMAIL='suporte@example.test',
)
class CentralAjudaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unidade = Unidade.objects.create(nome='Unidade Suporte', sigla='US')
        cls.outra = Unidade.objects.create(nome='Outra Unidade', sigla='OU')
        cls.coord = User.objects.create_user(
            email='coord@example.test', first_name='Pessoa', last_name='Unidade',
            unidade=cls.unidade, forcar_troca_senha=False,
        )
        cls.desup = User.objects.create_user(
            email='desup@example.test', perfil='DESUP', forcar_troca_senha=False,
        )
        cls.admin = User.objects.create_superuser(email='admin@example.test')

    def setUp(self):
        self.url = reverse('core:central_ajuda')
        self.faq_url = reverse('core:faq')
        self.client.force_login(self.coord)

    def dados(self, **kwargs):
        data = {
            'tipo': 'ERRO', 'assunto': 'Erro ao consultar',
            'descricao': 'A página não exibe o resultado esperado.',
            'contexto': novo_contexto(self.coord, 'Professores'),
        }
        data.update(kwargs)
        return data

    def test_abre_central_com_contexto_faq_e_tutorial(self):
        response = self.client.get(self.url, {'pagina': 'professors:professor_list'})
        self.assertContains(response, 'Perguntas frequentes')
        self.assertContains(response, self.coord.email)
        self.assertContains(response, self.unidade.nome)
        self.assertContains(response, 'data-ajuda-abrir')
        self.assertContains(response, 'Perguntas frequentes e suporte')
        self.assertContains(response, 'id="supportDock"')
        self.assertContains(response, 'ph-headset')
        self.assertContains(response, '<span>Suporte</span>')
        self.assertEqual(response.context['aba_ativa'], 'suporte')
        self.assertContains(response, 'data-support-form')
        self.assertNotContains(response, 'id="faq-titulo"')
        self.assertNotContains(response, 'ph-caret-right')
        self.assertNotContains(response, 'data-support-minimize')
        self.assertNotContains(response, 'data-support-restore')
        self.assertNotContains(response, 'class="support-open"')
        self.assertEqual(response.context['pagina_origem'], 'Professores')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(SolicitacaoSuporte.objects.count(), 0)

    def test_desup_pode_enviar_sem_unidade(self):
        self.client.force_login(self.desup)
        response = self.client.post(self.url, self.dados(contexto=novo_contexto(self.desup, 'Central de Ajuda')))
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(SolicitacaoSuporte.objects.get().unidade_id)
        self.assertIn('Sem unidade vinculada', mail.outbox[0].body)

    def test_admin_preserva_direcionamento_existente(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(self.url), '/admin/', fetch_redirect_response=False)
        self.assertRedirects(self.client.post(self.url, self.dados()), '/admin/', fetch_redirect_response=False)
        self.assertFalse(SolicitacaoSuporte.objects.exists())

    def test_anonimo_nao_abre_nem_envia(self):
        self.client.logout()
        for response in (self.client.get(self.url), self.client.post(self.url, self.dados())):
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse('login'), response.url)
        self.assertFalse(SolicitacaoSuporte.objects.exists())

    def test_perfil_nao_autorizado(self):
        User.objects.filter(pk=self.coord.pk).update(perfil='LEGADO')
        self.assertEqual(self.client.post(self.url, self.dados()).status_code, 403)

    def test_csrf_obrigatorio(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.coord)
        self.assertEqual(client.post(self.url, self.dados()).status_code, 403)
        response = client.get(self.url)
        data = self.dados(csrfmiddlewaretoken=client.cookies['csrftoken'].value)
        self.assertEqual(client.post(self.url, data).status_code, 302)

    def test_campos_invalidos_nao_enviam(self):
        for fields in (
            {'tipo': ''}, {'tipo': 'INEXISTENTE'}, {'assunto': '  '}, {'descricao': ''},
            {'assunto': 'a' * 151}, {'descricao': 'd' * 5001},
            {'assunto': 'Texto\r\nBcc: outro@example.test'},
        ):
            with self.subTest(fields=tuple(fields)):
                response = self.client.post(f'{self.url}?aba=faq', self.dados(**fields))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertEqual(response.context['aba_ativa'], 'suporte')
                self.assertContains(response, 'data-support-form')
        self.assertFalse(SolicitacaoSuporte.objects.exists())

    def test_contexto_adulterado_expirado_ou_de_outro_usuario(self):
        tokens = ['forjado', novo_contexto(self.desup, 'Professores')]
        expired = novo_contexto(self.coord, 'Professores')
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 7201):
            response = self.client.post(self.url, self.dados(contexto=expired))
        self.assertContains(response, 'O formulário expirou ou é inválido')
        for token in tokens:
            response = self.client.post(self.url, self.dados(contexto=token))
            self.assertContains(response, 'O formulário expirou ou é inválido')
        self.assertFalse(SolicitacaoSuporte.objects.exists())

    def test_envia_email_estruturado_e_ignora_identidades_do_browser(self):
        response = self.client.post(self.url, self.dados(
            usuario=self.desup.pk, unidade=self.outra.pk, email=self.desup.email,
            perfil='DESUP', pagina='https://externo.test/?token=segredo',
        ))
        recibo = SolicitacaoSuporte.objects.get()
        self.assertEqual(recibo.usuario_id, self.coord.pk)
        self.assertEqual(recibo.unidade_id, self.unidade.pk)
        self.assertEqual(recibo.status, SolicitacaoSuporte.Status.ENVIADO)
        self.assertIsNotNone(recibo.enviado_em)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['suporte@example.test'])
        self.assertEqual(message.reply_to, [self.coord.email])
        self.assertEqual(message.subject, '[HARPIA][SUPORTE][ERRO] Erro ao consultar')
        for text in (str(recibo.pk), 'Pessoa Unidade', self.unidade.nome, self.coord.email, 'Professores', 'Data e hora:'):
            self.assertIn(text, message.body)
        self.assertNotIn('segredo', message.body)
        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, 'E-mail aceito pelo serviço de envio.')
        self.unidade.refresh_from_db()
        self.assertEqual(self.unidade.nome, 'Unidade Suporte')

    def test_get_nao_coleta_url_referer_ou_filtros(self):
        response = self.client.get(self.url, {'pagina': '/accounts/redefinir-senha/TOKEN/?q=nome'}, HTTP_REFERER='https://externo.test/TOKEN')
        self.assertEqual(response.context['pagina_origem'], 'Central de Ajuda')
        token = response.context['form']['contexto'].value()
        self.assertNotIn('TOKEN', signing.loads(token, salt=SALT)['pagina'])

    def test_origem_em_formulario_usa_titulo_conhecido_sem_identificador(self):
        response = self.client.get(self.url, {'pagina': 'professors:professor_update'})
        self.assertEqual(response.context['pagina_origem'], 'Editar professor')

    def test_repeticao_de_post_nao_duplica_email_mesmo_em_outra_sessao(self):
        data = self.dados()
        first = self.client.post(self.url, data)
        second_client = Client()
        second_client.force_login(self.coord)
        second = second_client.post(self.url, data)
        self.assertEqual(first.url, second.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(SolicitacaoSuporte.objects.count(), 1)

    def test_cooldown_e_limite_horario_usam_registro_persistido(self):
        self.client.post(self.url, self.dados())
        response = self.client.post(self.url, self.dados())
        self.assertContains(response, 'Aguarde um minuto')
        SolicitacaoSuporte.objects.update(criado_em=timezone.now() - timedelta(minutes=5))
        for _ in range(4):
            SolicitacaoSuporte.objects.create(usuario=self.coord, criado_em=timezone.now() - timedelta(minutes=5))
        response = self.client.post(self.url, self.dados())
        self.assertContains(response, 'limite de cinco tentativas por hora')
        self.assertEqual(len(mail.outbox), 1)

    def test_falha_preserva_conteudo_registra_status_e_permite_nova_tentativa(self):
        data = self.dados()
        with patch('apps.core.support.EmailMessage.send', side_effect=SMTPException('detalhe-sigiloso')):
            with self.assertLogs('apps.core.support', level='ERROR') as logs:
                response = self.client.post(self.url, data)
        self.assertNotIn('detalhe-sigiloso', str(logs.output))
        self.assertContains(response, 'Não foi possível confirmar o envio')
        self.assertContains(response, data['descricao'])
        self.assertNotContains(response, 'E-mail aceito pelo serviço de envio.')
        recibo = SolicitacaoSuporte.objects.get()
        self.assertEqual(recibo.status, SolicitacaoSuporte.Status.FALHOU)
        new_token = response.context['form']['contexto'].value()
        self.assertNotEqual(new_token, data['contexto'])
        SolicitacaoSuporte.objects.update(criado_em=timezone.now() - timedelta(minutes=2))
        self.assertEqual(self.client.post(self.url, {**data, 'contexto': new_token}).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_retorno_zero_do_backend_nao_e_sucesso(self):
        with patch('apps.core.support.EmailMessage.send', return_value=0):
            response = self.client.post(self.url, self.dados())
        self.assertContains(response, 'Não foi possível confirmar o envio')
        self.assertEqual(SolicitacaoSuporte.objects.get().status, SolicitacaoSuporte.Status.FALHOU)

    def test_falha_ao_reservar_nao_envia_email_e_preserva_formulario(self):
        with patch('apps.core.support._reservar_envio', side_effect=DatabaseError):
            with patch('apps.core.support.EmailMessage.send') as send:
                response = self.client.post(self.url, self.dados())
        self.assertContains(response, 'Nenhum e-mail foi enviado')
        send.assert_not_called()

    def test_aceitacao_smtp_sem_confirmacao_no_banco_nao_libera_reenvio(self):
        data = self.dados()
        with patch('django.db.models.query.QuerySet.update', side_effect=DatabaseError):
            with patch('apps.core.support.EmailMessage.send', return_value=1) as send:
                response = self.client.post(self.url, data)
        send.assert_called_once()
        self.assertContains(response, 'Não reenvie')
        self.assertContains(response, str(SolicitacaoSuporte.objects.get().pk))
        self.assertEqual(SolicitacaoSuporte.objects.get().status, SolicitacaoSuporte.Status.ENVIANDO)
        self.assertEqual(response.context['form']['contexto'].value(), data['contexto'])

    def test_falha_smtp_e_falha_no_registro_preservam_reserva(self):
        data = self.dados()
        with patch('django.db.models.query.QuerySet.update', side_effect=DatabaseError):
            with patch('apps.core.support.EmailMessage.send', side_effect=SMTPException):
                response = self.client.post(self.url, data)
        self.assertContains(response, 'Confira com a equipe responsável')
        self.assertEqual(SolicitacaoSuporte.objects.get().status, SolicitacaoSuporte.Status.ENVIANDO)
        self.assertEqual(response.context['form']['contexto'].value(), data['contexto'])

    @override_settings(DEFAULT_FROM_EMAIL='Harpia <remetente@example.test>')
    def test_remetente_pode_ter_nome_de_exibicao(self):
        self.assertEqual(self.client.post(self.url, self.dados()).status_code, 302)
        self.assertEqual(mail.outbox[0].from_email, 'Harpia <remetente@example.test>')

    def test_reserva_em_andamento_nao_reenvia(self):
        data = self.dados()
        context = ler_contexto(data['contexto'], self.coord)
        SolicitacaoSuporte.objects.create(pk=context['id'], usuario=self.coord)
        with patch('apps.core.support.EmailMessage.send') as send:
            response = self.client.post(self.url, data)
        self.assertContains(response, 'em andamento ou sem confirmação')
        send.assert_not_called()

    def test_sem_destinatario_ou_backend_de_simulacao_nao_anuncia_envio(self):
        configs = [
            {'HARPIA_SUPPORT_EMAIL': '', 'DEFAULT_FROM_EMAIL': ''}, {'HARPIA_SUPPORT_EMAIL': 'invalido'},
            {'EMAIL_BACKEND': 'django.core.mail.backends.console.EmailBackend'},
            {'EMAIL_BACKEND': 'django.core.mail.backends.dummy.EmailBackend'},
            {'EMAIL_BACKEND': 'django.core.mail.backends.filebased.EmailBackend'},
        ]
        for config in configs:
            with self.subTest(config=config), override_settings(**config):
                response = self.client.get(self.url)
                self.assertContains(response, 'O envio está indisponível')
                if config.get('EMAIL_BACKEND'):
                    self.assertContains(response, 'modo de simulação de e-mail')
                else:
                    self.assertContains(response, 'não está configurado corretamente')
                self.assertContains(self.client.post(self.url, self.dados()), 'O envio de suporte está indisponível')
        self.assertFalse(SolicitacaoSuporte.objects.exists())

    @override_settings(HARPIA_SUPPORT_EMAIL='', DEFAULT_FROM_EMAIL='harpia@desup.faetec.rj.gov.br')
    def test_destino_reutiliza_caixa_institucional_existente(self):
        response = self.client.get(self.url)
        self.assertTrue(response.context['suporte_disponivel'])
        self.assertContains(response, 'harpia@desup.faetec.rj.gov.br')
        self.assertEqual(self.client.post(self.url, self.dados()).status_code, 302)
        self.assertEqual(mail.outbox[0].to, ['harpia@desup.faetec.rj.gov.br'])
        self.assertEqual(mail.outbox[0].from_email, 'harpia@desup.faetec.rj.gov.br')

    @override_settings(HARPIA_SUPPORT_EMAIL='', DEFAULT_FROM_EMAIL='Harpia <harpia@example.test>')
    def test_destino_padrao_extrai_apenas_endereco_do_remetente(self):
        self.client.post(self.url, self.dados())
        self.assertEqual(mail.outbox[0].to, ['harpia@example.test'])

    def test_confirmacao_nao_expoe_recibo_de_outro_usuario(self):
        recibo = SolicitacaoSuporte.objects.create(usuario=self.desup, status=SolicitacaoSuporte.Status.ENVIADO)
        response = self.client.get(self.url, {'enviado': str(recibo.pk)})
        self.assertIsNone(response.context['recibo'])
        self.assertNotContains(response, str(recibo.pk))
        self.assertEqual(self.client.get(self.url, {'enviado': 'invalido'}).status_code, 200)

    def test_html_e_texto_puro_no_email_e_escapado_na_validacao(self):
        data = self.dados(descricao='<script>alert("x")</script>')
        self.client.post(self.url, data)
        self.assertEqual(mail.outbox[0].content_subtype, 'plain')
        self.assertIn(data['descricao'], mail.outbox[0].body)
        response = self.client.post(self.url, self.dados(assunto='', descricao=data['descricao']))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert("x")</script>')

    def test_faq_adaptado_ao_perfil_e_fluxos_existentes(self):
        response = self.client.get(self.faq_url)
        self.assertContains(response, 'Nova justificativa')
        self.assertContains(response, 'Solicitar abertura')
        self.assertContains(response, 'redução de carga da unidade é definida pela DESUP')
        self.client.force_login(self.desup)
        response = self.client.get(self.faq_url)
        self.assertContains(response, 'gestão das janelas de entrega')
        self.assertNotContains(response, 'Use Nova justificativa')

    def test_aba_faq_separa_perguntas_e_oferece_suporte_ao_final(self):
        response = self.client.get(self.faq_url, {'pagina': 'professors:professor_list'})
        self.assertEqual(response.context['aba_ativa'], 'faq')
        self.assertContains(response, 'id="faq-titulo"')
        self.assertNotContains(response, 'data-support-form')
        html = response.content.decode()
        self.assertLess(html.index('</details>', html.index('id="faq-titulo"')), html.index('Como podemos ajudar?'))
        self.assertContains(response, '?pagina=professors%3Aprofessor_list#solicitar-suporte')

    def test_faq_no_menu_apos_ensino_com_item_ativo_por_perfil(self):
        for user in (self.coord, self.desup):
            self.client.force_login(user)
            response = self.client.get(self.faq_url)
            html = response.content.decode()
            menu = html[html.index('aria-label="Menu principal"'):html.index('</nav>')]
            self.assertLess(menu.index('Ensino e currículo'), menu.index('Perguntas frequentes'))
            self.assertIn(f'href="{self.faq_url}" class="sb-link is-active" aria-current="page"', menu)
            self.assertNotContains(response, 'aria-label="Seções da Central de Ajuda"')

    def test_faq_exige_autenticacao_e_nao_processa_formularios(self):
        self.assertEqual(self.client.post(self.faq_url, self.dados()).status_code, 405)
        self.assertFalse(SolicitacaoSuporte.objects.exists())
        self.client.logout()
        self.assertEqual(self.client.get(self.faq_url).status_code, 302)

    def test_link_antigo_de_faq_redireciona_para_pagina_no_menu(self):
        response = self.client.get(self.url, {'aba': 'faq', 'pagina': 'professors:professor_list'})
        self.assertRedirects(response, f'{self.faq_url}?pagina=professors%3Aprofessor_list')

    def test_visualizacao_admin_usa_unidade_e_perfil_da_sessao_sem_alterar_conta(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session['superadmin_modo_visualizacao'] = 'COORDENADOR_UNIDADE'
        session['superadmin_unidade_visualizacao'] = self.unidade.pk
        session.save()
        self.client.post(self.url, self.dados(contexto=novo_contexto(self.admin, 'Professores')))
        self.assertIn('visualização por administrador', mail.outbox[0].body)
        self.assertEqual(SolicitacaoSuporte.objects.get().unidade_id, self.unidade.pk)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.perfil, 'ADMIN')
        self.assertIsNone(self.admin.unidade_id)

    def test_contexto_nao_introduz_queries_de_suporte_durante_navegacao(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('profile'))
        self.assertContains(response, 'id="supportDock"')
        self.assertFalse(any('harpiadb_core_solicitacao_suporte' in query['sql'] for query in queries))
