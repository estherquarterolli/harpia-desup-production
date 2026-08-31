"""
Testes END-TO-END (E2E) do app `allocations` — Alocação Curricular.

Diferente de `apps/allocations/tests.py` (que cobre a regra de SEI/janela no
nível do model), aqui as jornadas passam pelas ROTAS reais registradas em
`config/urls.py`:

    alloc_curricular            -> /alocacao-curricular/
    alocar_docente_componente   -> /alocacao-curricular/componente/<pk>/alocar/
    liberar_alocacao            -> /alocacao-curricular/<pk>/liberar/
    aprovar_alocacao_unidade    -> /alocacao-curricular/unidade/<id>/aprovar/
    buscar_professores          -> /alocacao-curricular/buscar-professores/

Convenções destes testes:
- Usuários sempre com `forcar_troca_senha=False` (senão o
  `PasswordChangeForceMiddleware` redireciona tudo para a troca de senha).
- A janela de entrega precisa estar ABERTA para o perfil de unidade escrever;
  DESUP faz bypass (ver `apps.core.services`).
- Os testes com docstring "CORRIGIDO" nasceram como BUG-CANDIDATO
  (`@unittest.expectedFailure`): a asserção descreve o comportamento CORRETO,
  o bug foi corrigido e eles passaram a valer como teste de regressão.
"""

from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.allocations.models import AlocacaoCurricular
from apps.core.models import JanelaEntrega, Notificacao, Unidade
from apps.courses.models import (
    Course,
    CourseUnit,
    CurricularComponent,
    CurriculumMatrix,
    MatrixComponent,
)
from apps.professors.models import ContractType, Professor


class AlocacaoE2EBase(TestCase):
    """Cenário base: duas unidades, dois cursos, matriz vigente na unidade A."""

    def setUp(self):
        hoje = timezone.now().date()
        self.hoje = hoje
        self.semestre_atual = f"{hoje.year}.{'1' if hoje.month <= 6 else '2'}"

        # --- Unidades e cursos ---
        self.unidade_a = Unidade.objects.create(nome='Unidade Alfa', sigla='UA')
        self.unidade_b = Unidade.objects.create(nome='Unidade Beta', sigla='UB')

        self.curso_ads = Course.objects.create(nome='Analise e Desenvolvimento', sigla='ADS')
        self.curso_enf = Course.objects.create(nome='Enfermagem', sigla='ENF')

        self.course_unit_a = CourseUnit.objects.create(curso=self.curso_ads, unidade=self.unidade_a)
        self.course_unit_b = CourseUnit.objects.create(curso=self.curso_enf, unidade=self.unidade_b)

        # --- Contrato e docentes ---
        self.contrato = ContractType.objects.create(
            nome='Ensino Superior',
            regime_trabalho='40h DE',
            max_class_hours=20,
            max_total_hours=40,
            max_classes=4,
        )
        self.prof_a1 = self._professor('Ana Alves', 'A1', self.unidade_a)
        self.prof_a2 = self._professor('Bruno Barros', 'A2', self.unidade_a)
        self.prof_b1 = self._professor('Carla Costa', 'B1', self.unidade_b)

        # --- Matriz vigente publicada pela DESUP na unidade A ---
        self.matriz_a = CurriculumMatrix.objects.create(
            curso=self.curso_ads,
            nome='MC-ADS-2026',
            is_vigente=True,
            is_rascunho=False,
            turno='M',
            periodo_letivo=self.semestre_atual,
        )
        self.matriz_a.unidades.add(self.unidade_a)

        self.comp_algoritmos = self._componente(self.matriz_a, 'Algoritmos', 'ADS001')
        self.comp_banco = self._componente(self.matriz_a, 'Banco de Dados', 'ADS002')
        self.comp_redes = self._componente(self.matriz_a, 'Redes de Computadores', 'ADS003')

        # --- Matriz vigente da unidade B (usada nos testes de isolamento) ---
        self.matriz_b = CurriculumMatrix.objects.create(
            curso=self.curso_enf,
            nome='MC-ENF-2026',
            is_vigente=True,
            is_rascunho=False,
            turno='N',
            periodo_letivo=self.semestre_atual,
        )
        self.matriz_b.unidades.add(self.unidade_b)
        self.comp_anatomia = self._componente(self.matriz_b, 'Anatomia', 'ENF001')

        # --- Usuários ---
        self.desup = User.objects.create_user(
            email='desup.aloc@harpia.test', password='pw',
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.coord_a = User.objects.create_user(
            email='coord.a.aloc@harpia.test', password='pw',
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade_a, forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email='coord.b.aloc@harpia.test', password='pw',
            perfil='COORDENADOR_UNIDADE', unidade=self.unidade_b, forcar_troca_senha=False,
        )
        self.admin_ti = User.objects.create_user(
            email='ti.aloc@harpia.test', password='pw',
            perfil='ADMIN', forcar_troca_senha=False,
        )

        # --- Janela de entrega global aberta (unidade consegue escrever) ---
        self.janela = JanelaEntrega.objects.create(
            semestre=self.semestre_atual,
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje + timedelta(days=30),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )

        self.url_tela = reverse('alloc_curricular')

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

    def _componente(self, matriz, nome, codigo, carga_horaria=80, **kwargs):
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
            **kwargs,
        )

    def _url_alocar(self, componente):
        return reverse('alocar_docente_componente', kwargs={'pk': componente.pk})

    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def _fechar_janela_da_unidade(self, unidade):
        """Override explícito de fechamento (tem prioridade absoluta no service).

        O fechamento precisa estar VIGENTE (cobrir hoje) para valer como bloqueio:
        uma janela Fechado já expirada é histórico, não trava a unidade para sempre
        (ver `get_delivery_window`, apps/core/services.py).
        """
        JanelaEntrega.objects.create(
            semestre=self.semestre_atual,
            data_inicio=self.hoje - timedelta(days=10),
            data_fim=self.hoje + timedelta(days=10),
            status=JanelaEntrega.StatusChoices.FECHADO,
            unidade=unidade,
        )


