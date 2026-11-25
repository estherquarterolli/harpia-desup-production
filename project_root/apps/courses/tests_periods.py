from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from .forms import MatrixComponentForm
from .import_services import parse_matrix_rows
from .management.commands.import_matrizes import _detect_periodo
from .models import Course, CurricularComponent, CurriculumMatrix, MatrixComponent
from .periods import normalizar_periodo_matriz


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PeriodosMatrizTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.desup = User.objects.create_user(email='periodos@example.test', password='senha', perfil='DESUP', forcar_troca_senha=False)
        cls.curso = Course.objects.create(nome='Curso', sigla='CURSO')
        cls.disciplina = CurricularComponent.objects.create(nome='Algoritmos', codigo='ALG', carga_horaria_padrao=80)
        cls.matriz = CurriculumMatrix.objects.create(curso=cls.curso, nome='Matriz legada', turno='N', is_rascunho=False)

    def componente(self, periodo):
        return MatrixComponent.objects.create(matriz=self.matriz, componente_curricular=self.disciplina, periodo=periodo, carga_horaria=60)

    def test_novas_opcoes_e_normalizacao_importacao(self):
        escolhas = dict(MatrixComponentForm().fields['periodo'].widget.choices)
        self.assertIn('1º Período', escolhas)
        self.assertNotIn('1º Semestre', escolhas)
        for valor in ('1o periodo', '1º Período', '1º Semestre', 'Período 1', 'Semestre 1', '1º - período', 1):
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_periodo_matriz(valor), '1º Período')
        for valor in ('', '9º Período', '10', 'Período 10'):
            self.assertIsNone(normalizar_periodo_matriz(valor))
        self.assertEqual(_detect_periodo('2-ALG'), '2º Período')
        self.assertEqual(_detect_periodo('3ORG'), '3º Período')
        for valor in ('1o periodo', '1º Semestre'):
            preview = parse_matrix_rows([{'nome': 'Algoritmos', 'periodo': valor, 'carga_horaria': 80}])[0]
            self.assertEqual(preview.periodo, '1º Período')

    def test_editar_preserva_valor_exato_carga_e_identificador(self):
        self.client.force_login(self.desup)
        for valor in ('1o periodo', '1º Período', '1º Semestre', '', '9º Período', 'Módulo especial', ' 1o periodo '):
            with self.subTest(valor=valor):
                comp = self.componente(valor)
                url = reverse('courses:matrix_update', args=[self.matriz.pk])
                response = self.client.get(url)
                form = response.context['component_formset'].forms[0]
                self.assertInHTML(f'<option value="{valor}" selected>{valor or "Selecione"}</option>', str(form['periodo']))
                data = {
                    'curso': self.curso.pk, 'nome': 'Matriz com outro nome', 'turno': 'N', 'acao': 'salvar_vigente',
                    'componentes-TOTAL_FORMS': 1, 'componentes-INITIAL_FORMS': 1,
                    'componentes-0-id': comp.pk, 'componentes-0-componente_curricular': self.disciplina.pk,
                    'componentes-0-periodo': valor, 'componentes-0-status': comp.status,
                }
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
                comp.refresh_from_db()
                self.assertEqual(comp.periodo, valor)
                self.assertEqual(comp.carga_horaria, 60)
                self.assertEqual(comp.componente_curricular_id, self.disciplina.pk)
                comp.delete()

    def test_escolha_explicita_salva_novo_padrao(self):
        comp = self.componente('1o periodo')
        form = MatrixComponentForm(data={'componente_curricular': self.disciplina.pk, 'periodo': '2º Período', 'status': comp.status}, instance=comp)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        comp.refresh_from_db()
        self.assertEqual(comp.periodo, '2º Período')

    def test_erro_nao_perde_periodo_legado_ou_copiado(self):
        for valor in ('1o periodo', 'Módulo especial'):
            form = MatrixComponentForm(data={'periodo': valor})
            self.assertFalse(form.is_valid())
            self.assertInHTML(f'<option value="{valor}" selected>{valor}</option>', str(form['periodo']))
            copia = MatrixComponentForm(initial={'periodo': valor})
            self.assertInHTML(f'<option value="{valor}" selected>{valor}</option>', str(copia['periodo']))

    def test_copias_json_e_html_preservam_texto(self):
        self.client.force_login(self.desup)
        comp = self.componente('1o periodo')
        response = self.client.get(reverse('courses:matrix_dados_copiar', args=[self.matriz.pk]))
        self.assertEqual(response.json()['componentes'][0]['periodo'], comp.periodo)
        response = self.client.get(reverse('courses:matrix_import_previous'), {'curso_id': self.curso.pk})
        self.assertContains(response, '<option value="1o periodo" selected>1o periodo</option>', html=True)
