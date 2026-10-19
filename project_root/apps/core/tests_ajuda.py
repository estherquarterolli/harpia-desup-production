"""Ajuda ("?") com tutorial nas páginas do menu da DESUP."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.ajuda import AJUDA_PAGINAS
from apps.core.models import Unidade


class AjudaPaginasDesupTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome='Unidade Ajuda', sigla='UAJ')
        self.desup = User.objects.create_user(
            email='desup.ajuda@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False
        )
        self.coord = User.objects.create_user(
            email='coord.ajuda@harpia.test', password='pw', perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade, forcar_troca_senha=False,
        )

    def test_toda_entrada_tem_rota_valida_e_conteudo_completo(self):
        for nome, conteudo in AJUDA_PAGINAS.items():
            with self.subTest(rota=nome):
                reverse(nome)
                self.assertTrue(conteudo['titulo'] and conteudo['resumo'])
                self.assertTrue(conteudo['funcionalidades'])
                self.assertGreaterEqual(len(conteudo['passos']), 3)
                for passo in conteudo['passos']:
                    self.assertTrue(passo['titulo'] and passo['texto'])
                    # Todo passo aponta para algo real da tela (nunca só texto solto).
                    self.assertTrue(passo['alvo'], passo['titulo'])

    def test_todas_as_abas_do_menu_da_desup_tem_ajuda(self):
        esperadas = {
            'dashboard_desup', 'core:unidade_list', 'desup_user_list', 'core:equipe_diretiva_desup',
            'core:solicitacao_professor_list', 'core:alertas_carga_desup', 'professors:professor_list',
            'alloc_curricular', 'extra_curricular:pendencia_list', 'courses:matrix_list',
            'courses:component_list', 'core:janela_list',
        }
        self.assertEqual(esperadas, set(AJUDA_PAGINAS))

    def test_desup_ve_botao_e_modal_em_cada_pagina(self):
        self.client.force_login(self.desup)
        for nome, conteudo in AJUDA_PAGINAS.items():
            with self.subTest(rota=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, 'data-ajuda-abrir')
                self.assertContains(resposta, 'id="tourRoot"')
                self.assertContains(resposta, 'Pular tutorial')
                dados = resposta.context['ajuda_pagina']
                self.assertEqual(dados['titulo'], conteudo['titulo'])
                self.assertEqual(len(dados['passos']), len(conteudo['passos']))
                self.assertContains(resposta, 'id="ajuda-dados"')

    def test_alertas_tem_um_unico_titulo_e_sem_texto_extra(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('core:alertas_carga_desup'))
        html = resposta.content.decode()

        # Um único <h1> com o nome da página (no cabeçalho fixo), sem repetição no corpo.
        import re
        self.assertEqual(len(re.findall(r'Alertas e Limites de Carga\s*</h1>', html)), 1)
        self.assertEqual(html.count('<h1'), 1)
        self.assertNotContains(resposta, 'Acompanhe a supervisão de carga horária')
        self.assertNotContains(resposta, 'O que significa')
        self.assertNotContains(resposta, 'Como é calculado')
        self.assertEqual(html.count('<button type="button" data-ajuda-abrir'), 1)

    def test_coordenador_nao_ve_a_ajuda(self):
        self.client.force_login(self.coord)
        resposta = self.client.get(reverse('dashboard_unidade'))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, 'data-ajuda-abrir')
        self.assertNotContains(resposta, 'id="tourRoot"')

    def test_cabecalho_fixo_traz_titulo_ajuda_notificacoes_e_conta(self):
        self.client.force_login(self.desup)
        html = self.client.get(reverse('core:unidade_list')).content.decode()
        topbar = html[html.index('id="topbar"'):html.index('</header>')]

        self.assertIn('sticky top-0', html[html.index('id="topbar"') - 80:html.index('id="topbar"') + 200])
        self.assertIn('<h1', topbar)
        self.assertIn('data-ajuda-abrir', topbar)
        self.assertIn('notificationMenu', topbar)
        self.assertIn('userMenu', topbar)

    def test_alvos_dos_passos_sao_seletores_ou_vazios(self):
        for nome, conteudo in AJUDA_PAGINAS.items():
            for passo in conteudo['passos']:
                with self.subTest(rota=nome, passo=passo['titulo']):
                    for chave in ('alvo', 'abrir', 'fechar'):
                        self.assertIsInstance(passo[chave], list)
                        for seletor in passo[chave]:
                            self.assertIsInstance(seletor, str)
                            self.assertNotIn('<', seletor)

    def test_passos_apontam_para_o_botao_da_acao_e_o_popup_fica_ao_lado(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('core:unidade_list'))
        alvos = {p['titulo']: p['alvo'] for p in resposta.context['ajuda_pagina']['passos']}

        self.assertEqual(alvos['Cadastre uma unidade'], ['a[href^="%s"]' % reverse('core:unidade_create')])
        self.assertEqual(alvos['Edite os dados'][0], '[data-tour="unidade-editar"]')
        # O script posiciona o popup à direita/esquerda do elemento antes de tentar embaixo/em cima.
        self.assertContains(resposta, 'r.right + 18 + cw <= vw - margem')

    def test_funcoes_em_popup_abrem_o_popup_real_durante_o_tutorial(self):
        """Passos cuja função vive em um popup abrem esse popup e o fecham ao sair do passo."""
        passos = {p['titulo']: p for p in AJUDA_PAGINAS['core:equipe_diretiva_desup']['passos']}
        for titulo in ('Abra um cargo', 'Preencha o cargo', 'Ajuste a redução', 'Cadastre e exclua cargos', 'Consulte o histórico'):
            with self.subTest(passo=titulo):
                self.assertTrue(passos[titulo]['abrir'])
                self.assertTrue(passos[titulo]['fechar'])
        alertas = {p['titulo']: p for p in AJUDA_PAGINAS['core:alertas_carga_desup']['passos']}
        self.assertTrue(alertas['Abra uma lista']['abrir'] and alertas['Abra uma lista']['fechar'])
        self.client.force_login(self.desup)
        html = self.client.get(reverse('core:equipe_diretiva_desup')).content.decode()
        self.assertIn('desfazerPasso', html)
        self.assertIn('abrirDoPasso', html)
