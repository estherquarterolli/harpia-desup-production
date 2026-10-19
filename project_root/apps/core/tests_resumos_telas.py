"""Padrão resumo + filtro + dados nas telas Unidades, Solicitações externas, Professores e Matrizes."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Unidade
from apps.courses.models import Course, CourseUnit, CurriculumMatrix


class ResumosTelasTests(TestCase):
    def setUp(self):
        self.ua = Unidade.objects.create(nome='Unidade Alfa', sigla='UAL', status=True)
        self.ub = Unidade.objects.create(nome='Unidade Beta', sigla='UBE', status=False)
        curso = Course.objects.create(nome='Curso X', sigla='CX')
        CourseUnit.objects.create(curso=curso, unidade=self.ua, ativo=True)
        CourseUnit.objects.create(curso=curso, unidade=self.ub, ativo=False)
        self.matriz = CurriculumMatrix.objects.create(curso=curso, nome='M1', is_vigente=True, turno='M')
        self.matriz.unidades.add(self.ua)
        CurriculumMatrix.objects.create(curso=curso, nome='M2', is_vigente=False, is_rascunho=True)
        self.desup = User.objects.create_user(
            email='desup.resumo@harpia.test', password='pw', perfil='DESUP', forcar_troca_senha=False
        )
        self.coord = User.objects.create_user(
            email='coord.resumo@harpia.test', password='pw', perfil='COORDENADOR_UNIDADE',
            unidade=self.ua, forcar_troca_senha=False,
        )

    def _kpis(self, resposta):
        return {k['rotulo']: k['valor'] for k in resposta.context['kpis']}

    def test_unidades_resumo_busca_e_filtro_de_situacao(self):
        self.client.force_login(self.desup)
        url = reverse('core:unidade_list')

        resposta = self.client.get(url)
        self.assertEqual(self._kpis(resposta), {'Unidades': 2, 'Ativas': 1, 'Inativas': 1, 'Cursos ativos': 1})
        self.assertEqual(len(resposta.context['unidades']), 2)

        self.assertEqual([u.sigla for u in self.client.get(url, {'status': 'ativa'}).context['unidades']], ['UAL'])
        self.assertEqual([u.sigla for u in self.client.get(url, {'status': 'inativa'}).context['unidades']], ['UBE'])
        self.assertEqual([u.sigla for u in self.client.get(url, {'q': 'beta'}).context['unidades']], ['UBE'])
        por_cursos = {u.sigla: u.qtd_cursos for u in resposta.context['unidades']}
        self.assertEqual(por_cursos, {'UAL': 1, 'UBE': 0})

    def test_unidades_continua_restrita_a_desup(self):
        self.client.force_login(self.coord)
        self.assertEqual(self.client.get(reverse('core:unidade_list')).status_code, 403)

    def test_solicitacoes_externas_tem_resumo_e_tabela(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('core:solicitacao_professor_list'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self._kpis(resposta), {'Pendentes': 0, 'Aprovadas': 0, 'Recusadas': 0})
        self.assertContains(resposta, 'Nenhuma solicitação encontrada.')

    def test_professores_resumo_no_topo(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('professors:professor_list'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(self._kpis(resposta)), ['No sistema', 'Ativos', 'Afastados'])
        filtrada = self.client.get(reverse('professors:professor_list'), {'q': 'zzz'})
        self.assertIn('Encontrados', self._kpis(filtrada))

    def test_matrizes_resumo_respeita_o_escopo_do_perfil(self):
        self.client.force_login(self.desup)
        resposta = self.client.get(reverse('courses:matrix_list'))
        self.assertEqual(self._kpis(resposta), {'Matrizes': 2, 'Vigentes': 1, 'Rascunhos': 1, 'Histórico': 0})

        self.client.force_login(self.coord)
        resposta = self.client.get(reverse('courses:matrix_list'))
        # A unidade não vê rascunhos nem o cartão de rascunhos.
        self.assertEqual(self._kpis(resposta), {'Matrizes': 1, 'Vigentes': 1, 'Histórico': 0})

    def test_cabecalho_fixo_colado_no_topo(self):
        self.client.force_login(self.desup)
        html = self.client.get(reverse('core:unidade_list')).content.decode()
        self.assertIn('<main class="main-content flex-grow px-4 pb-4 pt-0', html)
        self.assertIn('id="topbar" class="sticky top-0', html)
