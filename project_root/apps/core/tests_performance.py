from pathlib import Path

from django.test import SimpleTestCase

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
