from django.test import SimpleTestCase

from apps.accounts.admin import CustomUserAdmin, HarpiaModelAdmin
from apps.accounts.views import DesupUserListView
from apps.core.views import CursoListView, JanelaEntregaListView, UnidadeListView
from apps.courses.views import CurricularComponentListView, CurriculumMatrixListView
from apps.professors.views import ProfessorListView


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

    def test_superadmin_tambem_limita_resultados(self):
        self.assertEqual(HarpiaModelAdmin.list_per_page, 25)
        self.assertFalse(HarpiaModelAdmin.show_full_result_count)
        self.assertEqual(CustomUserAdmin.list_per_page, 25)
        self.assertFalse(CustomUserAdmin.show_full_result_count)