class JornadaAlocacaoCurricularE2ETests(AlocacaoE2EBase):
    """Cenário 1: jornada completa da unidade sobre a matriz vigente."""

    def test_jornada_completa_coordenador_aloca_marca_sem_professor_e_nao_oferecida(self):
        self.client.force_login(self.coord_a)

        # 1) A unidade abre a tela e vê SOMENTE a matriz vigente da sua unidade.
        resposta = self.client.get(self.url_tela)
        self.assertEqual(resposta.status_code, 200)
        matrizes = [item['matriz'] for item in resposta.context['matrizes_data']]
        self.assertEqual(matrizes, [self.matriz_a])
        self.assertNotIn(self.matriz_b, matrizes)
        self.assertContains(resposta, 'Algoritmos')
        self.assertContains(resposta, 'Banco de Dados')
        # Nenhum componente alocado ainda: 3 sem docente.
        self.assertEqual(resposta.context['componentes_sem_docente'], 3)
        self.assertFalse(resposta.context['alocacao_curricular_preenchida'])
        # Os professores do select são apenas os da unidade da coordenação.
        self.assertEqual(
            list(resposta.context['professores_unidade']),
            [self.prof_a1, self.prof_a2],
        )

        # 2) Aloca um docente no primeiro componente.
        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['HX-Refresh'], 'true')

        self.comp_algoritmos.refresh_from_db()
        self.assertEqual(self.comp_algoritmos.docente, self.prof_a1)
        self.assertEqual(self.comp_algoritmos.status, MatrixComponent.StatusChoices.COMPLETO)

        # A CH alocada do docente sobe (80h semestrais / 20 semanas = 4 HA/sem).
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.ch_alocada, 4)
        self.assertIn('Algoritmos', self.prof_a1.get_disciplinas_alocadas())

        # 3) Marca outro componente como SEM PROFESSOR.
        resposta = self.client.post(
            self._url_alocar(self.comp_banco),
            {'docente_id': MatrixComponent.StatusChoices.SEM_PROFESSOR},
        )
        self.assertEqual(resposta.status_code, 200)
        self.comp_banco.refresh_from_db()
        self.assertIsNone(self.comp_banco.docente)
        self.assertEqual(self.comp_banco.status, MatrixComponent.StatusChoices.SEM_PROFESSOR)

        # 4) Marca o terceiro como NÃO OFERECIDA.
        resposta = self.client.post(
            self._url_alocar(self.comp_redes),
            {'docente_id': MatrixComponent.StatusChoices.NAO_OFERECIDA},
        )
        self.assertEqual(resposta.status_code, 200)
        self.comp_redes.refresh_from_db()
        self.assertIsNone(self.comp_redes.docente)
        self.assertEqual(self.comp_redes.status, MatrixComponent.StatusChoices.NAO_OFERECIDA)

        # 5) Confere os estados na tela: só o SEM_PROFESSOR conta como pendência
        #    (NÃO OFERECIDA é excluída da contagem).
        resposta = self.client.get(self.url_tela)
        self.assertEqual(resposta.context['componentes_sem_docente'], 1)
        self.assertFalse(resposta.context['alocacao_curricular_preenchida'])

        # 6) Fecha a lacuna: com todos resolvidos, a alocação fica "preenchida".
        self.client.post(
            self._url_alocar(self.comp_banco),
            {'docente_id': self.prof_a2.pk},
        )
        resposta = self.client.get(self.url_tela)
        self.assertEqual(resposta.context['componentes_sem_docente'], 0)
        self.assertTrue(resposta.context['alocacao_curricular_preenchida'])

        self.prof_a2.refresh_from_db()
        self.assertEqual(self.prof_a2.ch_alocada, 4)

    def test_post_sem_docente_id_cai_no_estado_sem_professor(self):
        """`docente_id` vazio equivale a marcar o componente como Sem professor."""
        self.client.force_login(self.coord_a)
        self.comp_algoritmos.docente = self.prof_a1
        self.comp_algoritmos.status = MatrixComponent.StatusChoices.COMPLETO
        self.comp_algoritmos.save()

        resposta = self.client.post(self._url_alocar(self.comp_algoritmos), {})

        self.assertEqual(resposta.status_code, 200)
        self.comp_algoritmos.refresh_from_db()
        self.assertIsNone(self.comp_algoritmos.docente)
        self.assertEqual(self.comp_algoritmos.status, MatrixComponent.StatusChoices.SEM_PROFESSOR)
        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.ch_alocada, 0)

    def test_desup_ve_todas_as_matrizes_vigentes_sem_filtro_de_unidade(self):
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_tela)

        self.assertEqual(resposta.status_code, 200)
        matrizes = [item['matriz'] for item in resposta.context['matrizes_data']]
        self.assertIn(self.matriz_a, matrizes)
        self.assertIn(self.matriz_b, matrizes)

    def test_matriz_nao_vigente_nao_aparece_na_tela(self):
        self.matriz_a.is_vigente = False
        self.matriz_a.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_tela)

        self.assertEqual(resposta.context['matrizes_data'], [])
        self.assertContains(resposta, 'Nenhuma Matriz Encontrada')


