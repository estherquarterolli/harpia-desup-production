"""
Testes END-TO-END (E2E) do app `professors`.

As jornadas passam pelas rotas reais do namespace `professors`
(apps/professors/urls.py):

    professors:professor_list        -> /professores/
    professors:professor_create      -> /professores/criar/
    professors:professor_update      -> /professores/<pk>/editar/
    professors:professor_delete      -> /professores/<pk>/excluir/
    professors:professor_duplicar    -> /professores/<pk>/duplicar/
    professors:htmx_tabela_alocacao  -> /professores/htmx/tabela-alocacao/
    professors:htmx_cursos_unidade   -> /professores/htmx/cursos-unidade/

Convenções destes testes:
- Usuários sempre com `forcar_troca_senha=False` (senão o
  `PasswordChangeForceMiddleware` redireciona tudo para a troca de senha).
- Permissões conforme as views: criar é exclusivo da DESUP (`pode_criar`);
  editar/duplicar/excluir são do COORDENADOR_UNIDADE (`CoordenadorOnlyMixin`).
- Os testes com docstring "CORRIGIDO" nasceram como BUG-CANDIDATO
  (`@unittest.expectedFailure`): a asserção descreve o comportamento CORRETO,
  o bug foi corrigido e eles passaram a valer como teste de regressão.
"""

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import Unidade
from apps.courses.models import (
    Course,
    CourseUnit,
    CurricularComponent,
    CurriculumMatrix,
    MatrixComponent,
)
from apps.extra_curricular.models import OrientacaoTCC, ParecerChoices, PendenciaExtra
from apps.extra_curricular.utils import semestre_atual
from apps.professors.models import ContractType, Professor


