from django.test import TestCase

from apps.core.models import Unidade
from apps.courses.forms import CurriculumMatrixForm, MatrixComponentFormSet
from apps.courses.models import Course, CourseUnit, CurricularComponent, CurriculumMatrix, MatrixComponent


class CurriculumMatrixComponentTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome='Unidade Teste', sigla='UT')
        self.curso_global = Course.objects.create(
            nome='Sistemas de Informacao',
            sigla='SI',
        )
        self.curso = CourseUnit.objects.create(
            curso=self.curso_global,
            unidade=self.unidade,
        )
        self.algoritmos = CurricularComponent.objects.create(
            nome='Algoritmos',
            sigla='ALG',
            codigo='SI001',
            carga_horaria_padrao=80,
            creditos=4,
        )
        self.estrutura = CurricularComponent.objects.create(
            nome='Estrutura de Dados',
            sigla='ED',
            codigo='SI002',
            carga_horaria_padrao=80,
            creditos=4,
        )

    def test_matrix_formset_connects_multiple_components_to_one_matrix(self):
        """Verifica que o formset cria múltiplos componentes via disciplina_nome."""
        matrix_form = CurriculumMatrixForm(
            data={
                'curso': self.curso.id,
                'nome': 'Matriz Teste',
            }
        )
        matrix = CurriculumMatrix(curso=self.curso)
        formset = MatrixComponentFormSet(
            data={
                'componentes-TOTAL_FORMS': '2',
                'componentes-INITIAL_FORMS': '0',
                'componentes-MIN_NUM_FORMS': '1',
                'componentes-MAX_NUM_FORMS': '1000',
                'componentes-0-componente_curricular': self.algoritmos.id,
                'componentes-0-codigo': 'SI001',
                'componentes-0-periodo': '1º Semestre',
                'componentes-0-carga_horaria': '80',
                'componentes-0-creditos': '4',
                'componentes-0-carga_horaria_semanal': '4',
                'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
                'componentes-1-componente_curricular': self.estrutura.id,
                'componentes-1-codigo': 'SI002',
                'componentes-1-periodo': '2º Semestre',
                'componentes-1-carga_horaria': '80',
                'componentes-1-creditos': '4',
                'componentes-1-carga_horaria_semanal': '4',
                'componentes-1-status': MatrixComponent.StatusChoices.INCOMPLETO,
            },
            instance=matrix,
            prefix='componentes',
        )

        self.assertTrue(matrix_form.is_valid(), matrix_form.errors)
        self.assertTrue(formset.is_valid(), formset.errors)

        matrix = matrix_form.save()
        formset.instance = matrix
        formset.save()

        self.assertEqual(matrix.componentes_da_matriz.count(), 2)
        self.assertTrue(
            MatrixComponent.objects.filter(
                matriz=matrix,
                componente_curricular__nome='Algoritmos',
                carga_horaria=80,
                creditos=4,
                status=MatrixComponent.StatusChoices.SEM_PROFESSOR,
            ).exists()
        )

        ed_na_matriz = MatrixComponent.objects.get(
            matriz=matrix,
            componente_curricular__nome='Estrutura de Dados',
        )
        self.assertEqual(ed_na_matriz.status, MatrixComponent.StatusChoices.INCOMPLETO)

    def test_matrix_component_uses_component_defaults_when_fields_are_blank(self):
        """Verifica que campos omitidos herdam defaults do CurricularComponent via save()."""
        matrix = CurriculumMatrix(curso=self.curso)
        formset = MatrixComponentFormSet(
            data={
                'componentes-TOTAL_FORMS': '1',
                'componentes-INITIAL_FORMS': '0',
                'componentes-MIN_NUM_FORMS': '1',
                'componentes-MAX_NUM_FORMS': '1000',
                'componentes-0-componente_curricular': self.algoritmos.id,
                'componentes-0-carga_horaria_semanal': '4',
                'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            },
            instance=matrix,
            prefix='componentes',
        )

        self.assertTrue(formset.is_valid(), formset.errors)

        matrix.save()
        formset.instance = matrix
        formset.save()

        matrix_component = MatrixComponent.objects.get(matriz=matrix)
        # O componente deve ter sido encontrado pelo get_or_create (já criado no setUp)
        self.assertEqual(matrix_component.componente_curricular.nome, 'Algoritmos')
        self.assertEqual(matrix_component.componente_curricular.codigo, 'SI001')
