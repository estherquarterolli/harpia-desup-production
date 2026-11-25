from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.professors.tests_e2e import ProfessorE2EBase
from .communication import get_desup_recipients
from .context_processors import notificacoes
from .models import AuditoriaGlobal, ConfiguracaoComunicacao, Notificacao, PreferenciaComunicacao, Unidade
from .services import create_window_ticket, record_window_attempt
from .tasks import send_notification_email_task


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    CELERY_TASK_ALWAYS_EAGER=True,
)
class ComunicacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unidade = Unidade.objects.create(nome='Unidade de teste', sigla='TESTE')
        cls.outra = Unidade.objects.create(nome='Unidade regular', sigla='REG')
        cls.desup = User.objects.create_user(email='desup@example.test', password='senha', perfil='DESUP', forcar_troca_senha=False)
        cls.outro_desup = User.objects.create_user(email='outro@example.test', password='senha', perfil='DESUP', forcar_troca_senha=False)
        cls.ti = User.objects.create_user(email='ti@example.test', password='senha', perfil='ADMIN', forcar_troca_senha=False)
        cls.superuser = User.objects.create_superuser(email='super@example.test', password='senha')
        cls.coord = User.objects.create_user(email='coord@example.test', password='senha', perfil='COORDENADOR_UNIDADE', unidade=cls.unidade, forcar_troca_senha=False)

    def config(self):
        return ConfiguracaoComunicacao.objects.get_or_create(pk=1)[0]

    def preferencia(self, usuario, receber=True):
        return PreferenciaComunicacao.objects.update_or_create(
            usuario=usuario, defaults={'receber_emails': receber},
        )[0]

    def admin_post(self, usuario=None, **data):
        return self.client.post(reverse('alloc_admin:core_configuracaocomunicacao_changelist'), {
            'acao': 'preferencia', 'usuario': (usuario or self.ti).pk, **data,
        })

    def aviso(self, **kwargs):
        return Notificacao.objects.create(titulo='Teste de aviso', mensagem='Solicitação registrada.', **kwargs)

    def test_padrao_envia_so_para_caixa_principal_sem_criar_configuracao(self):
        self.assertEqual(get_desup_recipients(), [settings.HARPIA_NOTIFICATION_EMAIL])
        self.assertFalse(ConfiguracaoComunicacao.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            aviso = self.aviso(url_acao='/core/unidades/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [settings.HARPIA_NOTIFICATION_EMAIL])
        self.assertIn(f'{settings.SITE_URL}/core/unidades/', mail.outbox[0].body)
        self.assertEqual(aviso._email_status, 'enfileirado')

    def test_apenas_perfis_elegiveis_ativos_inscritos_sem_duplicar_caixa_principal(self):
        duplicado = User.objects.create_user(email=settings.HARPIA_NOTIFICATION_EMAIL.upper(), password='senha', perfil='DESUP')
        for user in (self.desup, duplicado, self.coord, self.ti):
            self.preferencia(user)
        self.assertEqual(get_desup_recipients(), [settings.HARPIA_NOTIFICATION_EMAIL, self.desup.email, self.ti.email])
        User.objects.filter(pk=self.desup.pk).update(is_active=False)
        self.assertEqual(get_desup_recipients(), [settings.HARPIA_NOTIFICATION_EMAIL, self.ti.email])
        User.objects.filter(pk=self.desup.pk).update(is_active=True, perfil='COORDENADOR_UNIDADE')
        self.assertEqual(get_desup_recipients(), [settings.HARPIA_NOTIFICATION_EMAIL, self.ti.email])

    def test_silenciada_preserva_aviso_e_sino_sem_enfileirar(self):
        self.config().unidades_silenciadas.add(self.unidade)
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            aviso = self.aviso(unidade_origem=self.unidade)
        delay.assert_not_called()
        self.assertTrue(Notificacao.objects.filter(pk=aviso.pk).exists())
        request = RequestFactory().get('/')
        request.user = self.desup
        self.assertIn(aviso, notificacoes(request)['notificacoes_nao_lidas'])
        self.assertEqual(aviso._email_status, 'silenciado')

    def test_silenciamento_nao_afeta_outra_unidade_ou_evento_global(self):
        self.config().unidades_silenciadas.add(self.unidade)
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            outro = self.aviso(unidade_origem=self.outra)
            global_ = self.aviso()
        self.assertEqual([c.args[0] for c in delay.call_args_list], [outro.pk, global_.pk])

    def test_aviso_destinado_a_unidade_ou_usuario_nao_espelha_para_desup(self):
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            self.aviso(unidade_destino=self.unidade)
            self.aviso(destinatario=self.desup)
        delay.assert_not_called()

    def test_tarefa_confere_silenciamento_e_destinatarios_apos_enfileiramento(self):
        with patch('apps.core.tasks.send_notification_email_task.delay'), self.captureOnCommitCallbacks(execute=True):
            aviso = self.aviso(unidade_origem=self.unidade)
        config = self.config()
        config.unidades_silenciadas.add(self.unidade)
        self.assertEqual(send_notification_email_task.run(aviso.pk), 'silenciado')
        self.assertEqual(len(mail.outbox), 0)
        config.unidades_silenciadas.clear()
        self.preferencia(self.outro_desup)
        self.assertEqual(send_notification_email_task.run(aviso.pk), 'enviado')
        self.assertEqual(mail.outbox[0].to, [settings.HARPIA_NOTIFICATION_EMAIL, self.outro_desup.email])
        self.preferencia(self.outro_desup, receber=False)
        send_notification_email_task.run(aviso.pk)
        self.assertEqual(mail.outbox[1].to, [settings.HARPIA_NOTIFICATION_EMAIL])

    def test_rollback_nao_enfileira(self):
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError), transaction.atomic():
                self.aviso()
                raise ValueError('rollback')
        delay.assert_not_called()
        self.assertFalse(Notificacao.objects.exists())

    def test_editar_aviso_antigo_nao_reenvia(self):
        with self.captureOnCommitCallbacks():
            aviso = self.aviso()
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            aviso.mensagem = 'Atualizada'
            aviso.save()
        delay.assert_not_called()

    def test_falha_de_fila_preserva_notificacao(self):
        with patch('apps.core.tasks.send_notification_email_task.delay', side_effect=RuntimeError('indisponível')), self.captureOnCommitCallbacks(execute=True):
            aviso = self.aviso()
        self.assertEqual(aviso._email_status, 'falhou')
        self.assertTrue(Notificacao.objects.filter(pk=aviso.pk).exists())

    def test_tarefa_propaga_falha_ou_ausencia_de_confirmacao_para_retry(self):
        aviso = self.aviso()
        for resultado in (0, RuntimeError('SMTP indisponível')):
            with self.subTest(resultado=resultado):
                kwargs = {'side_effect': resultado} if isinstance(resultado, Exception) else {'return_value': resultado}
                with patch('apps.core.tasks.send_mail', **kwargs), self.assertRaises(RuntimeError):
                    # __wrapped__ executa o corpo sem o wrapper de autorretry do Celery.
                    send_notification_email_task._orig_run(aviso.pk)

    def test_senha_e_boas_vindas_nao_sao_silenciadas(self):
        from apps.accounts.services import enviar_email_senha_redefinida
        self.config().unidades_silenciadas.add(self.unidade)
        with self.captureOnCommitCallbacks(execute=True):
            novo = User.objects.create_user(email='novo@example.test', unidade=self.unidade)
        self.assertEqual(mail.outbox[0].to, [novo.email])
        self.assertTrue(enviar_email_senha_redefinida(novo))
        self.assertEqual(mail.outbox[1].to, [novo.email])

    def test_configuracoes_exigem_login_e_unidade_tem_apenas_senha(self):
        url = reverse('configuracoes')
        self.assertEqual(self.client.get(url).status_code, 302)
        for user in (self.desup, self.ti, self.superuser):
            self.client.force_login(user)
            self.assertContains(self.client.get(url), 'Salvar minhas preferências')
            self.assertRedirects(self.client.post(url, {'receber_emails': 'on'}), url)
        self.client.force_login(self.coord)
        response = self.client.get(url)
        self.assertContains(response, 'Alterar senha')
        self.assertNotContains(response, 'Salvar minhas preferências')
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_desup_so_edita_preferencia_propria_e_audita_antes_depois(self):
        self.preferencia(self.outro_desup)
        self.client.force_login(self.desup)
        url = reverse('configuracoes')
        self.client.post(url, {
            'usuario': self.outro_desup.pk, 'acao': 'global', 'receber_emails': 'on',
            'unidades_silenciadas': [self.unidade.pk], 'global-unidades_silenciadas': [self.outra.pk],
        })
        pessoal = PreferenciaComunicacao.objects.get(usuario=self.desup)
        self.assertTrue(pessoal.receber_emails)
        self.assertEqual(list(pessoal.unidades_silenciadas.all()), [self.unidade])
        self.assertFalse(PreferenciaComunicacao.objects.get(usuario=self.outro_desup).unidades_silenciadas.exists())
        self.assertFalse(ConfiguracaoComunicacao.objects.filter(unidades_silenciadas__isnull=False).exists())
        evento = AuditoriaGlobal.objects.get(acao='COMUNICACAO_PESSOAL_ALTERADA')
        self.assertEqual(evento.usuario, self.desup)
        self.assertEqual(evento.objeto, self.desup.email)
        self.assertEqual(evento.mudancas[0]['antes'], [])
        self.assertEqual(evento.mudancas[0]['depois'], [str(self.unidade)])
        self.client.post(url, {})
        self.assertEqual(get_desup_recipients(), [settings.HARPIA_NOTIFICATION_EMAIL, self.outro_desup.email])
        self.assertEqual(AuditoriaGlobal.objects.filter(acao='COMUNICACAO_PESSOAL_ALTERADA').count(), 2)

    def test_formulario_invalido_preserva_preferencia_e_selecoes(self):
        self.client.force_login(self.desup)
        self.preferencia(self.desup).unidades_silenciadas.add(self.unidade)
        response = self.client.post(reverse('configuracoes'), {'unidades_silenciadas': ['999999']})
        self.assertTrue(response.context['form'].errors)
        pessoal = PreferenciaComunicacao.objects.get(usuario=self.desup)
        self.assertTrue(pessoal.receber_emails)
        self.assertEqual(list(pessoal.unidades_silenciadas.all()), [self.unidade])

    def test_admin_renderiza_dentro_do_admin_e_configuracao_e_unica(self):
        self.client.force_login(self.ti)
        response = self.client.get(reverse('alloc_admin:core_configuracaocomunicacao_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/core/comunicacao.html')
        self.assertTemplateUsed(response, 'admin/base_site.html')
        self.assertContains(response, 'Silenciamento global de unidades')
        self.assertContains(response, self.ti.email)
        self.assertContains(response, self.desup.email)
        self.config()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConfiguracaoComunicacao.objects.create(pk=2)

    def test_admin_edita_a_si_mesmo_e_desup_mas_nao_outro_admin_ou_unidade(self):
        self.client.force_login(self.ti)
        for user in (self.ti, self.desup):
            response = self.admin_post(user, receber_emails='on', unidades_silenciadas=[self.unidade.pk])
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/admin/'))
            self.assertTrue(PreferenciaComunicacao.objects.get(usuario=user).receber_emails)
        for user in (self.superuser, self.coord):
            self.assertEqual(self.admin_post(user, receber_emails='on').status_code, 404)
        eventos = AuditoriaGlobal.objects.filter(acao='COMUNICACAO_PESSOAL_ALTERADA')
        self.assertEqual(set(eventos.values_list('objeto', flat=True)), {self.ti.email, self.desup.email})
        self.assertTrue(all(e.usuario_id == self.ti.pk for e in eventos))

    def test_desup_nao_altera_admin_nem_global_mesmo_com_acesso_staff(self):
        User.objects.filter(pk=self.desup.pk).update(is_staff=True)
        self.client.force_login(self.desup)
        url = reverse('alloc_admin:core_configuracaocomunicacao_changelist')
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.admin_post(acao='global', **{'global-unidades_silenciadas': [self.unidade.pk]})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConfiguracaoComunicacao.objects.exists())

    def test_silenciamento_pessoal_afeta_so_um_destinatario_e_unidade(self):
        pessoal = self.preferencia(self.desup)
        pessoal.unidades_silenciadas.add(self.unidade)
        self.preferencia(self.outro_desup)
        with self.captureOnCommitCallbacks(execute=True):
            self.aviso(unidade_origem=self.unidade)
            self.aviso(unidade_origem=self.outra)
        self.assertEqual(mail.outbox[0].to, [settings.HARPIA_NOTIFICATION_EMAIL, self.outro_desup.email])
        self.assertEqual(mail.outbox[1].to, [settings.HARPIA_NOTIFICATION_EMAIL, self.desup.email, self.outro_desup.email])

    def test_silenciamento_global_prevalece_e_desup_pode_reativar_preferencia_propria(self):
        self.client.force_login(self.ti)
        self.admin_post(self.desup)
        self.client.force_login(self.desup)
        self.client.post(reverse('configuracoes'), {'receber_emails': 'on'})
        self.assertIn(self.desup.email, get_desup_recipients(self.unidade.pk))
        self.client.force_login(self.ti)
        response = self.admin_post(acao='global', **{'global-unidades_silenciadas': [self.unidade.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_desup_recipients(self.unidade.pk), [])
        self.assertEqual(AuditoriaGlobal.objects.get(acao='COMUNICACAO_GLOBAL_ALTERADA').usuario, self.ti)
        self.client.force_login(self.desup)
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, 'Unidades silenciadas globalmente')
        self.client.post(reverse('configuracoes'), {'receber_emails': 'on', 'global-unidades_silenciadas': []})
        self.assertEqual(get_desup_recipients(self.unidade.pk), [])

    def test_preferencias_pessoais_sao_reavaliadas_apos_enfileiramento(self):
        pessoal = self.preferencia(self.desup)
        with patch('apps.core.tasks.send_notification_email_task.delay'), self.captureOnCommitCallbacks(execute=True):
            aviso = self.aviso(unidade_origem=self.unidade)
        pessoal.unidades_silenciadas.add(self.unidade)
        send_notification_email_task.run(aviso.pk)
        self.assertEqual(mail.outbox[0].to, [settings.HARPIA_NOTIFICATION_EMAIL])

    def test_menu_e_link_legado_apontam_para_destinos_corretos(self):
        self.client.force_login(self.desup)
        response = self.client.get(reverse('profile'))
        html = response.content.decode()
        menu = html.split('id="userMenu"', 1)[1].split('<hr', 1)[0]
        self.assertLess(menu.index('Meu Perfil'), menu.index('Configurações'))
        self.assertNotIn('Alterar senha', menu)
        self.assertNotContains(response, f'href="{reverse("core:comunicacao")}"')
        self.assertRedirects(self.client.get(reverse('core:comunicacao')), reverse('configuracoes'))
        self.assertEqual(self.client.post(reverse('core:comunicacao'), {}).status_code, 403)
        self.client.force_login(self.ti)
        self.assertRedirects(self.client.get(reverse('core:comunicacao')), reverse('alloc_admin:core_configuracaocomunicacao_changelist'))

    def test_chamado_e_tentativa_bloqueada_registram_origem_silenciada(self):
        self.config().unidades_silenciadas.add(self.unidade)
        request = RequestFactory().post('/')
        request.user = self.coord
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            create_window_ticket(request=request, area_label='Alocação', action_label='editar')
            record_window_attempt(request, area_label='Alocação', action_label='editar')
        delay.assert_not_called()
        self.assertEqual(Notificacao.objects.filter(unidade_origem=self.unidade).count(), 2)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OrigensComunicacaoTests(ProfessorE2EBase):
    def test_unidade_silenciada_preserva_pedidos_sem_enviar_email_em_todos_os_fluxos(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.allocations.views import _avisar_professor_de_outra_unidade
        from apps.extra_curricular.models import PendenciaExtra
        from .models import JanelaEntrega, SolicitacaoProfessorExterno
        from .services import solicitar_rat

        hoje = timezone.localdate()
        config = ConfiguracaoComunicacao.objects.create()
        PreferenciaComunicacao.objects.create(usuario=self.desup, receber_emails=True)
        config.unidades_silenciadas.add(self.unidade_a)
        JanelaEntrega.objects.create(
            semestre=self.semestre_atual, data_inicio=hoje, data_fim=hoje + timedelta(days=1),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        matriz = self._matriz_vigente(self.curso_ads, self.unidade_a)
        componente = self._componente(matriz, 'Carga regular', 'REG', carga_horaria=400, docente=self.prof_a1)
        pendencia = PendenciaExtra.objects.create(
            professor=self.prof_a1, unidade=self.unidade_a, semestre=self.semestre_atual,
        )
        request = RequestFactory().post('/')
        request.user = self.coord_a
        self.client.force_login(self.coord_a)
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay, self.captureOnCommitCallbacks(execute=True):
            cadastro = self.client.post(reverse('professors:professor_solicitar_cadastro'), {
                'nome': 'Docente novo', 'id_funcional': 'NOVO', 'tipo_contrato': self.contrato.pk,
            })
            cessao = self.client.post(reverse('professors:professor_solicitar_cessao'), {
                'professor': self.prof_b1.pk, 'justificativa': 'Solicitação de teste.',
            })
            extracurricular = self.client.post(reverse('extra_curricular:enviar_desup_lote'), {'ids': str(self.prof_a1.pk)})
            _avisar_professor_de_outra_unidade(request, componente, self.unidade_a, self.prof_b1)
            solicitar_rat(
                request=request, professor_id=self.prof_a1.pk, horas_adicionais=4,
                data_inicio=hoje, data_fim=None, justificativa='Solicitação de teste.',
            )
        for response in (cadastro, cessao, extracurricular):
            self.assertEqual(response.status_code, 302)
        self.assertEqual(SolicitacaoProfessorExterno.objects.filter(unidade_solicitante=self.unidade_a).count(), 2)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.assertEqual(Notificacao.objects.count(), 5)
        self.assertEqual(Notificacao.objects.filter(unidade_origem=self.unidade_a).count(), 5)
        delay.assert_not_called()
