"""Log detalhado (quem, o quê, onde, quando), filtro "contém" do superadmin e
% de preenchimento na lista de unidades."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, CurricularComponent, CurriculumMatrix, MatrixComponent
from apps.professors.models import ContractType, Professor

from .models import AuditoriaGlobal, Unidade


class AuditoriaDetalhadaTests(TestCase):
    def setUp(self):
        self.desup = User.objects.create_user(
            email='desup.log@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False,
        )
        self.superadmin = User.objects.create_superuser(
            email='super.log@harpia.test', password='pw',
        )
        self.contrato = ContractType.objects.create(
            nome='PROF 40H', categoria=ContractType.CategoriaChoices.EFETIVO, regime_trabalho='40h',
            dias_presenca_obrigatorios=3, max_class_hours=20, max_total_hours=40, max_classes=8,
        )

    def test_cadastro_de_unidade_registra_quem_quando_e_o_que(self):
        self.client.force_login(self.desup)
        resposta = self.client.post(
            reverse('core:unidade_create'),
            {'nome': 'Unidade Nova', 'sigla': 'UNV', 'status': 'on'},
        )
        self.assertEqual(resposta.status_code, 302)

        log = AuditoriaGlobal.objects.get(acao='UNIDADE_CRIADO')
        self.assertEqual(log.email, 'desup.log@harpia.test')
        self.assertEqual(log.usuario, self.desup)
        self.assertEqual(log.categoria, AuditoriaGlobal.Categoria.CRIACAO)
        self.assertEqual(log.entidade, 'Unidade')
        self.assertIn('Unidade Nova', log.objeto)
        self.assertIn('Unidade Nova', log.detalhes)
        self.assertTrue(log.perfil_usuario)
        self.assertIsNotNone(log.criado_em)

    def test_alteracao_mostra_valor_de_antes_e_de_depois(self):
        unidade = Unidade.objects.create(nome='Unidade Alfa', sigla='UAL', status=True)
        self.client.force_login(self.desup)
        self.client.post(
            reverse('core:unidade_update', args=[unidade.pk]),
            {'nome': 'Unidade Alfa', 'sigla': 'UAX', 'status': 'on'},
        )

        log = AuditoriaGlobal.objects.get(acao='UNIDADE_ALTERADO')
        self.assertEqual(log.categoria, AuditoriaGlobal.Categoria.ALTERACAO)
        self.assertIn('UAL → UAX', log.detalhes)
        self.assertEqual(log.objeto_id, str(unidade.pk))

    def test_professor_criado_na_requisicao_guarda_nome_e_unidade(self):
        """Sinais de modelo gravam nome do professor e unidade quando há requisição ativa."""
        from apps.core import audit

        unidade = Unidade.objects.create(nome='Unidade Beta', sigla='UBE')
        self.client.force_login(self.desup)
        requisicao = self.client.get(reverse('core:unidade_list')).wsgi_request

        audit._local.request = requisicao
        try:
            professor = Professor.objects.create(
                id_funcional='ID-777', rh_nome='Maria da Silva', unidade_principal=unidade,
                tipo_contrato=self.contrato,
            )
            professor.unidades.add(unidade)
        finally:
            audit._local.request = None

        log = AuditoriaGlobal.objects.get(acao='PROFESSOR_CRIADO')
        self.assertIn('MARIA DA SILVA', log.objeto)
        self.assertIn('ID-777', log.objeto)
        self.assertIn('Unidade Beta', log.unidade_objeto)
        self.assertIn('Unidade Beta', log.detalhes)

    def test_sem_requisicao_nao_gera_linha(self):
        Unidade.objects.create(nome='Sem Requisicao', sigla='SRQ')
        self.assertFalse(AuditoriaGlobal.objects.filter(acao='UNIDADE_CRIADO').exists())

    def test_filtro_contem_do_superadmin_acha_trecho_no_meio_do_texto(self):
        AuditoriaGlobal.objects.create(
            email='a@x.test', acao='PROFESSOR_CRIADO', categoria='CRIACAO',
            objeto='JOÃO PEDRO (ID funcional 1)', detalhes='Professor cadastrado: JOÃO PEDRO.',
        )
        AuditoriaGlobal.objects.create(
            email='b@x.test', acao='UNIDADE_CRIADO', categoria='CRIACAO',
            objeto='Unidade Zeta', detalhes='Unidade cadastrada: Unidade Zeta.',
        )
        self.client.force_login(self.superadmin)
        url = reverse('alloc_admin:core_auditoriaglobal_changelist')

        por_detalhes = self.client.get(url, {'detalhes_contem': 'pedro'})
        self.assertEqual(por_detalhes.status_code, 200)
        self.assertEqual([l.email for l in por_detalhes.context['cl'].result_list], ['a@x.test'])

        por_registro = self.client.get(url, {'registro_contem': 'zeta'})
        self.assertEqual([l.email for l in por_registro.context['cl'].result_list], ['b@x.test'])

        por_busca = self.client.get(url, {'q': 'cadastrado pedro'})
        self.assertEqual([l.email for l in por_busca.context['cl'].result_list], ['a@x.test'])


class PreenchimentoUnidadesTests(TestCase):
    def setUp(self):
        self.desup = User.objects.create_user(
            email='desup.pct@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False,
        )
        self.com_professor = Unidade.objects.create(nome='Unidade Com Professor', sigla='UCP')
        self.vazia = Unidade.objects.create(nome='Unidade Vazia', sigla='UVZ')
        contrato = ContractType.objects.create(
            nome='PROF 40H', categoria=ContractType.CategoriaChoices.EFETIVO, regime_trabalho='40h',
            dias_presenca_obrigatorios=3, max_class_hours=20, max_total_hours=40, max_classes=8,
        )
        professor = Professor.objects.create(
            id_funcional='PCT-1', rh_nome='Professor Pct', unidade_principal=self.com_professor,
            tipo_contrato=contrato,
        )
        professor.unidades.add(self.com_professor)

    def test_lista_de_unidades_traz_percentual_de_preenchimento(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('core:unidade_list'))
        self.assertEqual(resposta.status_code, 200)

        por_sigla = {u.sigla: u.preenchimento for u in resposta.context['unidades']}
        self.assertEqual(por_sigla['UCP']['professores'], 1)
        self.assertEqual(por_sigla['UCP']['horas_meta'], 20.0)
        self.assertEqual(por_sigla['UCP']['percentual'], 0.0)
        self.assertIsNone(por_sigla['UVZ']['percentual'])
        self.assertContains(resposta, 'Preenchimento')
        self.assertContains(resposta, 'Carga preenchida')
        self.assertContains(resposta, 'Prof. completos')
        self.assertContains(resposta, '0/1')
        self.assertContains(resposta, 'Sem professores')


class AuditoriaEstruturadaTests(TestCase):
    """Antes/depois por campo, código da operação, inferência do registro e painéis do admin."""

    def setUp(self):
        self.desup = User.objects.create_user(
            email='desup.est@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False,
        )
        self.superadmin = User.objects.create_superuser(
            email='super.est@harpia.test', password='pw',
        )

    def test_alteracao_guarda_antes_e_depois_por_campo(self):
        unidade = Unidade.objects.create(nome='Unidade Alfa', sigla='UAL', status=True)
        self.client.force_login(self.desup)
        self.client.post(
            reverse('core:unidade_update', args=[unidade.pk]),
            {'nome': 'Unidade Alfa', 'sigla': 'UAX', 'status': 'on'},
        )

        log = AuditoriaGlobal.objects.get(acao='UNIDADE_ALTERADO')
        self.assertTrue(
            any(c['antes'] == 'UAL' and c['depois'] == 'UAX' for c in log.mudancas),
            log.mudancas,
        )

    def test_linhas_da_mesma_requisicao_compartilham_operacao_e_guardam_a_tela(self):
        self.client.force_login(self.desup)
        self.client.post(
            reverse('core:unidade_create'),
            {'nome': 'Unidade Op', 'sigla': 'UOP', 'status': 'on'},
        )
        log = AuditoriaGlobal.objects.get(acao='UNIDADE_CRIADO')
        self.assertEqual(len(log.operacao), 32)
        self.assertTrue(log.caminho.startswith('POST '))
        self.assertTrue(any(c['campo'] == 'Sigla' and c['depois'] == 'UOP' for c in log.mudancas))

    def test_evento_explicito_deduz_o_tipo_pelo_codigo_da_acao(self):
        from apps.core.audit import registrar, titulo_da_acao

        linha = registrar(None, 'MATRIZ_VIGENTE_EDITADA', 'Matriz editada.')
        self.assertEqual(linha.entidade, 'Matriz curricular')
        self.assertEqual(titulo_da_acao('MATRIZ_VIGENTE_EDITADA'), 'Matriz vigente editada')
        self.assertEqual(titulo_da_acao('PROFESSOR_ALTERADO'), 'Professor alterado')
        self.assertEqual(titulo_da_acao('LOGIN_FALHOU'), 'Tentativa de acesso recusada')
        self.assertEqual(titulo_da_acao('ALGO_NOVO_QUALQUER'), 'Algo novo qualquer')

    def test_evento_explicito_herda_o_registro_gravado_na_mesma_requisicao(self):
        from apps.core import audit

        self.client.force_login(self.desup)
        requisicao = self.client.get(reverse('core:unidade_list')).wsgi_request
        audit._local.request = requisicao
        try:
            Unidade.objects.create(nome='Unidade Herdada', sigla='UHE')
            evento = audit.registrar(requisicao, 'EXTRACURRICULAR_EXCLUIDO', 'Item excluído.')
        finally:
            audit._local.request = None

        filha = AuditoriaGlobal.objects.get(acao='UNIDADE_CRIADO')
        self.assertIn('Unidade Herdada', evento.objeto)
        self.assertEqual(evento.operacao, filha.operacao)
        self.assertTrue(evento.operacao)

    def test_reset_de_senha_pela_desup_registra_o_usuario_afetado(self):
        alvo = User.objects.create_user(
            email='alvo.senha@harpia.test', password='pw', perfil='COORDENADOR_UNIDADE',
            forcar_troca_senha=False,
        )
        self.client.force_login(self.desup)
        self.client.post(reverse('desup_user_password_reset', args=[alvo.pk]), {'confirmar': 'sim'})

        log = AuditoriaGlobal.objects.get(acao='DESUP_PASSWORD_FORCE_RESET')
        self.assertEqual(log.email, 'desup.est@harpia.test')
        self.assertEqual(log.objeto, 'alvo.senha@harpia.test')
        self.assertEqual(log.entidade, 'Senha de usuário')

    def test_detalhe_mostra_tabela_de_antes_e_depois(self):
        log = AuditoriaGlobal.objects.create(
            email='a@x.test', acao='UNIDADE_ALTERADO', categoria='ALTERACAO', entidade='Unidade',
            objeto='Unidade Alfa', detalhes='Unidade alterada: Unidade Alfa.',
            mudancas=[{'campo': 'Sigla', 'antes': 'UAL', 'depois': 'UAX'}],
        )
        self.client.force_login(self.superadmin)
        resposta = self.client.get(reverse('alloc_admin:core_auditoriaglobal_change', args=[log.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Unidade alterada')
        self.assertContains(resposta, '<th>Antes</th>')
        self.assertContains(resposta, 'UAL')
        self.assertContains(resposta, 'UAX')

    def test_detalhe_de_registro_antigo_le_antes_e_depois_do_texto(self):
        log = AuditoriaGlobal.objects.create(
            email='a@x.test', acao='UNIDADE_ALTERADO', categoria='ALTERACAO',
            detalhes='Unidade alterada: X. Alterações: Sigla: AAA → BBB.',
        )
        self.client.force_login(self.superadmin)
        resposta = self.client.get(reverse('alloc_admin:core_auditoriaglobal_change', args=[log.pk]))
        self.assertContains(resposta, 'AAA')
        self.assertContains(resposta, 'BBB')

    def test_detalhe_lista_os_outros_registros_da_mesma_operacao(self):
        codigo = 'a' * 32
        principal = AuditoriaGlobal.objects.create(
            email='a@x.test', acao='MATRIZ_VIGENTE_EDITADA', categoria='ALTERACAO', operacao=codigo,
        )
        AuditoriaGlobal.objects.create(
            email='a@x.test', acao='COMPONENTE_MATRIZ_ALTERADO', categoria='ALTERACAO',
            entidade='Componente da matriz', objeto='Cálculo I', operacao=codigo,
        )
        self.client.force_login(self.superadmin)
        resposta = self.client.get(
            reverse('alloc_admin:core_auditoriaglobal_change', args=[principal.pk]),
        )
        self.assertContains(resposta, 'Componente da matriz alterado')
        self.assertContains(resposta, 'Cálculo I')

    def test_lista_mostra_nome_legivel_da_acao(self):
        AuditoriaGlobal.objects.create(
            email='a@x.test', acao='PROFESSOR_CRIADO', categoria='CRIACAO',
            entidade='Professor', objeto='JOÃO PEDRO', detalhes='Professor cadastrado: JOÃO PEDRO.',
        )
        self.client.force_login(self.superadmin)
        resposta = self.client.get(reverse('alloc_admin:core_auditoriaglobal_changelist'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Professor cadastrado')
        self.assertContains(resposta, 'JOÃO PEDRO')

    def test_painel_inicial_mostra_nome_atividade_e_carrega_o_css_proprio(self):
        AuditoriaGlobal.objects.create(
            email='a@x.test', acao='UNIDADE_CRIADO', categoria='CRIACAO', objeto='Unidade Zeta',
        )
        self.client.force_login(self.superadmin)
        resposta = self.client.get(reverse('alloc_admin:index'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Olá, super.est@harpia.test')
        self.assertContains(resposta, 'sa-hero')
        self.assertContains(resposta, 'Atividade recente')
        self.assertContains(resposta, 'Unidade cadastrada')
        self.assertContains(resposta, 'css/superadmin.css')


class SuperadminExperienciaTests(TestCase):
    """Painel "Precisa de atenção", filtros de acesso, ativar/desativar, CSV e erros legíveis."""

    def setUp(self):
        self.superadmin = User.objects.create_superuser(
            email='super.exp@harpia.test', password='pw',
        )
        self.client.force_login(self.superadmin)

    def _lista_de_usuarios(self, consulta=''):
        return self.client.get(reverse('alloc_admin:accounts_user_changelist') + consulta)

    def test_home_lista_pendencias_com_link_para_a_lista_filtrada(self):
        Unidade.objects.create(nome='Unidade Sem Ninguém', sigla='USN', status=True)
        resposta = self.client.get(reverse('alloc_admin:index'))
        self.assertContains(resposta, 'Precisa de atenção')
        self.assertContains(resposta, 'Unidades sem usuário')
        self.assertContains(resposta, 'acesso=sem_usuario')

    def test_home_esconde_o_painel_de_atencao_quando_nao_ha_pendencias(self):
        self.superadmin.last_login = timezone.now()
        self.superadmin.forcar_troca_senha = False
        self.superadmin.save(update_fields=['last_login', 'forcar_troca_senha'])
        resposta = self.client.get(reverse('alloc_admin:index'))
        self.assertNotContains(resposta, 'Precisa de atenção')

    def test_filtro_de_unidades_sem_usuario_mostra_so_as_sem_usuario(self):
        Unidade.objects.create(nome='Unidade Vazia', sigla='UVZ', status=True)
        com_gente = Unidade.objects.create(nome='Unidade Ocupada', sigla='UOC', status=True)
        User.objects.create_user(
            email='coord.ocupada@harpia.test', password='pw', unidade=com_gente,
        )
        resposta = self.client.get(reverse('alloc_admin:core_unidade_changelist') + '?acesso=sem_usuario')
        self.assertContains(resposta, 'Unidade Vazia')
        self.assertNotContains(resposta, 'Unidade Ocupada')

    def test_filtro_de_situacao_separa_quem_nunca_acessou(self):
        User.objects.create_user(email='nunca@harpia.test', password='pw')
        antigo = User.objects.create_user(email='ja.entrou@harpia.test', password='pw')
        antigo.last_login = timezone.now()
        antigo.save(update_fields=['last_login'])
        resposta = self._lista_de_usuarios('?situacao=nunca_acessou')
        self.assertContains(resposta, 'nunca@harpia.test')
        self.assertNotContains(resposta, 'ja.entrou@harpia.test')

    def test_lista_de_usuarios_mostra_selos_de_situacao(self):
        User.objects.create_user(email='temp@harpia.test', password='pw')
        resposta = self._lista_de_usuarios()
        self.assertContains(resposta, 'Nunca acessou')
        self.assertContains(resposta, 'Senha temporária')

    def test_desativar_usuarios_pela_lista_audita_e_protege_a_propria_conta(self):
        alvo = User.objects.create_user(email='sair@harpia.test', password='pw')
        antes = AuditoriaGlobal.objects.count()
        self.client.post(
            reverse('alloc_admin:accounts_user_changelist'),
            {
                'action': 'desativar_usuarios',
                '_selected_action': [alvo.pk, self.superadmin.pk],
                'index': '0',
            },
            follow=True,
        )
        alvo.refresh_from_db()
        self.superadmin.refresh_from_db()
        self.assertFalse(alvo.is_active)
        self.assertTrue(self.superadmin.is_active)
        self.assertGreater(AuditoriaGlobal.objects.count(), antes)
        evento = AuditoriaGlobal.objects.get(acao='USUARIO_DESATIVADO')
        self.assertEqual(evento.email, 'super.exp@harpia.test')
        self.assertIn('sair@harpia.test', evento.objeto)

    def test_ativar_usuarios_reativa_a_conta(self):
        alvo = User.objects.create_user(email='volta@harpia.test', password='pw', is_active=False)
        self.client.post(
            reverse('alloc_admin:accounts_user_changelist'),
            {'action': 'ativar_usuarios', '_selected_action': [alvo.pk], 'index': '0'},
            follow=True,
        )
        alvo.refresh_from_db()
        self.assertTrue(alvo.is_active)

    def test_pagina_do_usuario_mostra_atividade_recente_com_link_para_a_auditoria(self):
        alvo = User.objects.create_user(email='ativo@harpia.test', password='pw')
        AuditoriaGlobal.objects.create(
            email='ativo@harpia.test', acao='UNIDADE_CRIADO', categoria='CRIACAO', objeto='Unidade Beta',
        )
        resposta = self.client.get(reverse('alloc_admin:accounts_user_change', args=[alvo.pk]))
        self.assertContains(resposta, 'Atividade recente')
        self.assertContains(resposta, 'Unidade cadastrada')
        self.assertContains(resposta, 'quem_contem=ativo@harpia.test')

    def test_exportar_auditoria_em_csv_traz_antes_depois_e_neutraliza_formulas(self):
        linha = AuditoriaGlobal.objects.create(
            email='quem@harpia.test', acao='PROFESSOR_ALTERADO', categoria='ALTERACAO',
            objeto='=CMD()', entidade='Professor',
            mudancas=[{'campo': 'Carga horária', 'antes': '20', 'depois': '40'}],
        )
        resposta = self.client.post(
            reverse('alloc_admin:core_auditoriaglobal_changelist'),
            {'action': 'exportar_csv', '_selected_action': [linha.pk], 'index': '0'},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('text/csv', resposta['Content-Type'])
        conteudo = resposta.content.decode('utf-8')
        self.assertIn('Carga horária: 20 → 40', conteudo)
        self.assertIn("'=CMD()", conteudo)
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='AUDITORIA_EXPORTADA').exists())

    def test_lista_de_erros_mostra_gravidade_e_mensagem_curta(self):
        from .models import ErroSistema

        ErroSistema.objects.create(
            metodo='POST', caminho='/matrizes/salvar/', status_http=500, tipo_erro='ValueError',
            mensagem='valor inválido na carga horária', request_id='abc123', fingerprint='f' * 16,
        )
        resposta = self.client.get(reverse('alloc_admin:core_errosistema_changelist'))
        self.assertContains(resposta, 'Erro do sistema')
        self.assertContains(resposta, 'valor inválido na carga horária')
        self.assertContains(resposta, '/matrizes/salvar/')

    def test_filtro_de_periodo_dos_erros_esconde_os_antigos(self):
        from datetime import timedelta

        from .models import ErroSistema

        novo = ErroSistema.objects.create(
            metodo='GET', caminho='/novo/', status_http=500, tipo_erro='ErroNovo',
            request_id='n1', fingerprint='n' * 16,
        )
        velho = ErroSistema.objects.create(
            metodo='GET', caminho='/velho/', status_http=500, tipo_erro='ErroVelho',
            request_id='v1', fingerprint='v' * 16,
        )
        ErroSistema.objects.filter(pk=velho.pk).update(criado_em=timezone.now() - timedelta(days=3))
        resposta = self.client.get(reverse('alloc_admin:core_errosistema_changelist') + '?periodo=24h')
        self.assertContains(resposta, 'ErroNovo')
        self.assertNotContains(resposta, 'ErroVelho')
        self.assertTrue(novo.pk)


class MatrizVigenteAuditoriaTests(TestCase):
    """"Matriz vigente editada" precisa dizer o que mudou, inclusive componentes novos e removidos."""

    def setUp(self):
        self.desup = User.objects.create_user(
            email='desup.mat@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False,
        )
        self.unidade = Unidade.objects.create(nome='Unidade Teste', sigla='UT')
        self.curso = Course.objects.create(nome='Curso Teste', sigla='PW')
        self.algoritmos = CurricularComponent.objects.create(
            nome='Algoritmos', codigo='AL1', carga_horaria_padrao=80, creditos=4,
        )
        self.banco = CurricularComponent.objects.create(
            nome='Banco de Dados', codigo='BD1', carga_horaria_padrao=60, creditos=3,
        )
        self.matriz = CurriculumMatrix.objects.create(
            curso=self.curso, nome='GAIO', is_vigente=True, is_rascunho=False, turno='M',
        )
        self.matriz.unidades.add(self.unidade)
        self.componente = MatrixComponent.objects.create(
            matriz=self.matriz, componente_curricular=self.algoritmos, periodo='1º Semestre',
            carga_horaria=80, creditos=4, carga_horaria_semanal=4,
            status=MatrixComponent.StatusChoices.SEM_PROFESSOR,
        )

    def _editar(self, carga_horaria='100', adicionar_banco=True):
        dados = {
            'curso': self.curso.id, 'unidades': [self.unidade.id], 'nome': 'GAIO', 'turno': 'M',
            'acao': 'salvar_vigente',
            'componentes-TOTAL_FORMS': '2' if adicionar_banco else '1',
            'componentes-INITIAL_FORMS': '1',
            'componentes-MIN_NUM_FORMS': '1',
            'componentes-MAX_NUM_FORMS': '1000',
            'componentes-0-id': self.componente.pk,
            'componentes-0-matriz': self.matriz.pk,
            'componentes-0-componente_curricular': self.algoritmos.id,
            'componentes-0-codigo': 'AL1',
            'componentes-0-periodo': '1º Semestre',
            'componentes-0-carga_horaria': carga_horaria,
            'componentes-0-creditos': '4',
            'componentes-0-carga_horaria_semanal': '4',
            'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
        }
        if adicionar_banco:
            dados.update({
                'componentes-1-componente_curricular': self.banco.id,
                'componentes-1-periodo': '2º Semestre',
                'componentes-1-carga_horaria': '60',
                'componentes-1-creditos': '3',
                'componentes-1-carga_horaria_semanal': '3',
                'componentes-1-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            })
        self.client.force_login(self.desup)
        return self.client.post(
            reverse('courses:matrix_update', kwargs={'pk': self.matriz.pk}), dados,
        )

    def test_evento_lista_campo_alterado_e_componente_novo(self):
        resposta = self._editar()
        self.assertEqual(resposta.status_code, 302)

        evento = AuditoriaGlobal.objects.get(acao='MATRIZ_VIGENTE_EDITADA')
        self.assertEqual(evento.entidade, 'Matriz curricular')
        self.assertIn('GAIO', evento.objeto)
        campos = evento.mudancas
        self.assertTrue(any(
            'arga' in c['campo'] and c['antes'] == '80' and c['depois'] == '100' for c in campos
        ), campos)
        self.assertTrue(any(
            'Banco de Dados' in c['campo'] or 'Banco de Dados' in c['depois'] for c in campos
        ), campos)

    def test_componentes_nao_geram_linhas_soltas_quando_a_matriz_vigente_e_editada(self):
        self._editar()
        self.assertFalse(AuditoriaGlobal.objects.filter(acao__startswith='COMPONENTE_MATRIZ').exists())

    def test_componente_removido_aparece_no_evento(self):
        dados_ok = self._editar(carga_horaria='80', adicionar_banco=False)
        self.assertEqual(dados_ok.status_code, 302)
        AuditoriaGlobal.objects.all().delete()
        self.client.post(
            reverse('courses:matrix_update', kwargs={'pk': self.matriz.pk}),
            {
                'curso': self.curso.id, 'unidades': [self.unidade.id], 'nome': 'GAIO', 'turno': 'M',
                'acao': 'salvar_vigente',
                'componentes-TOTAL_FORMS': '2', 'componentes-INITIAL_FORMS': '1',
                'componentes-MIN_NUM_FORMS': '1', 'componentes-MAX_NUM_FORMS': '1000',
                'componentes-0-id': self.componente.pk, 'componentes-0-matriz': self.matriz.pk,
                'componentes-0-DELETE': 'on',
                'componentes-1-componente_curricular': self.banco.id,
                'componentes-1-periodo': '1º Semestre', 'componentes-1-carga_horaria': '60',
                'componentes-1-creditos': '3', 'componentes-1-carga_horaria_semanal': '3',
                'componentes-1-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            },
        )
        evento = AuditoriaGlobal.objects.get(acao='MATRIZ_VIGENTE_EDITADA')
        self.assertTrue(any(
            'Algoritmos' in c['campo'] and c['depois'] == '—' for c in evento.mudancas
        ), evento.mudancas)