class LiberarAlocacaoE2ETests(AlocacaoE2EBase):
    """Cenário 2: DESUP libera/reabre a alocação consolidada de um curso."""

    def setUp(self):
        super().setUp()
        self.alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade_a,
            curso=self.course_unit_a,
            semestre=self.semestre_atual,
            turno='M',
            status=AlocacaoCurricular.StatusChoices.APROVADO,
            sei_numero='SEI-123456/123456/2026',
        )
        self.url_liberar = reverse('liberar_alocacao', kwargs={'pk': self.alocacao.pk})

    def test_desup_libera_alocacao_volta_para_rascunho_e_reabre_janela_expirada(self):
        # Janela específica da unidade, já expirada.
        janela_unidade = JanelaEntrega.objects.create(
            semestre=self.semestre_atual,
            data_inicio=self.hoje - timedelta(days=20),
            data_fim=self.hoje - timedelta(days=5),
            status=JanelaEntrega.StatusChoices.FECHADO,
            unidade=self.unidade_a,
        )
        self.client.force_login(self.desup)

        resposta = self.client.post(self.url_liberar)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], self.url_tela)

        self.alocacao.refresh_from_db()
        self.assertEqual(self.alocacao.status, AlocacaoCurricular.StatusChoices.RASCUNHO)

        janela_unidade.refresh_from_db()
        self.assertEqual(janela_unidade.status, JanelaEntrega.StatusChoices.REABERTO)
        self.assertGreaterEqual(janela_unidade.data_fim, self.hoje)
        self.assertTrue(janela_unidade.is_ativa)

        self.assertTrue(
            any('liberada' in m for m in self._mensagens(resposta)),
            self._mensagens(resposta),
        )

        # Efeito prático: a unidade volta a conseguir editar a alocação.
        self.client.force_login(self.coord_a)
        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )
        self.assertEqual(resposta.status_code, 200)
        self.comp_algoritmos.refresh_from_db()
        self.assertEqual(self.comp_algoritmos.docente, self.prof_a1)

    def test_liberar_nao_altera_os_componentes_ja_alocados(self):
        """Liberar mexe apenas no consolidado; os componentes seguem como estavam."""
        self.comp_algoritmos.docente = self.prof_a1
        self.comp_algoritmos.status = MatrixComponent.StatusChoices.COMPLETO
        self.comp_algoritmos.save()
        self.client.force_login(self.desup)

        self.client.post(self.url_liberar)

        self.comp_algoritmos.refresh_from_db()
        self.assertEqual(self.comp_algoritmos.docente, self.prof_a1)
        self.assertEqual(self.comp_algoritmos.status, MatrixComponent.StatusChoices.COMPLETO)

    def test_coordenador_de_unidade_nao_pode_liberar(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.post(self.url_liberar)

        self.assertEqual(resposta.status_code, 403)
        self.alocacao.refresh_from_db()
        self.assertEqual(self.alocacao.status, AlocacaoCurricular.StatusChoices.APROVADO)

    def test_anonimo_e_redirecionado_para_o_login(self):
        resposta = self.client.post(self.url_liberar)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class AprovarAlocacaoUnidadeE2ETests(AlocacaoE2EBase):
    """Cenário 3: aprovação da alocação curricular de uma unidade (DESUP)."""

    def setUp(self):
        super().setUp()
        self.url_aprovar = reverse(
            'aprovar_alocacao_unidade', kwargs={'unidade_id': self.unidade_a.id}
        )

    def _completar_alocacao_da_unidade_a(self):
        for componente, docente in (
            (self.comp_algoritmos, self.prof_a1),
            (self.comp_banco, self.prof_a2),
        ):
            componente.docente = docente
            componente.status = MatrixComponent.StatusChoices.COMPLETO
            componente.save()
        self.comp_redes.status = MatrixComponent.StatusChoices.NAO_OFERECIDA
        self.comp_redes.save()

    def test_desup_aprova_unidade_com_alocacao_completa(self):
        self._completar_alocacao_da_unidade_a()
        self.client.force_login(self.desup)

        resposta = self.client.post(self.url_aprovar)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], f'/alocacao-curricular/?unidade_id={self.unidade_a.id}')

        alocacao = AlocacaoCurricular.objects.get(unidade=self.unidade_a, curso=self.course_unit_a)
        self.assertEqual(alocacao.status, AlocacaoCurricular.StatusChoices.APROVADO)
        self.assertEqual(alocacao.semestre, self.semestre_atual)
        self.assertEqual(alocacao.turno, self.matriz_a.turno)
        self.assertTrue(
            any('aprovada' in m.lower() for m in self._mensagens(resposta)),
            self._mensagens(resposta),
        )

        # A aprovação de uma unidade não cria consolidado para a outra unidade.
        self.assertFalse(AlocacaoCurricular.objects.filter(unidade=self.unidade_b).exists())

    def test_desup_nao_aprova_com_componente_sem_docente(self):
        self.comp_algoritmos.docente = self.prof_a1
        self.comp_algoritmos.status = MatrixComponent.StatusChoices.COMPLETO
        self.comp_algoritmos.save()
        self.client.force_login(self.desup)

        resposta = self.client.post(self.url_aprovar)

        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(AlocacaoCurricular.objects.exists())
        mensagens = self._mensagens(resposta)
        self.assertTrue(any('sem docente' in m for m in mensagens), mensagens)
        # 2 pendências: Banco de Dados e Redes (nenhum marcado como não oferecido).
        self.assertTrue(any('2 componente' in m for m in mensagens), mensagens)

    def test_aprovar_e_idempotente_reaproveitando_o_consolidado(self):
        self._completar_alocacao_da_unidade_a()
        self.client.force_login(self.desup)

        self.client.post(self.url_aprovar)
        self.client.post(self.url_aprovar)

        self.assertEqual(
            AlocacaoCurricular.objects.filter(unidade=self.unidade_a).count(), 1
        )

    def test_coordenador_de_unidade_nao_pode_aprovar(self):
        self._completar_alocacao_da_unidade_a()
        self.client.force_login(self.coord_a)

        resposta = self.client.post(self.url_aprovar)

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(AlocacaoCurricular.objects.exists())

    def test_botao_aprovar_so_aparece_para_desup_com_unidade_selecionada(self):
        self._completar_alocacao_da_unidade_a()
        self.client.force_login(self.desup)

        resposta = self.client.get(self.url_tela, {'unidade_id': self.unidade_a.id})

        self.assertContains(resposta, self.url_aprovar)
        self.assertTrue(resposta.context['alocacao_curricular_preenchida'])

        # Coordenador de unidade não recebe o botão de aprovação.
        self.client.force_login(self.coord_a)
        resposta = self.client.get(self.url_tela)
        self.assertNotContains(resposta, self.url_aprovar)

    def test_aprovar_unidade_com_matriz_sem_turno_nao_deve_estourar(self):
        """
        CORRIGIDO: aprovar a unidade não estoura mais IntegrityError quando a
        matriz vigente não tem turno.

        `CurriculumMatrixForm` (apps/courses/forms.py) nem expõe o campo `turno`,
        então TODA matriz criada pela tela nasce com `turno=None`, e
        `AprovarAlocacaoUnidadeView` repassava esse None para
        `AlocacaoCurricular.turno`, que é NOT NULL (models.py:21) —
        IntegrityError/500 em vez de redirect. Agora a matriz sem turno cai no
        `TURNO_PADRAO_ALOCACAO` ('M') e a DESUP recebe um aviso para corrigir a
        matriz (a correção definitiva é o formulário de matriz exigir o turno).
        """
        self.matriz_a.turno = None
        self.matriz_a.save()
        self._completar_alocacao_da_unidade_a()
        self.client.force_login(self.desup)

        resposta = self.client.post(self.url_aprovar)

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(AlocacaoCurricular.objects.filter(unidade=self.unidade_a).exists())
        # O usuário é avisado de que o turno foi assumido, para poder ajustar a matriz.
        mensagens = self._mensagens(resposta)
        self.assertTrue(any('sem turno' in m for m in mensagens), mensagens)


