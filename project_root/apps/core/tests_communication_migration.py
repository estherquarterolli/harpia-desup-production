from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ComunicacaoMigrationTests(TransactionTestCase):
    def test_migracao_preserva_notificacoes_e_periodos_sem_enviar_email(self):
        if settings.MIGRATION_MODULES.get('core', '') is None or 'core' in settings.MIGRATION_MODULES:
            self.skipTest('Requer migrações reais (config.settings.development).')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [node for node in latest if node[0] != 'core'] + [('core', '0021_auditoria_mudancas_operacao')]
        executor.migrate(previous)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old_apps = executor.loader.project_state(previous).apps
        Notificacao = old_apps.get_model('core', 'Notificacao')
        Matriz = old_apps.get_model('courses', 'CurriculumMatrix')
        Componente = old_apps.get_model('courses', 'MatrixComponent')
        aviso = Notificacao.objects.create(titulo='Aviso antigo', mensagem='Preservar', lida=True)
        matriz = Matriz.objects.create(nome='Matriz antiga', turno='N')
        comp = Componente.objects.create(matriz=matriz, periodo='1o periodo', nome_temporario='Legada', carga_horaria=60)
        executor = MigrationExecutor(connection)
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay:
            executor.migrate(latest)
        delay.assert_not_called()
        new_apps = executor.loader.project_state(latest).apps
        self.assertEqual(new_apps.get_model('courses', 'MatrixComponent').objects.get(pk=comp.pk).periodo, '1o periodo')
        preservado = new_apps.get_model('core', 'Notificacao').objects.get(pk=aviso.pk)
        self.assertTrue(preservado.lida)
        self.assertEqual(preservado.mensagem, 'Preservar')
        self.assertIsNone(preservado.unidade_origem_id)
        self.assertFalse(new_apps.get_model('core', 'ConfiguracaoComunicacao').objects.exists())

    def test_preferencias_migram_selecao_antiga_e_preservam_silenciamento_global(self):
        if settings.MIGRATION_MODULES.get('core', '') is None or 'core' in settings.MIGRATION_MODULES:
            self.skipTest('Requer migrações reais (config.settings.development).')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        previous = [node for node in latest if node[0] != 'core'] + [('core', '0022_comunicacao_email')]
        executor.migrate(previous)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old_apps = executor.loader.project_state(previous).apps
        Usuario = old_apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
        Configuracao = old_apps.get_model('core', 'ConfiguracaoComunicacao')
        Unidade = old_apps.get_model('core', 'Unidade')
        usuarios = [Usuario.objects.create(
            email=f'legado-{i}@teste.com', username=f'legado-{i}', perfil='DESUP', is_active=(i != 1),
        ) for i in range(3)]
        unidade = Unidade.objects.create(nome='Unidade silenciada', sigla='SIL')
        config = Configuracao.objects.create()
        config.destinatarios_adicionais.add(*usuarios[:2])
        config.unidades_silenciadas.add(unidade)
        executor = MigrationExecutor(connection)
        with patch('apps.core.tasks.send_notification_email_task.delay') as delay:
            executor.migrate(latest)
        delay.assert_not_called()
        new_apps = executor.loader.project_state(latest).apps
        Preferencia = new_apps.get_model('core', 'PreferenciaComunicacao')
        ConfiguracaoNova = new_apps.get_model('core', 'ConfiguracaoComunicacao')
        self.assertEqual(set(Preferencia.objects.filter(receber_emails=True).values_list('usuario_id', flat=True)), {u.pk for u in usuarios[:2]})
        self.assertFalse(Preferencia.objects.filter(usuario_id=usuarios[2].pk).exists())
        self.assertFalse(Preferencia.objects.filter(unidades_silenciadas__isnull=False).exists())
        self.assertEqual(list(ConfiguracaoNova.objects.get().unidades_silenciadas.values_list('pk', flat=True)), [unidade.pk])
        MigrationExecutor(connection).migrate(previous)
        self.assertEqual(set(Configuracao.objects.get().destinatarios_adicionais.values_list('pk', flat=True)), {u.pk for u in usuarios[:2]})
        self.assertEqual(list(Configuracao.objects.get().unidades_silenciadas.values_list('pk', flat=True)), [unidade.pk])