class ProfessorE2EBase(TestCase):
    """Cenário base: duas unidades com cursos, docentes e usuários dos 3 perfis."""

    def setUp(self):
        self.semestre_atual = semestre_atual()

        self.unidade_a = Unidade.objects.create(nome='Unidade Alfa', sigla='UA')
        self.unidade_b = Unidade.objects.create(nome='Unidade Beta', sigla='UB')

        self.curso_ads = Course.objects.create(nome='Analise e Desenvolvimento', sigla='ADS')
        self.curso_log = Course.objects.create(nome='Logistica', sigla='LOG')
        self.curso_enf = Course.objects.create(nome='Enfermagem', sigla='ENF')

        self.course_unit_ads_a = CourseUnit.objects.create(curso=self.curso_ads, unidade=self.unidade_a)
        self.course_unit_log_a = CourseUnit.objects.create(
            curso=self.curso_log, unidade=self.unidade_a, ativo=False
        )
        self.course_unit_enf_b = CourseUnit.objects.create(curso=self.curso_enf, unidade=self.unidade_b)

        self.contrato = ContractType.objects.create(
            nome='Ensino Superior',
            regime_trabalho='40h DE',
            max_class_hours=20,
            max_total_hours=40,
            max_classes=4,
        )

        self.prof_a1 = self._professor('Ana Alves', 'A1', self.unidade_a)
        self.prof_b1 = self._professor('Carla Costa', 'B1', self.unidade_b)

        self.desup = User.objects.create_user(
            email='desup.prof@harpia.test', password='pw',
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.coord_a = User.objects.create_user(
            email='coord.a.prof@harpia.test', password='pw',
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade_a, forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email='coord.b.prof@harpia.test', password='pw',
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade_b, forcar_troca_senha=False,
        )
        self.admin_ti = User.objects.create_user(
            email='ti.prof@harpia.test', password='pw',
            perfil='ADMIN', forcar_troca_senha=False,
        )

        self.url_lista = reverse('professors:professor_list')
        self.url_criar = reverse('professors:professor_create')

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _professor(self, nome, sufixo, unidade, **kwargs):
        return Professor.objects.create(
            id_funcional=f'IDF-{sufixo}',
            rh_matricula=f'MAT-{sufixo}',
            rh_nome=nome,
            rh_email=f'{sufixo.lower()}@harpia.test',
            unidade_principal=unidade,
            tipo_contrato=self.contrato,
            **kwargs,
        )

    def _matriz_vigente(self, curso, unidade, turno='M', nome='MC-2026'):
        matriz = CurriculumMatrix.objects.create(
            curso=curso,
            nome=nome,
            is_vigente=True,
            is_rascunho=False,
            turno=turno,
            periodo_letivo=self.semestre_atual,
        )
        matriz.unidades.add(unidade)
        return matriz

    def _componente(self, matriz, nome, codigo, carga_horaria=80, docente=None, **kwargs):
        componente = CurricularComponent.objects.create(
            nome=nome,
            codigo=codigo,
            carga_horaria_padrao=carga_horaria,
            creditos=carga_horaria // 20,
        )
        return MatrixComponent.objects.create(
            matriz=matriz,
            componente_curricular=componente,
            periodo='1o periodo',
            carga_horaria=carga_horaria,
            creditos=carga_horaria // 20,
            carga_horaria_semanal=carga_horaria / 20,
            docente=docente,
            status=(
                MatrixComponent.StatusChoices.COMPLETO
                if docente
                else MatrixComponent.StatusChoices.SEM_PROFESSOR
            ),
            **kwargs,
        )

    def _dados_professor(self, **overrides):
        dados = {
            'id_funcional': 'IDF-NOVO',
            'rh_matricula': 'MAT-NOVO',
            'rh_nome': 'Daniel Dias',
            'tipo_contrato': self.contrato.pk,
            'unidade_principal': self.unidade_a.pk,
            'materia': Professor.MateriaChoices.INFORMATICA,
            'status': Professor.StatusChoices.ATIVO,
            'cursos': [self.curso_ads.pk],
            'limite_horas_extra': '',
        }
        dados.update(overrides)
        return dados

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def _justificativa_aprovada(self, professor, unidade, num_orientandos=4, status=None):
        """Cria uma PendenciaExtra do semestre atual com uma orientação de TCC.

        O parecer do item também vai como APROVADO: `ch_total_justificada` só soma
        item com parecer da DESUP (o status do cabeçalho sozinho não basta), e é
        justamente essa CH aprovada que `Professor.ch_justificada` consome.
        """
        pendencia = PendenciaExtra.objects.create(
            professor=professor,
            unidade=unidade,
            semestre=self.semestre_atual,
            status=status or PendenciaExtra.StatusChoices.APROVADO,
        )
        OrientacaoTCC.objects.create(
            pendencia=pendencia,
            num_orientandos=num_orientandos,
            parecer_desup=ParecerChoices.APROVADO,
        )
        return pendencia


class CrudProfessorE2ETests(ProfessorE2EBase):
    """Cenário 9: jornada de CRUD completo com as permissões de cada perfil."""

    def test_jornada_crud_completa_criar_editar_duplicar_excluir(self):
        # 1) DESUP cria o professor (é o único perfil com `pode_criar`).
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_criar)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'professors/professor_form.html')

        resposta = self.client.post(self.url_criar, self._dados_professor())
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], self.url_lista)

        novo = Professor.objects.get(id_funcional='IDF-NOVO')
        self.assertEqual(novo.rh_nome, 'Daniel Dias')
        self.assertEqual(novo.unidade_principal, self.unidade_a)
        self.assertEqual(list(novo.cursos.all()), [self.curso_ads])
        self.assertTrue(
            any('cadastrado' in m for m in self._mensagens(resposta)),
            self._mensagens(resposta),
        )

        # 2) O coordenador da unidade edita (a DESUP não edita — ver teste de permissões).
        self.client.force_login(self.coord_a)
        url_editar = reverse('professors:professor_update', kwargs={'pk': novo.pk})

        resposta = self.client.get(url_editar)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Daniel Dias')

        resposta = self.client.post(
            url_editar,
            self._dados_professor(
                rh_nome='Daniel Dias da Silva',
                status=Professor.StatusChoices.AFASTADO,
            ),
        )
        self.assertEqual(resposta.status_code, 302)
        novo.refresh_from_db()
        self.assertEqual(novo.rh_nome, 'Daniel Dias da Silva')
        self.assertEqual(novo.status, Professor.StatusChoices.AFASTADO)
        self.assertEqual(novo.unidade_principal, self.unidade_a)
        self.assertTrue(
            any('atualizado' in m for m in self._mensagens(resposta)),
            self._mensagens(resposta),
        )

        # 3) O coordenador duplica: cópia com prefixo e redirect para a edição dela.
        url_duplicar = reverse('professors:professor_duplicar', kwargs={'pk': novo.pk})
        resposta = self.client.post(url_duplicar)
        self.assertEqual(resposta.status_code, 302)

        copia = Professor.objects.get(id_funcional='COPIA-IDF-NOVO')
        self.assertEqual(
            resposta['Location'],
            reverse('professors:professor_update', kwargs={'pk': copia.pk}),
        )
        self.assertEqual(copia.rh_matricula, 'COPIA-MAT-NOVO')
        self.assertEqual(copia.rh_nome, '[Cópia] Daniel Dias da Silva')
        self.assertEqual(copia.unidade_principal, self.unidade_a)
        self.assertEqual(list(copia.cursos.all()), [self.curso_ads])
        # O original continua intacto.
        novo.refresh_from_db()
        self.assertEqual(novo.rh_nome, 'Daniel Dias da Silva')
        self.assertEqual(Professor.objects.filter(unidade_principal=self.unidade_a).count(), 3)

        # 4) O coordenador exclui a cópia.
        url_excluir = reverse('professors:professor_delete', kwargs={'pk': copia.pk})
        resposta = self.client.get(url_excluir)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'professors/professor_confirm_delete.html')

        resposta = self.client.post(url_excluir)
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], self.url_lista)
        self.assertFalse(Professor.objects.filter(pk=copia.pk).exists())
        self.assertTrue(Professor.objects.filter(pk=novo.pk).exists())

    def test_coordenador_nao_pode_criar_professor(self):
        """`pode_criar` é exclusivo da DESUP (ProfessorListView.get_context_data)."""
        self.client.force_login(self.coord_a)

        self.assertEqual(self.client.get(self.url_criar).status_code, 403)
        self.assertEqual(
            self.client.post(self.url_criar, self._dados_professor()).status_code, 403
        )
        self.assertFalse(Professor.objects.filter(id_funcional='IDF-NOVO').exists())

        # E a lista não oferece o botão "Novo Professor" para a unidade.
        resposta = self.client.get(self.url_lista)
        self.assertFalse(resposta.context['pode_criar'])
        self.assertNotContains(resposta, 'Novo Professor')

    def test_desup_ve_botao_criar_mas_nao_edita_nem_exclui(self):
        """
        Assimetria REAL do produto (documentada, não é asserção enfraquecida):
        as views de editar/excluir/duplicar usam `CoordenadorOnlyMixin`, então a
        DESUP — que é justamente quem cria — recebe 403 nelas, apesar de o
        contexto `pode_crud` (apps/professors/views.py:50-52) afirmar que a DESUP
        pode editar. Ver relatório: inconsistência entre contexto e permissão.
        """
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_lista)
        self.assertTrue(resposta.context['pode_criar'])
        self.assertTrue(resposta.context['pode_crud'])
        self.assertContains(resposta, 'Novo Professor')

        alvo = self.prof_a1.pk
        self.assertEqual(
            self.client.get(reverse('professors:professor_update', kwargs={'pk': alvo})).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('professors:professor_delete', kwargs={'pk': alvo})).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('professors:professor_duplicar', kwargs={'pk': alvo})).status_code,
            403,
        )
        self.assertTrue(Professor.objects.filter(pk=alvo).exists())

    def test_coordenador_nao_edita_exclui_ou_duplica_professor_de_outra_unidade(self):
        self.client.force_login(self.coord_a)
        alvo = self.prof_b1.pk

        self.assertEqual(
            self.client.get(reverse('professors:professor_update', kwargs={'pk': alvo})).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('professors:professor_delete', kwargs={'pk': alvo})).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse('professors:professor_duplicar', kwargs={'pk': alvo})).status_code,
            404,
        )
        self.assertTrue(Professor.objects.filter(pk=alvo).exists())

    def test_perfil_admin_ti_e_redirecionado_para_o_admin_do_django(self):
        self.client.force_login(self.admin_ti)

        resposta = self.client.get(self.url_criar)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], '/admin/')

    def test_anonimo_vai_para_o_login_na_listagem(self):
        resposta = self.client.get(self.url_lista)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_rotas_de_escrita_deveriam_exigir_login(self):
        """
        CORRIGIDO: as rotas de escrita de professor mandam o anônimo para o
        login em vez de estourar 500.

        `CoordenadorOnlyMixin` e `DesupOnlyMixin` herdavam SÓ de
        `PerfilRequiredMixin`, que para usuário não autenticado apenas delega ao
        `super().dispatch` (apps/accounts/mixins.py) — o request anônimo chegava
        no corpo da view e quebrava em `AnonymousUser.perfil` / `.unidade`
        (AttributeError/500). Agora os dois mixins herdam também de
        `LoginRequiredMixin`, que barra o anônimo antes.
        """
        rotas = [
            self.url_criar,
            reverse('professors:professor_update', kwargs={'pk': self.prof_a1.pk}),
            reverse('professors:professor_delete', kwargs={'pk': self.prof_a1.pk}),
        ]
        for rota in rotas:
            resposta = self.client.get(rota)
            self.assertEqual(resposta.status_code, 302, rota)
            self.assertIn(reverse('login'), resposta['Location'], rota)

    def test_matricula_igual_ao_id_funcional_e_recusada(self):
        """Regra do model (`Professor.clean`) chega até o formulário da tela."""
        self.client.force_login(self.desup)

        resposta = self.client.post(
            self.url_criar,
            self._dados_professor(id_funcional='REPETIDO', rh_matricula='REPETIDO'),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFormError(
            resposta.context['form'],
            'rh_matricula',
            'A matrícula deve ser diferente do ID Funcional.',
        )
        self.assertFalse(Professor.objects.filter(id_funcional='REPETIDO').exists())

    def test_duplicar_duas_vezes_o_mesmo_professor_nao_deve_estourar(self):
        """
        CORRIGIDO: duplicar o mesmo professor duas vezes não gera mais 500.

        `ProfessorDuplicarView` montava o novo identificador com um prefixo fixo
        (`COPIA-<id_funcional>`), mas `id_funcional`/`rh_matricula` são `unique`
        (apps/professors/models.py:48-55) — na segunda duplicação do MESMO
        professor o INSERT violava o unique (IntegrityError/500). Agora
        `_identificador_unico_de_copia` incrementa o prefixo
        (`COPIA-2-`, `COPIA-3-`…) até achar um identificador livre.
        """
        self.client.force_login(self.coord_a)
        url_duplicar = reverse('professors:professor_duplicar', kwargs={'pk': self.prof_a1.pk})

        self.client.post(url_duplicar)
        resposta = self.client.post(url_duplicar)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            Professor.objects.filter(rh_nome__startswith='[Cópia]').count(), 2
        )

    def test_excluir_professor_alocado_deve_avisar_em_vez_de_estourar(self):
        """
        CORRIGIDO: excluir professor alocado em matriz vigente avisa em vez de
        estourar 500.

        `MatrixComponent.docente` usa `on_delete=PROTECT`
        (apps/courses/models.py:197-204) e `ProfessorDeleteView` não tratava o
        `ProtectedError`. Agora `form_valid` captura a exceção, mostra
        "libere as alocações antes de excluir" e redireciona para a listagem.
        """
        matriz = self._matriz_vigente(self.curso_ads, self.unidade_a)
        self._componente(matriz, 'Algoritmos', 'ADS001', docente=self.prof_a1)
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse('professors:professor_delete', kwargs={'pk': self.prof_a1.pk})
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Professor.objects.filter(pk=self.prof_a1.pk).exists())

    def test_exclusao_deveria_mostrar_mensagem_de_sucesso(self):
        """
        CORRIGIDO: a mensagem "Professor excluído com sucesso." volta a aparecer.

        `ProfessorDeleteView.delete()` era código morto desde o Django 4.0: a
        `DeleteView` passou a usar `FormMixin` e o POST cai em `form_valid()`,
        não em `delete()` — o projeto roda Django 6, então a exclusão acontecia
        em silêncio. A lógica foi movida para `form_valid()`.
        """
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse('professors:professor_delete', kwargs={'pk': self.prof_a1.pk})
        )

        self.assertFalse(Professor.objects.filter(pk=self.prof_a1.pk).exists())
        self.assertTrue(
            any('excluído' in m for m in self._mensagens(resposta)),
            self._mensagens(resposta),
        )