class BuscarProfessoresE2ETests(AlocacaoE2EBase):
    """Cenário 4: endpoint JSON de busca de docentes (autocomplete)."""

    def setUp(self):
        super().setUp()
        self.url_busca = reverse('buscar_professores')

    def test_exige_login(self):
        resposta = self.client.get(self.url_busca)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_coordenador_recebe_json_apenas_da_propria_unidade(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_busca)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/json')
        nomes = [item['nome'] for item in resposta.json()['results']]
        self.assertEqual(nomes, ['Ana Alves', 'Bruno Barros'])
        self.assertNotIn('Carla Costa', nomes)
        self.assertEqual(
            {item['unidade'] for item in resposta.json()['results']}, {'UA'}
        )

    def test_coordenador_nao_consegue_espiar_outra_unidade_via_parametro(self):
        """`unidade_id` é ignorado para o perfil de unidade (isolamento server-side)."""
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_busca, {'unidade_id': self.unidade_b.id})

        nomes = [item['nome'] for item in resposta.json()['results']]
        self.assertEqual(nomes, ['Ana Alves', 'Bruno Barros'])

    def test_desup_busca_global_e_filtra_por_unidade(self):
        self.client.force_login(self.desup)

        todos = self.client.get(self.url_busca).json()['results']
        self.assertEqual(
            [item['nome'] for item in todos],
            ['Ana Alves', 'Bruno Barros', 'Carla Costa'],
        )

        so_b = self.client.get(self.url_busca, {'unidade_id': self.unidade_b.id}).json()['results']
        self.assertEqual([item['nome'] for item in so_b], ['Carla Costa'])

    def test_busca_por_termo_e_ignora_afastados(self):
        self.prof_a2.status = Professor.StatusChoices.AFASTADO
        self.prof_a2.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_busca, {'q': 'ana'})

        nomes = [item['nome'] for item in resposta.json()['results']]
        self.assertEqual(nomes, ['Ana Alves'])

        # O afastado some da busca mesmo sem termo.
        nomes = [item['nome'] for item in self.client.get(self.url_busca).json()['results']]
        self.assertEqual(nomes, ['Ana Alves'])

    def test_coordenador_sem_unidade_recebe_lista_vazia(self):
        self.coord_a.unidade = None
        self.coord_a.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_busca)

        self.assertEqual(resposta.json(), {'results': []})

    def test_busca_deveria_respeitar_o_nome_ajustado_pela_desup(self):
        """
        CORRIGIDO: `BuscarProfessoresView` respeita o override da DESUP.

        A Regra #3 diz que `desup_nome` prevalece sobre `rh_nome`
        (`Professor.nome`, apps/professors/models.py:152-154), mas o endpoint
        devolvia `p.rh_nome` e filtrava só por `rh_nome__icontains` — o
        autocomplete da tela de alocação mostrava e buscava o nome antigo do RH.
        Agora a busca casa com os dois nomes e a resposta devolve `p.nome`.
        """
        self.prof_a1.desup_nome = 'Ana Alves Ajustada'
        self.prof_a1.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_busca, {'q': 'Ajustada'})

        nomes = [item['nome'] for item in resposta.json()['results']]
        self.assertEqual(nomes, ['Ana Alves Ajustada'])


