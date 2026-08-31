from decimal import Decimal

from django import forms
from django.template.defaultfilters import floatformat
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditoriaGlobal, Unidade
from apps.courses.forms import (
    CurriculumMatrixForm,
    MatrixComponentForm,
    MatrixComponentFormSet,
)
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
            codigo='SI001',
            carga_horaria_padrao=80,
            creditos=4,
        )
        self.estrutura = CurricularComponent.objects.create(
            nome='Estrutura de Dados',
            codigo='SI002',
            carga_horaria_padrao=80,
            creditos=4,
        )

    def test_matrix_formset_connects_multiple_components_to_one_matrix(self):
        """Verifica que o formset cria múltiplos componentes via disciplina_nome."""
        matrix_form = CurriculumMatrixForm(
            data={
                'curso': self.curso_global.id,
                'unidades': [self.unidade.id],
                'nome': 'Matriz Teste',
            }
        )
        matrix = CurriculumMatrix(curso=self.curso_global)
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
        matrix = CurriculumMatrix(curso=self.curso_global)
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

    def test_codigo_e_ch_semanal_ignoram_valor_adulterado_no_post(self):
        """Código e CH semanal são campos bloqueados: valor vindo do POST é ignorado
        e recalculado no servidor a partir da disciplina e da carga horária."""
        matrix = CurriculumMatrix(curso=self.curso_global)
        formset = MatrixComponentFormSet(
            data={
                'componentes-TOTAL_FORMS': '1',
                'componentes-INITIAL_FORMS': '0',
                'componentes-MIN_NUM_FORMS': '1',
                'componentes-MAX_NUM_FORMS': '1000',
                'componentes-0-componente_curricular': self.algoritmos.id,  # codigo SI001, CH padrão 80
                'componentes-0-carga_horaria': '80',
                'componentes-0-codigo': 'HACKED',          # tentativa de burlar
                'componentes-0-carga_horaria_semanal': '999',  # tentativa de burlar
                'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            },
            instance=matrix,
            prefix='componentes',
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        matrix.save()
        formset.instance = matrix
        formset.save()

        mc = MatrixComponent.objects.get(matriz=matrix)
        self.assertEqual(mc.codigo, 'SI001')                       # não 'HACKED'
        self.assertEqual(mc.carga_horaria_semanal, Decimal('4'))   # 80/20, não 999


class HoraAulaHoraRelogioTests(TestCase):
    """Conversão HA→HR (2 casas) e carga_horaria_semanal como hora-aula real."""

    def setUp(self):
        self.unidade = Unidade.objects.create(nome='Unidade HAHR', sigla='UHR')
        self.curso_global = Course.objects.create(
            nome='Analise e Desenvolvimento de Sistemas',
            sigla='ADS',
        )
        self.matriz = CurriculumMatrix.objects.create(curso=self.curso_global)

    def _make_component(self, codigo, carga_horaria):
        componente = CurricularComponent.objects.create(
            nome=f'Componente {codigo}',
            codigo=codigo,
            carga_horaria_padrao=carga_horaria,
        )
        return MatrixComponent.objects.create(
            matriz=self.matriz,
            componente_curricular=componente,
            carga_horaria=carga_horaria,
        )

    def test_hr_total_dois_decimais(self):
        """hr_total renderizado com floatformat:2 arredonda half-up para 2 casas."""
        casos = {80: '66.67', 48: '40.00', 40: '33.33'}
        for carga_horaria, esperado in casos.items():
            comp = self._make_component(f'CH{carga_horaria}', carga_horaria)
            self.assertEqual(
                floatformat(comp.hr_total, 2),
                esperado,
                f'carga_horaria={carga_horaria} deveria renderizar HR={esperado}',
            )

    def test_save_respeita_creditos_e_carga_horaria_semanal_digitados(self):
        """save() NÃO sobrescreve creditos/carga_horaria_semanal informados pela DESUP."""
        componente = CurricularComponent.objects.create(
            nome='Componente Digitado',
            codigo='DIG48',
            carga_horaria_padrao=48,
        )
        comp = MatrixComponent.objects.create(
            matriz=self.matriz,
            componente_curricular=componente,
            carga_horaria=48,
            creditos=7,
            carga_horaria_semanal=Decimal('3.5'),
        )
        comp.refresh_from_db()
        # 48 // 20 == 2 e round(48/20, 2) == 2.4 — NÃO devem sobrescrever os valores digitados.
        self.assertEqual(comp.creditos, 7)
        self.assertEqual(comp.carga_horaria_semanal, Decimal('3.5'))

    def test_save_preenche_calculados_quando_em_branco(self):
        """save() preenche creditos/carga_horaria_semanal como fallback quando vierem em branco."""
        componente = CurricularComponent.objects.create(
            nome='Componente Em Branco',
            codigo='BR48',
            carga_horaria_padrao=48,
        )
        comp = MatrixComponent(
            matriz=self.matriz,
            componente_curricular=componente,
            carga_horaria=48,
            creditos=None,
            carga_horaria_semanal=None,
        )
        comp.save()
        comp.refresh_from_db()
        self.assertEqual(comp.creditos, 2)
        self.assertEqual(comp.carga_horaria_semanal, Decimal('2.4'))


class MatrixPermissaoUnidadeTests(TestCase):
    """CORR-008: só a DESUP edita matriz; a unidade não edita e não vê rascunhos."""

    def setUp(self):
        self.client = Client()
        self.unidade = Unidade.objects.create(nome='Unidade Perm', sigla='UP')
        self.curso_global = Course.objects.create(nome='Curso Perm', sigla='CP')

        # Matriz publicada (vigente) da unidade — a unidade PODE ver.
        self.matriz_vigente = CurriculumMatrix.objects.create(
            curso=self.curso_global, is_vigente=True, is_rascunho=False,
        )
        self.matriz_vigente.unidades.add(self.unidade)

        # Matriz em rascunho da unidade — só a DESUP pode ver/editar.
        self.matriz_rascunho = CurriculumMatrix.objects.create(
            curso=self.curso_global, is_vigente=False, is_rascunho=True,
        )
        self.matriz_rascunho.unidades.add(self.unidade)

        self.desup = User.objects.create_user(
            email='desup_perm@teste.com', perfil='DESUP', forcar_troca_senha=False,
        )
        self.coord = User.objects.create_user(
            email='coord_perm@teste.com', perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade, forcar_troca_senha=False,
        )

    # ── Edição: só DESUP ────────────────────────────────────────────
    def test_unidade_nao_edita_matriz(self):
        """Coordenador de unidade é redirecionado ao tentar editar (mesmo rascunho)."""
        self.client.force_login(self.coord)
        url = reverse('courses:matrix_update', kwargs={'pk': self.matriz_rascunho.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:matrix_list'))

    def test_desup_edita_rascunho(self):
        """DESUP acessa normalmente a edição de uma matriz em rascunho."""
        self.client.force_login(self.desup)
        url = reverse('courses:matrix_update', kwargs={'pk': self.matriz_rascunho.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    # ── Visibilidade: rascunho invisível para a unidade ─────────────
    def test_unidade_nao_ve_rascunho_na_lista(self):
        """Na lista da unidade aparece a vigente, nunca o rascunho — nem forçando o filtro."""
        self.client.force_login(self.coord)
        resp = self.client.get(reverse('courses:matrix_list'))
        pks = {m.pk for m in resp.context['matrices']}
        self.assertIn(self.matriz_vigente.pk, pks)
        self.assertNotIn(self.matriz_rascunho.pk, pks)

        # Mesmo forçando ?status=rascunho, a unidade não enxerga rascunhos.
        resp_forcado = self.client.get(reverse('courses:matrix_list'), {'status': 'rascunho'})
        pks_forcado = {m.pk for m in resp_forcado.context['matrices']}
        self.assertNotIn(self.matriz_rascunho.pk, pks_forcado)

    def test_unidade_nao_ve_rascunho_no_detalhe(self):
        """Acesso direto ao detalhe de um rascunho pela unidade retorna 404."""
        self.client.force_login(self.coord)
        url = reverse('courses:matrix_detail', kwargs={'pk': self.matriz_rascunho.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_desup_ve_rascunho(self):
        """DESUP enxerga o rascunho na lista e no detalhe."""
        self.client.force_login(self.desup)
        resp_lista = self.client.get(reverse('courses:matrix_list'), {'status': 'rascunho'})
        pks = {m.pk for m in resp_lista.context['matrices']}
        self.assertIn(self.matriz_rascunho.pk, pks)

        url = reverse('courses:matrix_detail', kwargs={'pk': self.matriz_rascunho.pk})
        self.assertEqual(self.client.get(url).status_code, 200)


class MatrixCoexistenciaVigentesTests(TestCase):
    """CORR-011: publicar/duplicar uma matriz NÃO arquiva as demais do mesmo curso.

    Após a remoção do auto-arquivamento, matrizes do mesmo curso (ex.: turnos
    diferentes) coexistem como vigentes; o arquivamento passa a ser manual
    (CORR-012) ou em massa na virada de semestre.
    """

    def setUp(self):
        self.client = Client()
        self.unidade = Unidade.objects.create(nome='Unidade Coex', sigla='UC')
        self.curso_global = Course.objects.create(nome='Curso Coex', sigla='CC')
        self.componente = CurricularComponent.objects.create(
            nome='Componente Coex', codigo='CC001', carga_horaria_padrao=80, creditos=4,
        )
        # Matriz de origem já publicada (vigente) do curso.
        self.matriz_origem = CurriculumMatrix.objects.create(
            curso=self.curso_global, nome='MC-CC-Manha', is_vigente=True, is_rascunho=False,
        )
        self.matriz_origem.unidades.add(self.unidade)

        self.desup = User.objects.create_user(
            email='desup_coex@teste.com', perfil='DESUP', forcar_troca_senha=False,
        )
        self.client.force_login(self.desup)

    def _post_publicar_nova_matriz(self, nome):
        """POST no CreateView publicando uma nova matriz do mesmo curso."""
        return self.client.post(reverse('courses:matrix_create'), data={
            'curso': self.curso_global.id,
            'unidades': [self.unidade.id],
            'nome': nome,
            # publicar (salvar_rascunho ausente/≠ 'true' → is_vigente=True)
            'componentes-TOTAL_FORMS': '1',
            'componentes-INITIAL_FORMS': '0',
            'componentes-MIN_NUM_FORMS': '1',
            'componentes-MAX_NUM_FORMS': '1000',
            'componentes-0-componente_curricular': self.componente.id,
            'componentes-0-periodo': '1º Semestre',
            'componentes-0-carga_horaria': '80',
            'componentes-0-creditos': '4',
            'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
        })

    def test_publicar_nova_nao_arquiva_a_de_origem(self):
        """Publicar uma segunda matriz do mesmo curso mantém a de origem vigente."""
        resp = self._post_publicar_nova_matriz('MC-CC-Noite')
        self.assertEqual(resp.status_code, 302, getattr(resp, 'content', b''))

        self.matriz_origem.refresh_from_db()
        self.assertTrue(self.matriz_origem.is_vigente,
                        'A matriz de origem NÃO deve ser arquivada ao publicar outra do mesmo curso.')

        nova = CurriculumMatrix.objects.get(nome='MC-CC-Noite')
        self.assertTrue(nova.is_vigente)
        self.assertFalse(nova.is_rascunho)

    def test_duas_vigentes_do_mesmo_curso_coexistem(self):
        """Ambas as matrizes do mesmo curso ficam vigentes simultaneamente."""
        self._post_publicar_nova_matriz('MC-CC-Noite')
        vigentes = CurriculumMatrix.objects.filter(
            curso=self.curso_global, is_vigente=True,
        )
        self.assertEqual(vigentes.count(), 2)


class MatrixArquivarReativarTests(TestCase):
    """CORR-012: ação manual de arquivar/reativar matriz (DESUP-only)."""

    def setUp(self):
        self.client = Client()
        self.unidade = Unidade.objects.create(nome='Unidade Arq', sigla='UA')
        self.curso = Course.objects.create(nome='Curso Arq', sigla='CA')

        self.vigente = CurriculumMatrix.objects.create(
            curso=self.curso, nome='MC-CA-V', is_vigente=True, is_rascunho=False,
        )
        self.vigente.unidades.add(self.unidade)
        self.historico = CurriculumMatrix.objects.create(
            curso=self.curso, nome='MC-CA-H', is_vigente=False, is_rascunho=False,
        )
        self.historico.unidades.add(self.unidade)
        self.rascunho = CurriculumMatrix.objects.create(
            curso=self.curso, nome='MC-CA-R', is_vigente=False, is_rascunho=True,
        )
        self.rascunho.unidades.add(self.unidade)

        self.desup = User.objects.create_user(
            email='desup_arq@teste.com', perfil='DESUP', forcar_troca_senha=False,
        )
        self.coord = User.objects.create_user(
            email='coord_arq@teste.com', perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade, forcar_troca_senha=False,
        )

    # ── Arquivar ────────────────────────────────────────────────────
    def test_desup_arquiva_vigente(self):
        self.client.force_login(self.desup)
        resp = self.client.post(reverse('courses:matrix_archive', kwargs={'pk': self.vigente.pk}))
        self.assertEqual(resp.status_code, 302)
        self.vigente.refresh_from_db()
        self.assertFalse(self.vigente.is_vigente)
        self.assertFalse(self.vigente.is_rascunho)
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='MATRIZ_ARQUIVADA').exists())

    def test_arquivar_rascunho_bloqueado(self):
        self.client.force_login(self.desup)
        self.client.post(reverse('courses:matrix_archive', kwargs={'pk': self.rascunho.pk}))
        self.rascunho.refresh_from_db()
        self.assertTrue(self.rascunho.is_rascunho, 'Rascunho não deve ser arquivado.')

    def test_unidade_nao_arquiva(self):
        self.client.force_login(self.coord)
        resp = self.client.post(reverse('courses:matrix_archive', kwargs={'pk': self.vigente.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:matrix_list'))
        self.vigente.refresh_from_db()
        self.assertTrue(self.vigente.is_vigente, 'Unidade não pode arquivar matriz.')

    # ── Reativar ────────────────────────────────────────────────────
    def test_desup_reativa_historico(self):
        self.client.force_login(self.desup)
        resp = self.client.post(reverse('courses:matrix_reactivate', kwargs={'pk': self.historico.pk}))
        self.assertEqual(resp.status_code, 302)
        self.historico.refresh_from_db()
        self.assertTrue(self.historico.is_vigente)
        self.assertFalse(self.historico.is_rascunho)
        self.assertTrue(AuditoriaGlobal.objects.filter(acao='MATRIZ_REATIVADA').exists())

    def test_reativar_nao_arquiva_as_demais_do_curso(self):
        """CORR-011: reativar uma matriz NÃO arquiva as outras vigentes do curso."""
        self.client.force_login(self.desup)
        self.client.post(reverse('courses:matrix_reactivate', kwargs={'pk': self.historico.pk}))
        self.vigente.refresh_from_db()
        self.assertTrue(self.vigente.is_vigente, 'A vigente existente deve permanecer vigente.')
        self.assertEqual(
            CurriculumMatrix.objects.filter(curso=self.curso, is_vigente=True).count(), 2,
        )


# ══════════════════════════════════════════════════════════════════════════════
# CORR-007 — Só Disciplina e Período são editáveis no componente da matriz
# ══════════════════════════════════════════════════════════════════════════════
class MatrixComponentCamposBloqueadosTests(TestCase):
    """
    Ao criar/editar matriz, o usuário só informa **Disciplina** e **Período**.
    'Código', 'CH Total', 'Créditos' e 'CH Sem.' derivam da disciplina no servidor
    e são `disabled` — o valor vindo do POST é ignorado (à prova de adulteração).
    """

    def setUp(self):
        self.unidade = Unidade.objects.create(nome='Unidade CORR007', sigla='U7')
        self.curso_global = Course.objects.create(nome='Curso CORR007', sigla='C7')
        self.disciplina = CurricularComponent.objects.create(
            nome='Disciplina CORR007',
            codigo='C7001',
            carga_horaria_padrao=80,
            creditos=4,
        )

    def _formset(self, extra_data=None):
        matrix = CurriculumMatrix(curso=self.curso_global)
        data = {
            'componentes-TOTAL_FORMS': '1',
            'componentes-INITIAL_FORMS': '0',
            'componentes-MIN_NUM_FORMS': '1',
            'componentes-MAX_NUM_FORMS': '1000',
            'componentes-0-componente_curricular': self.disciplina.id,
            'componentes-0-periodo': '1º Semestre',
            'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
        }
        data.update(extra_data or {})
        formset = MatrixComponentFormSet(data=data, instance=matrix, prefix='componentes')
        return matrix, formset

    # ── Os campos estão realmente bloqueados ────────────────────────
    def test_apenas_disciplina_e_periodo_ficam_editaveis(self):
        form = MatrixComponentForm()
        editaveis = {
            nome for nome, field in form.fields.items()
            if not field.disabled and not isinstance(field.widget, forms.HiddenInput)
        }
        # 'compartilhado' e 'curso_compartilhado' seguem editáveis (outra regra);
        # o que importa aqui é que os 4 campos derivados estejam travados.
        for bloqueado in ('codigo', 'carga_horaria', 'creditos', 'carga_horaria_semanal'):
            with self.subTest(campo=bloqueado):
                self.assertTrue(form.fields[bloqueado].disabled)
                self.assertNotIn(bloqueado, editaveis)
        self.assertIn('componente_curricular', editaveis)
        self.assertIn('periodo', editaveis)

    def test_campos_bloqueados_renderizam_com_disabled(self):
        html = str(MatrixComponentForm()['carga_horaria']) + str(MatrixComponentForm()['creditos'])
        self.assertEqual(html.count('disabled'), 2)

    # ── Derivação no servidor ───────────────────────────────────────
    def test_ch_total_e_creditos_derivados_da_disciplina_quando_omitidos(self):
        matrix, formset = self._formset()
        self.assertTrue(formset.is_valid(), formset.errors)
        matrix.save()
        formset.instance = matrix
        formset.save()

        mc = MatrixComponent.objects.get(matriz=matrix)
        self.assertEqual(mc.carga_horaria, 80)             # CH padrão da disciplina
        self.assertEqual(mc.creditos, 4)                   # 80 // 20
        self.assertEqual(mc.carga_horaria_semanal, Decimal('4'))
        self.assertEqual(mc.codigo, 'C7001')

    def test_ch_total_e_creditos_adulterados_no_post_sao_ignorados(self):
        """Regressão CORR-007: POST forjado não pode alterar CH Total nem Créditos."""
        matrix, formset = self._formset({
            'componentes-0-carga_horaria': '999',
            'componentes-0-creditos': '99',
            'componentes-0-codigo': 'HACKED',
            'componentes-0-carga_horaria_semanal': '777',
        })
        self.assertTrue(formset.is_valid(), formset.errors)
        matrix.save()
        formset.instance = matrix
        formset.save()

        mc = MatrixComponent.objects.get(matriz=matrix)
        self.assertEqual(mc.carga_horaria, 80)             # não 999
        self.assertEqual(mc.creditos, 4)                   # não 99
        self.assertEqual(mc.codigo, 'C7001')               # não 'HACKED'
        self.assertEqual(mc.carga_horaria_semanal, Decimal('4'))  # não 777

    def test_periodo_continua_sendo_gravado_do_post(self):
        matrix, formset = self._formset({'componentes-0-periodo': '3º Semestre'})
        self.assertTrue(formset.is_valid(), formset.errors)
        matrix.save()
        formset.instance = matrix
        formset.save()

        self.assertEqual(MatrixComponent.objects.get(matriz=matrix).periodo, '3º Semestre')

    def test_ch_nao_multipla_de_20_deriva_creditos_e_ch_semanal(self):
        disciplina = CurricularComponent.objects.create(
            nome='Disciplina 90h', codigo='C7090', carga_horaria_padrao=90, creditos=4,
        )
        matrix = CurriculumMatrix(curso=self.curso_global)
        formset = MatrixComponentFormSet(
            data={
                'componentes-TOTAL_FORMS': '1',
                'componentes-INITIAL_FORMS': '0',
                'componentes-MIN_NUM_FORMS': '1',
                'componentes-MAX_NUM_FORMS': '1000',
                'componentes-0-componente_curricular': disciplina.id,
                'componentes-0-periodo': '1º Semestre',
                'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            },
            instance=matrix,
            prefix='componentes',
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        matrix.save()
        formset.instance = matrix
        formset.save()

        mc = MatrixComponent.objects.get(matriz=matrix)
        self.assertEqual(mc.carga_horaria, 90)
        self.assertEqual(mc.creditos, 4)                          # 90 // 20
        self.assertEqual(mc.carga_horaria_semanal, Decimal('4.5'))  # 90 / 20

    # ── Edição preserva o valor já gravado ──────────────────────────
    def test_edicao_preserva_ch_ja_gravada_e_ignora_post(self):
        matrix = CurriculumMatrix.objects.create(curso=self.curso_global, nome='M CORR007')
        mc = MatrixComponent.objects.create(
            matriz=matrix,
            componente_curricular=self.disciplina,
            periodo='1º Semestre',
            carga_horaria=60,          # valor legado, diferente da CH padrão (80)
            creditos=3,
        )
        formset = MatrixComponentFormSet(
            data={
                'componentes-TOTAL_FORMS': '1',
                'componentes-INITIAL_FORMS': '1',
                'componentes-MIN_NUM_FORMS': '1',
                'componentes-MAX_NUM_FORMS': '1000',
                'componentes-0-id': mc.pk,
                'componentes-0-componente_curricular': self.disciplina.id,
                'componentes-0-periodo': '2º Semestre',
                'componentes-0-carga_horaria': '999',   # adulterado
                'componentes-0-creditos': '99',         # adulterado
                'componentes-0-status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            },
            instance=matrix,
            prefix='componentes',
        )
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()

        mc.refresh_from_db()
        self.assertEqual(mc.carga_horaria, 60)   # mantém o legado, não vira 999 nem 80
        self.assertEqual(mc.creditos, 3)         # 60 // 20
        self.assertEqual(mc.periodo, '2º Semestre')