class OverrideDesupProfessorE2ETests(ProfessorE2EBase):
    """Cenário 10 (Regra #3): ajuste da DESUP prevalece sobre o dado do RH."""

    def test_nome_e_email_ajustados_prevalecem_na_listagem(self):
        self.prof_a1.desup_nome = 'Ana Alves Ajustada'
        self.prof_a1.desup_email = 'ana.ajustada@harpia.test'
        self.prof_a1.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_lista)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.prof_a1.nome, 'Ana Alves Ajustada')
        self.assertEqual(self.prof_a1.email, 'ana.ajustada@harpia.test')
        # A tela usa `prof.nome` (override) mas preserva a matrícula do RH.
        self.assertContains(resposta, 'Ana Alves Ajustada')
        self.assertNotContains(resposta, '>Ana Alves<')
        self.assertContains(resposta, 'MAT-A1')

    def test_dados_de_rh_permanecem_intactos_apos_override(self):
        self.prof_a1.desup_nome = 'Ana Alves Ajustada'
        self.prof_a1.desup_email = 'ana.ajustada@harpia.test'
        self.prof_a1.save()
        self.prof_a1.refresh_from_db()

        self.assertEqual(self.prof_a1.rh_nome, 'Ana Alves')
        self.assertEqual(self.prof_a1.rh_email, 'a1@harpia.test')

    def test_override_vazio_cai_de_volta_para_o_rh(self):
        self.prof_a1.desup_nome = ''
        self.prof_a1.desup_email = ''
        self.prof_a1.save()

        self.assertEqual(self.prof_a1.nome, 'Ana Alves')
        self.assertEqual(self.prof_a1.email, 'a1@harpia.test')

    def test_edicao_pela_tela_nao_apaga_o_override_da_desup(self):
        """O formulário não expõe `desup_nome`/`desup_email`: eles sobrevivem à edição."""
        self.prof_a1.desup_nome = 'Ana Alves Ajustada'
        self.prof_a1.desup_email = 'ana.ajustada@harpia.test'
        self.prof_a1.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            reverse('professors:professor_update', kwargs={'pk': self.prof_a1.pk}),
            self._dados_professor(
                id_funcional=self.prof_a1.id_funcional,
                rh_matricula=self.prof_a1.rh_matricula,
                rh_nome='Ana Alves (RH corrigido)',
            ),
        )

        self.assertEqual(resposta.status_code, 302)
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.rh_nome, 'Ana Alves (RH corrigido)')
        self.assertEqual(self.prof_a1.nome, 'Ana Alves Ajustada')