class JanelaEntregaAlocacaoE2ETests(AlocacaoE2EBase):
    """Cenário 5: janela fechada bloqueia a unidade; DESUP faz bypass."""

    def setUp(self):
        super().setUp()
        # Sem janela ativa nenhuma: o padrão do sistema é "fechado".
        JanelaEntrega.objects.all().delete()

    def test_unidade_bloqueada_ao_tentar_alocar_com_janela_fechada(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
            HTTP_REFERER=self.url_tela,
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], self.url_tela)

        self.comp_algoritmos.refresh_from_db()
        self.assertIsNone(self.comp_algoritmos.docente)
        self.assertEqual(self.comp_algoritmos.status, MatrixComponent.StatusChoices.SEM_PROFESSOR)

        # A tentativa vira notificação para a DESUP.
        self.assertTrue(
            Notificacao.objects.filter(titulo__icontains='Tentativa bloqueada').exists()
        )
        mensagens = self._mensagens(resposta)
        self.assertTrue(any('Janela de entrega fechada' in m for m in mensagens), mensagens)

    def test_override_fechado_da_unidade_bloqueia_mesmo_com_janela_global_aberta(self):
        JanelaEntrega.objects.create(
            semestre=self.semestre_atual,
            data_inicio=self.hoje - timedelta(days=1),
            data_fim=self.hoje + timedelta(days=10),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        self._fechar_janela_da_unidade(self.unidade_a)
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
            HTTP_REFERER=self.url_tela,
        )

        self.assertEqual(resposta.status_code, 302)
        self.comp_algoritmos.refresh_from_db()
        self.assertIsNone(self.comp_algoritmos.docente)

    def test_desup_faz_bypass_da_janela_fechada(self):
        self.client.force_login(self.desup)

        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['HX-Refresh'], 'true')
        self.comp_algoritmos.refresh_from_db()
        self.assertEqual(self.comp_algoritmos.docente, self.prof_a1)
        self.assertFalse(
            Notificacao.objects.filter(titulo__icontains='Tentativa bloqueada').exists()
        )

    def test_tela_sinaliza_janela_fechada_para_a_unidade_e_aberta_para_a_desup(self):
        self.client.force_login(self.coord_a)
        resposta = self.client.get(self.url_tela)
        self.assertTrue(resposta.context['window_fechada'])
        self.assertEqual(resposta.context['window_area_label'], 'Alocação')

        self.client.force_login(self.desup)
        resposta = self.client.get(self.url_tela, {'unidade_id': self.unidade_a.id})
        self.assertFalse(resposta.context['window_fechada'])


