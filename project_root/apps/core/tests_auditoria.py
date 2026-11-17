"""Log detalhado (quem, o quê, onde, quando), filtro "contém" do superadmin e
% de preenchimento na lista de unidades."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
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
        self.assertContains(resposta, 'Sem professores')
