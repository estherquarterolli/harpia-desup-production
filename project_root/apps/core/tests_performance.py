from pathlib import Path
import json

from unittest.mock import patch

from django.db import connection
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.admin import CustomUserAdmin, HarpiaModelAdmin
from apps.accounts.views import DesupUserListView
from apps.core.views import CursoListView, JanelaEntregaListView, UnidadeListView
from apps.courses.views import CurricularComponentListView, CurriculumMatrixListView
from apps.professors.views import ALLOCATION_TABLE_PAGE_SIZE, ProfessorListView


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class LightweightListConfigurationTests(SimpleTestCase):
    """Impede que as telas pesadas voltem a carregar a base inteira."""

    def test_listas_operacionais_usam_lotes_pequenos(self):
        self.assertEqual(ProfessorListView.paginate_by, 20)
        self.assertEqual(DesupUserListView.paginate_by, 20)
        self.assertEqual(CurricularComponentListView.paginate_by, 25)
        self.assertEqual(CurriculumMatrixListView.paginate_by, 12)
        self.assertEqual(UnidadeListView.paginate_by, 18)
        self.assertEqual(CursoListView.paginate_by, 20)
        self.assertEqual(JanelaEntregaListView.paginate_by, 20)
        self.assertEqual(ALLOCATION_TABLE_PAGE_SIZE, 20)

    def test_superadmin_tambem_limita_resultados(self):
        self.assertEqual(HarpiaModelAdmin.list_per_page, 25)
        self.assertFalse(HarpiaModelAdmin.show_full_result_count)
        self.assertEqual(CustomUserAdmin.list_per_page, 25)
        self.assertFalse(CustomUserAdmin.show_full_result_count)


class FrontendAssetPerformanceTests(SimpleTestCase):
    def test_tailwind_e_compilado_e_nao_mais_executado_no_navegador(self):
        css = PROJECT_ROOT / 'static' / 'css' / 'tailwind.min.css'
        self.assertTrue(css.exists())
        self.assertLess(css.stat().st_size, 150_000)

        templates = PROJECT_ROOT / 'templates'
        for template in templates.rglob('*.html'):
            with self.subTest(template=template.relative_to(templates)):
                self.assertNotIn(
                    'cdn.tailwindcss.com',
                    template.read_text(encoding='utf-8-sig'),
                )


class BulkProfessorPerformanceTests(TestCase):
    """Mede consultas e candidatos processados numa base sintética de 5.000."""

    @classmethod
    def setUpTestData(cls):
        from apps.accounts.models import User
        from apps.core.models import Unidade
        from apps.professors.models import ContractType, Professor

        cls.unidade = Unidade.objects.create(nome='Unidade pequena', sigla='UP')
        cls.outra = Unidade.objects.create(nome='Unidade grande', sigla='UG')
        contrato = ContractType.objects.create(
            nome='Contrato desempenho', max_class_hours=20,
            max_total_hours=40, max_classes=4,
        )
        cls.professores = Professor.objects.bulk_create([
            Professor(
                rh_nome=f'Professor Matemática {i:05}', id_funcional=f'PERF{i}',
                rh_matricula=f'PERF{i}', tipo_contrato=contrato,
                unidade_principal=cls.unidade if i < 100 else cls.outra,
            )
            for i in range(5000)
        ])
        cls.coord = User.objects.create_user(
            email='perf.coord@harpia.test', perfil='COORDENADOR_UNIDADE',
            unidade=cls.unidade, forcar_troca_senha=False,
        )
        cls.desup = User.objects.create_user(
            email='perf.desup@harpia.test', perfil='DESUP', forcar_troca_senha=False,
        )

    def test_carga_rat_tem_consultas_constantes_por_unidade(self):
        from apps.core.forms import SolicitacaoRatUnidadeForm
        from apps.professors.services import obter_cargas_rat

        for unidade, total in ((self.unidade, 100), (self.outra, 4900)):
            with self.subTest(total=total):
                qs = SolicitacaoRatUnidadeForm(unidade=unidade).fields['professor'].queryset
                with self.assertNumQueries(6):
                    cargas = obter_cargas_rat(qs)
                self.assertEqual(len(cargas), total)
                self.assertTrue(all(not carga['completa'] for carga in cargas.values()))

    def test_busca_processa_apenas_candidatos_autorizados_e_filtrados(self):
        from apps.core.busca import texto_casa

        for user in (self.coord, self.desup):
            request = RequestFactory().get('/', {'q': 'Matematca', 'unidade_id': self.unidade.pk})
            request.user = user
            view = ProfessorListView()
            view.setup(request)
            with self.subTest(perfil=user.perfil), patch(
                'apps.core.busca.texto_casa', wraps=texto_casa,
            ) as comparar:
                ids = list(view.get_queryset().values_list('pk', flat=True))
                self.assertEqual(comparar.call_count, 100)
                self.assertEqual(set(ids), {p.pk for p in self.professores[:100]})

    def test_filtro_de_outra_unidade_nao_amplia_escopo(self):
        from apps.core.busca import texto_casa

        request = RequestFactory().get('/', {'q': 'Matematca', 'unidade_id': self.outra.pk})
        request.user = self.coord
        view = ProfessorListView()
        view.setup(request)
        with patch('apps.core.busca.texto_casa', wraps=texto_casa) as comparar:
            self.assertFalse(view.get_queryset().exists())
            comparar.assert_not_called()

    def test_dashboard_filtra_candidatos_antes_da_busca_e_pagina_o_resultado(self):
        from apps.core.busca import texto_casa

        self.client.force_login(self.desup)
        for rota in ('dashboard_desup', 'dashboard_professores_partial'):
            with self.subTest(rota=rota), patch(
                'apps.core.busca.texto_casa', wraps=texto_casa,
            ) as comparar:
                resposta = self.client.get(
                    reverse(rota), {'q': 'Matematca', 'unidade_id': self.unidade.pk},
                    HTTP_HX_REQUEST='true',
                )
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(comparar.call_count, 100)
                pagina = resposta.context.get('page_obj') or resposta.context['dashboard_page_obj']
                self.assertEqual(pagina.paginator.count, 100)
                self.assertEqual(len(pagina.object_list), 20)

    def test_autocomplete_sem_vinculo_multiplo_nao_faz_n_mais_um(self):
        from apps.allocations.views import BuscarProfessoresView

        counts = []
        for query, total in (('PERF00000', 0), ('00000', 1), ('Professor', 20)):
            # A busca deste endpoint é por nome; nenhum resultado para o ID.
            request = RequestFactory().get(reverse('buscar_professores'), {'q': query})
            request.user = self.desup
            with CaptureQueriesContext(connection) as consultas:
                response = BuscarProfessoresView.as_view()(request)
            results = json.loads(response.content)['results']
            self.assertEqual(len(results), total)
            if total:
                self.assertTrue(all(item['unidade'] == 'UP' for item in results))
                counts.append(len(consultas))
        self.assertEqual(counts[0], counts[1])

    def test_justificativas_nao_finalizadas_nao_carregam_relacoes(self):
        from apps.extra_curricular.models import PendenciaExtra
        from apps.extra_curricular.utils import semestre_atual
        from apps.professors.services import _bulk_ch_justificada

        PendenciaExtra.objects.bulk_create([
            PendenciaExtra(
                professor=p, unidade=self.unidade, semestre=semestre_atual(),
                status=PendenciaExtra.StatusChoices.ENVIADO,
            ) for p in self.professores[:100]
        ])
        with self.assertNumQueries(2):
            cargas = _bulk_ch_justificada([p.pk for p in self.professores[:100]])
        self.assertEqual(cargas, {})