class IsolamentoUnidadeAlocacaoE2ETests(AlocacaoE2EBase):
    """Cenário 6: a unidade A não alcança dados da unidade B."""

    def test_coordenador_a_nao_aloca_em_componente_de_matriz_da_unidade_b(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            self._url_alocar(self.comp_anatomia),
            {'docente_id': self.prof_a1.pk},
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertIn('outra unidade', resposta.content.decode())
        self.comp_anatomia.refresh_from_db()
        self.assertIsNone(self.comp_anatomia.docente)

    def test_coordenador_a_nao_aloca_docente_de_outra_unidade_no_proprio_componente(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_b1.pk},
        )

        self.assertEqual(resposta.status_code, 403)
        self.comp_algoritmos.refresh_from_db()
        self.assertIsNone(self.comp_algoritmos.docente)

    def test_coordenador_sem_unidade_nao_ve_nem_altera_nada(self):
        self.coord_a.unidade = None
        self.coord_a.save()
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_tela)
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('matrizes_data', resposta.context)

        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )
        self.assertEqual(resposta.status_code, 403)

    def test_desup_pode_alocar_em_qualquer_unidade(self):
        self.client.force_login(self.desup)

        resposta = self.client.post(
            self._url_alocar(self.comp_anatomia),
            {'docente_id': self.prof_b1.pk},
        )

        self.assertEqual(resposta.status_code, 200)
        self.comp_anatomia.refresh_from_db()
        self.assertEqual(self.comp_anatomia.docente, self.prof_b1)