class IsolamentoUnidadeProfessorE2ETests(ProfessorE2EBase):
    """Cenário 11: isolamento por unidade na listagem e no `for_user`."""

    def test_coordenador_ve_apenas_a_propria_unidade_na_listagem(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_lista)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([p.pk for p in resposta.context['professores']], [self.prof_a1.pk])
        self.assertContains(resposta, 'Ana Alves')
        self.assertNotContains(resposta, 'Carla Costa')
        self.assertFalse(resposta.context['is_desup'])
        self.assertEqual(resposta.context['unidade_atual'], self.unidade_a)

    def test_desup_ve_todas_as_unidades_e_filtra_por_unidade(self):
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_lista)
        self.assertTrue(resposta.context['is_desup'])
        self.assertCountEqual(
            [p.pk for p in resposta.context['professores']],
            [self.prof_a1.pk, self.prof_b1.pk],
        )

        resposta = self.client.get(self.url_lista, {'unidade_id': self.unidade_b.id})
        self.assertEqual([p.pk for p in resposta.context['professores']], [self.prof_b1.pk])
        self.assertEqual(resposta.context['unidade_atual'], self.unidade_b)

    def test_busca_por_nome_na_listagem_respeita_a_unidade(self):
        self._professor('Ana Aparecida', 'B2', self.unidade_b)
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_lista, {'q': 'Ana'})

        self.assertEqual([p.pk for p in resposta.context['professores']], [self.prof_a1.pk])

    def test_coordenador_sem_unidade_nao_ve_professor_algum(self):
        self.coord_a.unidade = None
        self.coord_a.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_lista)

        self.assertEqual(list(resposta.context['professores']), [])
        self.assertContains(resposta, 'Nenhum professor encontrado')

    def test_for_user_espelha_o_isolamento_da_tela(self):
        """`Professor.objects.for_user` é a fonte do isolamento por unidade."""
        self.assertCountEqual(
            Professor.objects.for_user(self.desup),
            [self.prof_a1, self.prof_b1],
        )
        self.assertEqual(list(Professor.objects.for_user(self.coord_a)), [self.prof_a1])
        self.assertEqual(list(Professor.objects.for_user(self.coord_b)), [self.prof_b1])
        # Perfil ADMIN (TI) não é operacional: não enxerga a base pelo `for_user`.
        self.assertEqual(list(Professor.objects.for_user(self.admin_ti)), [])

    def test_coordenador_nao_deveria_mover_professor_para_outra_unidade(self):
        """
        CORRIGIDO: o coordenador não move mais um docente para outra unidade
        adulterando o campo escondido `unidade_principal`.

        Trocar só o widget para `HiddenInput` (apps/professors/forms.py) não
        protegia nada: o campo seguia vinculado e o valor do POST era aceito, e o
        `ProfessorUpdateView` não refaz o vínculo como o
        `ProfessorCreateView.form_valid` faz. Agora o campo também é
        `disabled=True` para o perfil de unidade — o Django ignora o POST e usa o
        valor da instância. O mesmo vale para `limite_horas_extra` (teto usado no
        parecer da DESUP via `limite_horas_extra_efetivo`).
        """
        self.client.force_login(self.coord_a)

        self.client.post(
            reverse('professors:professor_update', kwargs={'pk': self.prof_a1.pk}),
            self._dados_professor(
                id_funcional=self.prof_a1.id_funcional,
                rh_matricula=self.prof_a1.rh_matricula,
                rh_nome=self.prof_a1.rh_nome,
                unidade_principal=self.unidade_b.pk,
                limite_horas_extra='999',
                cursos=[],
            ),
        )

        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.unidade_principal, self.unidade_a)
        # O teto de horas extras também é da DESUP: o POST do coordenador é ignorado.
        self.assertIsNone(self.prof_a1.limite_horas_extra)