class PerfisAcessoAlocacaoE2ETests(AlocacaoE2EBase):
    """Cenário 7: quem entra na tela de alocação."""

    def test_coordenador_e_desup_acessam_a_tela(self):
        for usuario in (self.coord_a, self.desup):
            with self.subTest(perfil=usuario.perfil):
                self.client.force_login(usuario)
                resposta = self.client.get(self.url_tela)
                self.assertEqual(resposta.status_code, 200)
                self.assertTemplateUsed(resposta, 'allocations/alloc_curricular.html')

    def test_perfil_admin_ti_e_redirecionado_para_o_admin_do_django(self):
        self.client.force_login(self.admin_ti)

        resposta = self.client.get(self.url_tela)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], '/admin/')

    def test_perfil_admin_ti_nao_consegue_alocar(self):
        self.client.force_login(self.admin_ti)

        resposta = self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta['Location'], '/admin/')
        self.comp_algoritmos.refresh_from_db()
        self.assertIsNone(self.comp_algoritmos.docente)

    def test_perfil_admin_ti_via_htmx_recebe_hx_redirect(self):
        self.client.force_login(self.admin_ti)

        resposta = self.client.get(self.url_tela, HTTP_HX_REQUEST='true')

        self.assertEqual(resposta.status_code, 204)
        self.assertEqual(resposta['HX-Redirect'], '/admin/')

    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get(self.url_tela)

        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])


class MultiplasMatrizesVigentesE2ETests(AlocacaoE2EBase):
    """Cenário 8 (CORR-011): duas matrizes vigentes do mesmo curso coexistem."""

    def setUp(self):
        super().setUp()
        self.matriz_a_noite = CurriculumMatrix.objects.create(
            curso=self.curso_ads,
            nome='MC-ADS-2026-N',
            is_vigente=True,
            is_rascunho=False,
            turno='N',
            periodo_letivo=self.semestre_atual,
        )
        self.matriz_a_noite.unidades.add(self.unidade_a)
        self.comp_algoritmos_noite = self._componente(
            self.matriz_a_noite, 'Algoritmos Noturno', 'ADS001N', carga_horaria=60
        )

    def test_tela_lista_as_duas_matrizes_vigentes_do_mesmo_curso(self):
        self.client.force_login(self.coord_a)

        resposta = self.client.get(self.url_tela)

        matrizes = [item['matriz'] for item in resposta.context['matrizes_data']]
        self.assertCountEqual(matrizes, [self.matriz_a, self.matriz_a_noite])
        # 3 componentes da matriz da manhã + 1 da noite.
        self.assertEqual(resposta.context['componentes_sem_docente'], 4)

    def test_ch_alocada_soma_as_duas_matrizes_vigentes(self):
        self.client.force_login(self.coord_a)

        self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )
        self.client.post(
            self._url_alocar(self.comp_algoritmos_noite),
            {'docente_id': self.prof_a1.pk},
        )

        self.prof_a1.refresh_from_db()
        # 80h/20 = 4 HA + 60h/20 = 3 HA
        self.assertEqual(self.prof_a1.ch_alocada, 7)
        self.assertCountEqual(
            self.prof_a1.get_disciplinas_alocadas(),
            ['Algoritmos', 'Algoritmos Noturno'],
        )

    def test_matriz_arquivada_deixa_de_somar_ch_alocada(self):
        self.client.force_login(self.coord_a)
        self.client.post(
            self._url_alocar(self.comp_algoritmos),
            {'docente_id': self.prof_a1.pk},
        )
        self.client.post(
            self._url_alocar(self.comp_algoritmos_noite),
            {'docente_id': self.prof_a1.pk},
        )

        # CORR-012: arquivamento manual de uma das matrizes.
        self.matriz_a_noite.is_vigente = False
        self.matriz_a_noite.save()

        self.prof_a1.refresh_from_db()
        self.assertEqual(self.prof_a1.ch_alocada, 4)

    def test_aprovacao_cria_um_consolidado_por_turno(self):
        for componente, docente in (
            (self.comp_algoritmos, self.prof_a1),
            (self.comp_banco, self.prof_a2),
            (self.comp_algoritmos_noite, self.prof_a1),
        ):
            componente.docente = docente
            componente.status = MatrixComponent.StatusChoices.COMPLETO
            componente.save()
        self.comp_redes.status = MatrixComponent.StatusChoices.NAO_OFERECIDA
        self.comp_redes.save()

        self.client.force_login(self.desup)
        resposta = self.client.post(
            reverse('aprovar_alocacao_unidade', kwargs={'unidade_id': self.unidade_a.id})
        )

        self.assertEqual(resposta.status_code, 302)
        turnos = set(
            AlocacaoCurricular.objects.filter(unidade=self.unidade_a).values_list('turno', flat=True)
        )
        self.assertEqual(turnos, {'M', 'N'})