class HtmxProfessorE2ETests(ProfessorE2EBase):
    """Cenário 12: endpoints HTMX de apoio às telas."""

    def setUp(self):
        super().setUp()
        self.url_tabela = reverse('professors:htmx_tabela_alocacao')
        self.url_cursos = reverse('professors:htmx_cursos_unidade')

    def test_tabela_alocacao_exige_login(self):
        resposta = self.client.get(self.url_tabela)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_tabela_alocacao_do_coordenador_traz_so_a_unidade_dele(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_tabela)

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'professors/partials/_linhas_alocacao.html')
        self.assertContains(resposta, 'Ana Alves')
        self.assertNotContains(resposta, 'Carla Costa')
        self.assertEqual([p.pk for p in resposta.context['professores']], [self.prof_a1.pk])

    def test_tabela_alocacao_do_superuser_filtra_pelo_parametro_unidade(self):
        superuser = User.objects.create_superuser(
            email='root.prof@harpia.test', password='pw',
        )
        self.client.force_login(superuser)

        todos = self.client.get(self.url_tabela)
        self.assertCountEqual(
            [p.pk for p in todos.context['professores']], [self.prof_a1.pk, self.prof_b1.pk]
        )

        so_b = self.client.get(self.url_tabela, {'unidade': self.unidade_b.id})
        self.assertEqual([p.pk for p in so_b.context['professores']], [self.prof_b1.pk])

    def test_tabela_alocacao_mostra_as_horas_calculadas(self):
        matriz = self._matriz_vigente(self.curso_ads, self.unidade_a)
        self._componente(matriz, 'Algoritmos', 'ADS001', docente=self.prof_a1)
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_tabela)

        # ch_total = 40 (contrato), ch_alocada = 4 -> não alocado = 36.
        # O parcial imprime o valor cru (sem `floatformat`), e `ch_nao_alocada`
        # devolve float porque `ha_semanal` é float — daí o "36.0h".
        self.assertContains(resposta, '40h')
        self.assertContains(resposta, '36.0h')
        self.assertContains(resposta, '10.0%')

    def test_tabela_alocacao_da_desup_deveria_trazer_todas_as_unidades(self):
        """
        CORRIGIDO: `htmx_tabela_alocacao` reconhece o perfil DESUP.

        A view decidia o escopo só por grupo (`user.groups.filter(name='Admin
        DESUP')`) em vez de usar `perfil == 'DESUP'` como o resto do app (ex.:
        `ProfessorListView.get_context_data`). Um usuário DESUP sem grupo caía no
        ramo da unidade e o filtro virava `unidade_principal=None` (DESUP não tem
        unidade), devolvendo APENAS professores sem unidade. Agora as duas views
        usam o helper `_perfil_desup`.
        """
        sem_unidade = self._professor('Eva Esteves', 'SU', None)
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_tabela)

        self.assertCountEqual(
            [p.pk for p in resposta.context['professores']],
            [self.prof_a1.pk, self.prof_b1.pk, sem_unidade.pk],
        )

    def test_cursos_unidade_lista_apenas_cursos_ativos_da_unidade(self):
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_cursos, {'unidade_principal': self.unidade_a.id})

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'professors/partials/_cursos_checkboxes.html')
        self.assertEqual(list(resposta.context['cursos']), [self.curso_ads])
        self.assertContains(resposta, 'ADS')
        # Curso com vínculo inativo (CourseUnit.ativo=False) não entra.
        self.assertNotContains(resposta, 'Logistica')
        # Curso de outra unidade também não.
        self.assertNotContains(resposta, 'Enfermagem')

    def test_cursos_unidade_sem_parametro_devolve_lista_vazia(self):
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_cursos)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(list(resposta.context['cursos']), [])
        self.assertContains(resposta, 'Nenhum curso disponível')

    def test_cursos_unidade_exige_login(self):
        resposta = self.client.get(self.url_cursos, {'unidade_principal': self.unidade_a.id})

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class CalculosCargaHorariaProfessorE2ETests(ProfessorE2EBase):
    """Cenário 13: CH alocada, pendente e justificada com dados reais."""

    def setUp(self):
        super().setUp()
        self.matriz_manha = self._matriz_vigente(
            self.curso_ads, self.unidade_a, turno='M', nome='MC-ADS-M'
        )
        self.matriz_noite = self._matriz_vigente(
            self.curso_ads, self.unidade_a, turno='N', nome='MC-ADS-N'
        )
        # 80h/20 = 4 HA/sem ; 60h/20 = 3 HA/sem
        self.comp_manha = self._componente(
            self.matriz_manha, 'Algoritmos', 'ADS001', carga_horaria=80, docente=self.prof_a1
        )
        self.comp_noite = self._componente(
            self.matriz_noite, 'Banco de Dados', 'ADS002', carga_horaria=60, docente=self.prof_a1
        )

    def test_ch_alocada_soma_matrizes_vigentes_e_ignora_arquivadas(self):
        self.assertEqual(self.prof_a1.ch_alocada, 7)

        matriz_antiga = self._matriz_vigente(
            self.curso_ads, self.unidade_a, turno='T', nome='MC-ADS-2025'
        )
        matriz_antiga.is_vigente = False
        matriz_antiga.save()
        self._componente(
            matriz_antiga, 'Algoritmos Antigo', 'ADS001V', carga_horaria=80, docente=self.prof_a1
        )

        self.assertEqual(self.prof_a1.ch_alocada, 7)

    def test_componente_compartilhado_conta_uma_unica_vez(self):
        """Regra do `ch_alocada`: compartilhado é deduplicado pelo componente base."""
        componente_base = CurricularComponent.objects.create(
            nome='Ingles Instrumental', codigo='GER001', carga_horaria_padrao=40, creditos=2
        )
        for matriz in (self.matriz_manha, self.matriz_noite):
            MatrixComponent.objects.create(
                matriz=matriz,
                componente_curricular=componente_base,
                periodo='1o periodo',
                carga_horaria=40,
                creditos=2,
                carga_horaria_semanal=2,
                docente=self.prof_a1,
                compartilhado=True,
                curso_compartilhado=self.course_unit_enf_b,
                status=MatrixComponent.StatusChoices.COMPLETO,
            )

        # 4 + 3 + 2 (o compartilhado entra uma vez só, não duas)
        self.assertEqual(self.prof_a1.ch_alocada, 9)

    def test_ch_justificada_usa_apenas_pendencia_aprovada_do_semestre(self):
        self.assertEqual(self.prof_a1.ch_justificada, 0.0)

        pendencia = self._justificativa_aprovada(
            self.prof_a1, self.unidade_a, num_orientandos=4,
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        self.assertEqual(self.prof_a1.ch_justificada, 0.0)

        pendencia.status = PendenciaExtra.StatusChoices.APROVADO
        pendencia.save()
        # 4 orientandos x 0,5h = 2h
        self.assertEqual(self.prof_a1.ch_justificada, 2.0)

    def test_ch_pendente_e_limite_extra_efetivo_descontam_a_ch_alocada(self):
        """
        `ch_pendente` (apps/extra_curricular/services.py:168-170) e
        `limite_horas_extra_efetivo` usam a mesma conta: meta de sala do contrato
        menos a CH já alocada na matriz vigente.
        """
        from apps.extra_curricular.services import get_pendencias_data

        # meta = max_class_hours = 20 ; ch_alocada = 7 -> pendente = 13
        self.assertEqual(self.prof_a1.limite_horas_extra_efetivo, 13)

        linhas = get_pendencias_data(self.unidade_a.id, self.semestre_atual)
        linha = next(l for l in linhas if l['professor'].pk == self.prof_a1.pk)
        self.assertEqual(linha['meta_horas'], 20)
        self.assertEqual(linha['ch_alocada'], 7)
        self.assertEqual(linha['ch_pendente'], 13)
        self.assertEqual(linha['ch_faltante'], 13)

        # Com justificativa aprovada de 2h, faltam 11h para cobrir a pendência.
        self._justificativa_aprovada(self.prof_a1, self.unidade_a, num_orientandos=4)
        linhas = get_pendencias_data(self.unidade_a.id, self.semestre_atual)
        linha = next(l for l in linhas if l['professor'].pk == self.prof_a1.pk)
        self.assertEqual(linha['ch_justificada'], 2.0)
        self.assertEqual(linha['ch_faltante'], 11.0)

    def test_limite_manual_da_desup_prevalece_sobre_o_calculo(self):
        self.prof_a1.limite_horas_extra = 5
        self.prof_a1.save()

        self.assertEqual(self.prof_a1.limite_horas_extra_efetivo, 5.0)

    def test_ch_nao_alocada_e_percentual_consideram_alocada_mais_justificada(self):
        self._justificativa_aprovada(self.prof_a1, self.unidade_a, num_orientandos=4)

        # ch_total = 40 (max_total_hours) ; alocada 7 + justificada 2 = 9
        self.assertEqual(self.prof_a1.ch_total, 40)
        self.assertEqual(self.prof_a1.ch_nao_alocada, 31)
        self.assertEqual(self.prof_a1.percentual_alocado, 22.5)

    def test_listagem_mostra_colunas_por_matriz_e_soma_de_horas(self):
        self._justificativa_aprovada(self.prof_a1, self.unidade_a, num_orientandos=4)
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_lista)

        self.assertEqual(resposta.status_code, 200)
        colunas = {col['id']: col['nome'] for col in resposta.context['colunas_cursos']}
        self.assertEqual(
            colunas,
            {self.matriz_manha.id: 'ADS - Manhã', self.matriz_noite.id: 'ADS - Noite'},
        )

        professor = next(p for p in resposta.context['professores'] if p.pk == self.prof_a1.pk)
        self.assertEqual(
            professor.alocacao_map,
            {self.matriz_manha.id: 4.0, self.matriz_noite.id: 3.0},
        )
        # soma_horas = ch_alocada (7) + ch_justificada (2)
        self.assertEqual(professor.soma_horas, 9.0)
        self.assertContains(resposta, 'ADS - Manhã')

    def test_professor_sem_alocacao_aparece_zerado_na_listagem(self):
        prof_novo = self._professor('Fabio Freitas', 'A9', self.unidade_a)
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_lista)

        professor = next(p for p in resposta.context['professores'] if p.pk == prof_novo.pk)
        self.assertEqual(professor.alocacao_map, {})
        self.assertEqual(professor.soma_horas, 0)
        self.assertEqual(prof_novo.ch_alocada, 0)
        self.assertEqual(prof_novo.percentual_alocado, 0.0)
