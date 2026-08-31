"""
Testes END-TO-END do app `core`.

Diferente de `apps/core/tests.py` — que valida unidades isoladas (forms, services,
managers) — aqui o foco são **jornadas completas** percorridas pelo cliente HTTP,
do jeito que a DESUP e o Coordenador de Unidade usam o sistema: navegar até a
lista, abrir o formulário, salvar, conferir o resultado na tela seguinte e
verificar os efeitos colaterais (notificação, auditoria, bloqueio de janela).

Perfis (`User.Perfil`):
    ADMIN                -> TI/DEV, só opera o admin do Django (CORR-021).
    DESUP                -> Coordenação DESUP, bypassa a janela de entrega.
    COORDENADOR_UNIDADE  -> opera apenas a própria unidade e respeita a janela.
"""

import unittest

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    AtalhoDashboard,
    AuditoriaGlobal,
    JanelaEntrega,
    Notificacao,
    Unidade,
)
from apps.courses.models import (
    Course,
    CourseUnit,
    CurricularComponent,
    CurriculumMatrix,
    MatrixComponent,
)
from apps.professors.models import ContractType, Professor

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# Infraestrutura compartilhada
# ══════════════════════════════════════════════════════════════════════════════

class BaseE2ETestCase(TestCase):
    """Helpers usados por todas as jornadas."""

    @staticmethod
    def criar_desup(email, **extra):
        return User.objects.create_user(
            email=email, password='pw', perfil='DESUP',
            forcar_troca_senha=False, **extra,
        )

    @staticmethod
    def criar_coordenador(email, unidade=None, **extra):
        return User.objects.create_user(
            email=email, password='pw', perfil='COORDENADOR_UNIDADE',
            unidade=unidade, forcar_troca_senha=False, **extra,
        )

    @staticmethod
    def criar_admin_ti(email, **extra):
        return User.objects.create_user(
            email=email, password='pw', perfil='ADMIN',
            forcar_troca_senha=False, **extra,
        )

    @staticmethod
    def criar_janela(status=JanelaEntrega.StatusChoices.ABERTO, unidade=None,
                     dias_inicio=0, dias_fim=15, semestre='2026.1'):
        hoje = timezone.now().date()
        return JanelaEntrega.objects.create(
            semestre=semestre,
            data_inicio=hoje + timezone.timedelta(days=dias_inicio),
            data_fim=hoje + timezone.timedelta(days=dias_fim),
            status=status,
            unidade=unidade,
        )

    @staticmethod
    def mensagens(response):
        """Textos das mensagens (django.contrib.messages) da resposta."""
        return [str(m) for m in get_messages(response.wsgi_request)]


class AlocacaoFixtureMixin:
    """
    Monta o mínimo necessário para exercitar a rota real que o coordenador usa
    e que é protegida pela janela de entrega: alocar um docente num componente
    da matriz vigente da sua unidade.
    """

    def montar_alocacao(self, unidade, sufixo='A'):
        contrato = ContractType.objects.create(
            nome=f'Contrato {sufixo}', max_class_hours=20,
            max_total_hours=40, max_classes=4,
        )
        professor = Professor.objects.create(
            id_funcional=f'IDF-{sufixo}',
            rh_matricula=f'MAT-{sufixo}',
            rh_nome=f'Professor {sufixo}',
            rh_email=f'prof_{sufixo.lower()}@teste.com',
            unidade_principal=unidade,
            tipo_contrato=contrato,
            ha=20,
        )
        curso = Course.objects.create(
            nome=f'Curso E2E {sufixo}', sigla=f'CE{sufixo}',
        )
        CourseUnit.objects.create(curso=curso, unidade=unidade)
        componente = CurricularComponent.objects.create(
            nome=f'Componente E2E {sufixo}',
            codigo=f'COMP{sufixo}',
            carga_horaria_padrao=80,
        )
        matriz = CurriculumMatrix.objects.create(
            curso=curso, nome=f'MC-{sufixo}', is_vigente=True,
            periodo_letivo='2026.1', turno='M',
        )
        matriz.unidades.add(unidade)
        matrix_component = MatrixComponent.objects.create(
            matriz=matriz, componente_curricular=componente,
            codigo=f'MC-{sufixo}-01', periodo='1o periodo', carga_horaria=80,
        )
        return {
            'contrato': contrato,
            'professor': professor,
            'curso': curso,
            'componente': componente,
            'matriz': matriz,
            'matrix_component': matrix_component,
        }

    def alocar(self, matrix_component, professor):
        """POST na rota real de alocação (protegida pela janela)."""
        return self.client.post(
            reverse('alocar_docente_componente', kwargs={'pk': matrix_component.pk}),
            {'docente_id': professor.pk},
        )


# ══════════════════════════════════════════════════════════════════════════════
# 1) CRUD completo de Unidade
# ══════════════════════════════════════════════════════════════════════════════

class JornadaCrudUnidadeTests(BaseE2ETestCase):
    """DESUP: listar -> criar -> editar -> conferir. Unidade: 403 em tudo."""

    def setUp(self):
        self.desup = self.criar_desup('e2e_unid_desup@teste.com')
        self.unidade_coord = Unidade.objects.create(nome='Unidade do Coord', sigla='UDC')
        self.coord = self.criar_coordenador('e2e_unid_coord@teste.com', unidade=self.unidade_coord)
        self.url_list = reverse('core:unidade_list')
        self.url_create = reverse('core:unidade_create')

    def test_jornada_desup_lista_cria_edita_e_confere_na_lista(self):
        self.client.force_login(self.desup)

        # 1) Lista inicial — a unidade nova ainda não existe.
        resp = self.client.get(self.url_list)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Centro Norte')

        # 2) Formulário de criação abre.
        resp = self.client.get(self.url_create)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)

        # 3) Cria a unidade.
        resp = self.client.post(self.url_create, {
            'nome': 'Centro Norte', 'sigla': 'CN', 'status': 'on',
        })
        self.assertRedirects(resp, self.url_list)
        unidade = Unidade.objects.get(nome='Centro Norte')
        self.assertEqual(unidade.sigla, 'CN')
        self.assertTrue(unidade.status)

        # 4) Ela aparece na lista.
        resp = self.client.get(self.url_list)
        self.assertContains(resp, 'Centro Norte')
        self.assertIn(unidade, list(resp.context['unidades']))

        # 5) Formulário de edição vem preenchido com os dados atuais.
        url_edit = reverse('core:unidade_update', kwargs={'pk': unidade.pk})
        resp = self.client.get(url_edit)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['form'].initial['sigla'], 'CN')

        # 6) Edita: renomeia e inativa (checkbox ausente == False).
        resp = self.client.post(url_edit, {'nome': 'Polo Norte Reformado', 'sigla': 'PNR'})
        self.assertRedirects(resp, self.url_list)
        unidade.refresh_from_db()
        self.assertEqual(unidade.nome, 'Polo Norte Reformado')
        self.assertEqual(unidade.sigla, 'PNR')
        self.assertFalse(unidade.status)

        # 7) Confere o resultado na lista.
        resp = self.client.get(self.url_list)
        self.assertContains(resp, 'Polo Norte Reformado')
        self.assertContains(resp, 'Inativo')
        self.assertEqual(Unidade.objects.filter(nome='Centro Norte').count(), 0)

    def test_nome_duplicado_e_rejeitado_e_nao_cria_segunda_unidade(self):
        self.client.force_login(self.desup)
        self.client.post(self.url_create, {'nome': 'Unidade Única', 'sigla': 'UU', 'status': 'on'})

        resp = self.client.post(self.url_create, {'nome': 'Unidade Única', 'sigla': 'XX', 'status': 'on'})

        self.assertEqual(resp.status_code, 200)  # volta ao form com erro
        self.assertIn('nome', resp.context['form'].errors)
        self.assertEqual(Unidade.objects.filter(nome='Unidade Única').count(), 1)

    def test_coordenador_de_unidade_nao_cria_nem_edita_unidade(self):
        self.client.force_login(self.coord)

        self.assertEqual(self.client.get(self.url_list).status_code, 403)
        self.assertEqual(self.client.get(self.url_create).status_code, 403)

        resp = self.client.post(self.url_create, {'nome': 'Invadida', 'sigla': 'INV', 'status': 'on'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Unidade.objects.filter(nome='Invadida').exists())

        url_edit = reverse('core:unidade_update', kwargs={'pk': self.unidade_coord.pk})
        self.assertEqual(self.client.get(url_edit).status_code, 403)
        resp = self.client.post(url_edit, {'nome': 'Renomeada', 'sigla': 'REN'})
        self.assertEqual(resp.status_code, 403)
        self.unidade_coord.refresh_from_db()
        self.assertEqual(self.unidade_coord.nome, 'Unidade do Coord')

    def test_anonimo_e_mandado_para_o_login(self):
        resp = self.client.get(self.url_list)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])


# ══════════════════════════════════════════════════════════════════════════════
# 2) CRUD completo de Curso dentro de uma Unidade
# ══════════════════════════════════════════════════════════════════════════════

class JornadaCrudCursoTests(BaseE2ETestCase):
    """DESUP: criar -> editar -> excluir curso da unidade + isolamento entre unidades."""

    def setUp(self):
        self.desup = self.criar_desup('e2e_curso_desup@teste.com')
        self.unidade_a = Unidade.objects.create(nome='Unidade Alfa', sigla='UAL')
        self.unidade_b = Unidade.objects.create(nome='Unidade Beta', sigla='UBE')
        self.coord_a = self.criar_coordenador('e2e_curso_coord_a@teste.com', unidade=self.unidade_a)

    def _url(self, nome, **kwargs):
        return reverse(f'core:{nome}', kwargs=kwargs)

    def test_jornada_desup_cria_edita_e_exclui_curso_da_unidade(self):
        self.client.force_login(self.desup)
        url_list = self._url('curso_list', unidade_pk=self.unidade_a.pk)

        # 1) Lista vazia da unidade.
        resp = self.client.get(url_list)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['cursos']), [])
        self.assertEqual(resp.context['unidade'], self.unidade_a)

        # 2) Cria o curso pela unidade.
        resp = self.client.post(
            self._url('curso_create', unidade_pk=self.unidade_a.pk),
            {'nome': 'Técnico em Informática', 'sigla': 'INFO'},
        )
        self.assertRedirects(resp, url_list)
        curso = Course.objects.get(sigla='INFO')
        vinculo = CourseUnit.objects.get(curso=curso, unidade=self.unidade_a)

        # 3) Aparece na lista da unidade — e só nela.
        resp = self.client.get(url_list)
        self.assertContains(resp, 'Técnico em Informática')
        self.assertEqual([cu.pk for cu in resp.context['cursos']], [vinculo.pk])
        resp_b = self.client.get(self._url('curso_list', unidade_pk=self.unidade_b.pk))
        self.assertEqual(list(resp_b.context['cursos']), [])

        # 4) Edita o curso a partir da unidade.
        url_edit = self._url('curso_update', unidade_pk=self.unidade_a.pk, pk=vinculo.pk)
        resp = self.client.get(url_edit)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['form'].initial['sigla'], 'INFO')

        resp = self.client.post(url_edit, {'nome': 'Técnico em Informática Integrado', 'sigla': 'INFOI'})
        self.assertRedirects(resp, url_list)
        curso.refresh_from_db()
        self.assertEqual(curso.nome, 'Técnico em Informática Integrado')
        self.assertEqual(curso.sigla, 'INFOI')
        self.assertContains(self.client.get(url_list), 'Técnico em Informática Integrado')

        # 5) Exclui o vínculo curso/unidade.
        url_delete = self._url('curso_delete', unidade_pk=self.unidade_a.pk, pk=vinculo.pk)
        resp = self.client.get(url_delete)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'INFOI')

        resp = self.client.post(url_delete)
        self.assertRedirects(resp, url_list)
        self.assertFalse(CourseUnit.objects.filter(pk=vinculo.pk).exists())
        # O Course é compartilhado entre unidades: some da unidade, não do catálogo.
        self.assertTrue(Course.objects.filter(pk=curso.pk).exists())

        # 6) Lista da unidade voltou a ficar vazia.
        self.assertEqual(list(self.client.get(url_list).context['cursos']), [])

    def test_coordenador_de_unidade_nao_gerencia_cursos(self):
        """CRUD de curso é DESUP-only — nem na própria unidade o coordenador entra."""
        curso = Course.objects.create(nome='Curso Existente', sigla='CEX')
        vinculo = CourseUnit.objects.create(curso=curso, unidade=self.unidade_a)
        self.client.force_login(self.coord_a)

        alvos = [
            self._url('curso_list', unidade_pk=self.unidade_a.pk),
            self._url('curso_create', unidade_pk=self.unidade_a.pk),
            self._url('curso_update', unidade_pk=self.unidade_a.pk, pk=vinculo.pk),
            self._url('curso_delete', unidade_pk=self.unidade_a.pk, pk=vinculo.pk),
        ]
        for url in alvos:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

        resp = self.client.post(self._url('curso_create', unidade_pk=self.unidade_a.pk),
                                {'nome': 'Curso Pirata', 'sigla': 'PIR'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Course.objects.filter(sigla='PIR').exists())

    def test_coordenador_da_unidade_a_nao_mexe_em_curso_da_unidade_b(self):
        """Isolamento entre unidades: nem leitura, nem exclusão do curso da outra unidade."""
        curso_b = Course.objects.create(nome='Curso da Beta', sigla='CBE')
        vinculo_b = CourseUnit.objects.create(curso=curso_b, unidade=self.unidade_b)
        self.client.force_login(self.coord_a)

        resp = self.client.get(self._url('curso_list', unidade_pk=self.unidade_b.pk))
        self.assertEqual(resp.status_code, 403)

        resp = self.client.post(
            self._url('curso_delete', unidade_pk=self.unidade_b.pk, pk=vinculo_b.pk)
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(CourseUnit.objects.filter(pk=vinculo_b.pk).exists())

        resp = self.client.post(
            self._url('curso_update', unidade_pk=self.unidade_b.pk, pk=vinculo_b.pk),
            {'nome': 'Sequestrado', 'sigla': 'SEQ'},
        )
        self.assertEqual(resp.status_code, 403)
        curso_b.refresh_from_db()
        self.assertEqual(curso_b.nome, 'Curso da Beta')

    def test_excluir_curso_pela_url_de_outra_unidade_da_404(self):
        """A exclusão é filtrada por `unidade_pk` — vínculo de outra unidade não some."""
        curso_b = Course.objects.create(nome='Curso Só da Beta', sigla='CSB')
        vinculo_b = CourseUnit.objects.create(curso=curso_b, unidade=self.unidade_b)
        self.client.force_login(self.desup)

        resp = self.client.post(
            self._url('curso_delete', unidade_pk=self.unidade_a.pk, pk=vinculo_b.pk)
        )

        self.assertEqual(resp.status_code, 404)
        self.assertTrue(CourseUnit.objects.filter(pk=vinculo_b.pk).exists())

    def test_editar_curso_pela_url_de_outra_unidade_deveria_dar_404(self):
        """
        CORRIGIDO (CORR-029): `CursoUpdateView.get_object` (apps/core/views.py:262-263) resolve
        o `CourseUnit` **sem** filtrar por `unidade_pk`, ao contrário de
        `CursoDeleteView.get_queryset` (apps/core/views.py:277-278), que filtra. Assim a
        edição feita a partir da URL de uma unidade altera o curso de OUTRA unidade e
        depois redireciona para a lista da unidade da URL — onde a alteração nem
        aparece, porque o curso não pertence a ela.

        Repro:
            1. Unidade Beta tem o curso "Curso Só da Beta" (vínculo CourseUnit #N).
            2. DESUP acessa /core/unidades/<pk_da_Alfa>/cursos/<N>/edit/ e salva.
            3. O curso da Beta é renomeado (esperado: 404, como no delete).
        """
        curso_b = Course.objects.create(nome='Curso Só da Beta', sigla='CSB')
        vinculo_b = CourseUnit.objects.create(curso=curso_b, unidade=self.unidade_b)
        self.client.force_login(self.desup)

        resp = self.client.post(
            self._url('curso_update', unidade_pk=self.unidade_a.pk, pk=vinculo_b.pk),
            {'nome': 'Renomeado pela Alfa', 'sigla': 'RPA'},
        )

        curso_b.refresh_from_db()
        self.assertEqual(curso_b.nome, 'Curso Só da Beta')  # vaza: vira "Renomeado pela Alfa"
        self.assertEqual(resp.status_code, 404)

    def test_oferecer_curso_existente_em_uma_segunda_unidade(self):
        """
        CORRIGIDO (CORR-029): não havia como oferecer um curso já cadastrado em uma segunda
        unidade pela tela de cadastro.

        `CursoCreateView.form_valid` (apps/core/views.py:241-250) tem o caminho de
        reaproveitamento (`Course.objects.filter(sigla=...).first()` -> `CourseUnit
        .get_or_create`), mas ele é **inalcançável**: o ModelForm de `Course` valida
        `nome`/`sigla` (ambos `unique=True`) antes, então o POST volta 200 com o erro
        "Curso com este Sigla já existe" e nenhum vínculo novo é criado.

        Repro:
            1. DESUP cadastra "Técnico em Redes"/"REDES" na Unidade Alfa.
            2. DESUP abre /core/unidades/<pk_da_Beta>/cursos/add/ e envia os mesmos
               nome e sigla (é o mesmo curso, agora ofertado na Beta).
            3. Esperado: vínculo CourseUnit(REDES, Beta) criado e redirect para a
               lista da Beta. Obtido: 200 com erro de unicidade e nenhum vínculo.
        """
        self.client.force_login(self.desup)
        self.client.post(
            self._url('curso_create', unidade_pk=self.unidade_a.pk),
            {'nome': 'Técnico em Redes', 'sigla': 'REDES'},
        )
        curso = Course.objects.get(sigla='REDES')

        resp = self.client.post(
            self._url('curso_create', unidade_pk=self.unidade_b.pk),
            {'nome': 'Técnico em Redes', 'sigla': 'REDES'},
        )

        self.assertRedirects(resp, self._url('curso_list', unidade_pk=self.unidade_b.pk))
        self.assertTrue(CourseUnit.objects.filter(curso=curso, unidade=self.unidade_b).exists())


# ══════════════════════════════════════════════════════════════════════════════
# 3) Ciclo de vida da Janela de Entrega
# ══════════════════════════════════════════════════════════════════════════════

class JornadaCicloDeVidaJanelaTests(AlocacaoFixtureMixin, BaseE2ETestCase):
    """DESUP abre -> coordenador opera -> DESUP fecha -> coordenador é bloqueado."""

    def setUp(self):
        self.hoje = timezone.now().date()
        self.desup = self.criar_desup('e2e_janela_desup@teste.com')
        self.unidade = Unidade.objects.create(nome='Unidade Janela', sigla='UJA')
        self.coord = self.criar_coordenador('e2e_janela_coord@teste.com', unidade=self.unidade)
        self.fixture = self.montar_alocacao(self.unidade, sufixo='JAN')

    def test_ciclo_completo_abre_opera_fecha_e_bloqueia(self):
        # ── DESUP cria a janela pela tela ─────────────────────────────────────
        self.client.force_login(self.desup)
        resp = self.client.get(reverse('core:janela_create'))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse('core:janela_create'), {
            'semestre': '2026.1',
            'data_inicio': self.hoje,
            'data_fim': self.hoje + timezone.timedelta(days=10),
            'status': JanelaEntrega.StatusChoices.ABERTO,
            'unidade': '',
        })
        self.assertRedirects(resp, reverse('core:janela_list'))
        janela = JanelaEntrega.objects.get(semestre='2026.1')
        self.assertEqual(janela.status, JanelaEntrega.StatusChoices.ABERTO)
        self.assertIsNone(janela.unidade)  # global
        self.assertTrue(janela.is_ativa)

        # A janela aparece na listagem da DESUP.
        resp = self.client.get(reverse('core:janela_list'))
        self.assertIn(janela, list(resp.context['janelas']))

        # ── Coordenador consegue operar com a janela aberta ───────────────────
        self.client.force_login(self.coord)
        resp = self.client.get('/alocacao-curricular/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['window_fechada'])
        self.assertNotContains(resp, 'windowClosedNotice')

        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['HX-Refresh'], 'true')
        self.fixture['matrix_component'].refresh_from_db()
        self.assertEqual(self.fixture['matrix_component'].docente, self.fixture['professor'])
        self.assertFalse(Notificacao.objects.filter(titulo__icontains='Tentativa bloqueada').exists())

        # ── DESUP fecha a janela pela tela de edição ─────────────────────────
        self.client.force_login(self.desup)
        resp = self.client.post(
            reverse('core:janela_update', kwargs={'pk': janela.pk}),
            {
                'semestre': '2026.1',
                'data_inicio': self.hoje,
                'data_fim': self.hoje + timezone.timedelta(days=10),
                'status': JanelaEntrega.StatusChoices.FECHADO,
                'unidade': '',
            },
        )
        self.assertRedirects(resp, reverse('core:janela_list'))
        janela.refresh_from_db()
        self.assertEqual(janela.status, JanelaEntrega.StatusChoices.FECHADO)

        # ── O mesmo coordenador agora é bloqueado ────────────────────────────
        self.client.force_login(self.coord)
        resp = self.client.get('/alocacao-curricular/')
        self.assertTrue(resp.context['window_fechada'])
        self.assertContains(resp, 'windowClosedNotice')

        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Notificacao.objects.filter(titulo__icontains='Tentativa bloqueada').exists())

    def test_reabrir_janela_pela_edicao_gera_status_reaberto_e_libera_de_novo(self):
        janela = self.criar_janela(status=JanelaEntrega.StatusChoices.FECHADO)
        self.client.force_login(self.desup)

        resp = self.client.post(
            reverse('core:janela_update', kwargs={'pk': janela.pk}),
            {
                'semestre': janela.semestre,
                'data_inicio': janela.data_inicio,
                'data_fim': janela.data_fim,
                'status': JanelaEntrega.StatusChoices.ABERTO,
                'unidade': '',
            },
        )
        self.assertRedirects(resp, reverse('core:janela_list'))
        janela.refresh_from_db()
        # Editar para "Aberto" registra REABERTO (rastreabilidade da reabertura).
        self.assertEqual(janela.status, JanelaEntrega.StatusChoices.REABERTO)

        self.client.force_login(self.coord)
        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])
        self.assertEqual(resp.status_code, 200)

    def test_desup_exclui_janela_e_coordenador_volta_a_ser_bloqueado(self):
        janela = self.criar_janela()
        self.client.force_login(self.desup)

        url_delete = reverse('core:janela_delete', kwargs={'pk': janela.pk})
        resp = self.client.post(url_delete)
        self.assertRedirects(resp, reverse('core:janela_list'))
        self.assertFalse(JanelaEntrega.objects.filter(pk=janela.pk).exists())

        self.client.force_login(self.coord)
        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])
        self.assertEqual(resp.status_code, 302)

    def test_janela_especifica_da_unidade_libera_apenas_a_propria_unidade(self):
        """Janela só da unidade A: a unidade B (sem janela global) continua bloqueada."""
        outra_unidade = Unidade.objects.create(nome='Unidade Fora', sigla='UFO')
        coord_fora = self.criar_coordenador('e2e_janela_fora@teste.com', unidade=outra_unidade)
        fixture_fora = self.montar_alocacao(outra_unidade, sufixo='FOR')
        self.criar_janela(unidade=self.unidade)

        self.client.force_login(self.coord)
        self.assertEqual(
            self.alocar(self.fixture['matrix_component'], self.fixture['professor']).status_code, 200
        )

        self.client.force_login(coord_fora)
        self.assertEqual(
            self.alocar(fixture_fora['matrix_component'], fixture_fora['professor']).status_code, 302
        )

    def test_janela_global_libera_todas_as_unidades(self):
        outra_unidade = Unidade.objects.create(nome='Unidade Global', sigla='UGL')
        coord_outro = self.criar_coordenador('e2e_janela_global@teste.com', unidade=outra_unidade)
        fixture_outro = self.montar_alocacao(outra_unidade, sufixo='GLO')
        janela = self.criar_janela(unidade=None)
        self.assertIsNone(janela.unidade)

        for user, fixture in ((self.coord, self.fixture), (coord_outro, fixture_outro)):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                resp = self.alocar(fixture['matrix_component'], fixture['professor'])
                self.assertEqual(resp.status_code, 200)

    def test_override_fechado_da_unidade_vence_a_janela_global_aberta(self):
        """Fechar só para uma unidade: a global segue valendo para as demais."""
        outra_unidade = Unidade.objects.create(nome='Unidade Livre', sigla='ULV')
        coord_outro = self.criar_coordenador('e2e_janela_livre@teste.com', unidade=outra_unidade)
        fixture_outro = self.montar_alocacao(outra_unidade, sufixo='LIV')

        self.criar_janela(unidade=None)  # global aberta
        self.criar_janela(status=JanelaEntrega.StatusChoices.FECHADO, unidade=self.unidade)

        self.client.force_login(self.coord)
        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])
        self.assertEqual(resp.status_code, 302)  # override fechado da unidade prevalece

        self.client.force_login(coord_outro)
        resp = self.alocar(fixture_outro['matrix_component'], fixture_outro['professor'])
        self.assertEqual(resp.status_code, 200)  # global continua valendo

    def test_janela_global_nao_pode_ser_convertida_em_janela_de_unidade(self):
        janela = self.criar_janela(unidade=None)
        self.client.force_login(self.desup)

        resp = self.client.post(
            reverse('core:janela_update', kwargs={'pk': janela.pk}),
            {
                'semestre': janela.semestre,
                'data_inicio': janela.data_inicio,
                'data_fim': janela.data_fim,
                'status': JanelaEntrega.StatusChoices.FECHADO,
                'unidade': self.unidade.pk,
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['form'].errors)
        janela.refresh_from_db()
        self.assertIsNone(janela.unidade)

    def test_fechar_janelas_expiradas_fecha_a_vencida_e_preserva_a_vigente(self):
        from apps.core.services import fechar_janelas_expiradas

        vencida = self.criar_janela(dias_inicio=-30, dias_fim=-1)
        vigente = self.criar_janela(dias_inicio=0, dias_fim=5, semestre='2026.2')
        reaberta_vencida = self.criar_janela(
            status=JanelaEntrega.StatusChoices.REABERTO, dias_inicio=-10, dias_fim=-2,
            semestre='2025.2',
        )

        fechar_janelas_expiradas()

        vencida.refresh_from_db()
        vigente.refresh_from_db()
        reaberta_vencida.refresh_from_db()
        self.assertEqual(vencida.status, JanelaEntrega.StatusChoices.FECHADO)
        self.assertEqual(reaberta_vencida.status, JanelaEntrega.StatusChoices.FECHADO)
        self.assertEqual(vigente.status, JanelaEntrega.StatusChoices.ABERTO)

    def test_listagem_da_desup_fecha_janela_vencida_ao_ser_aberta(self):
        """A própria tela de janelas roda o fechamento automático (E2E do expirar)."""
        vencida = self.criar_janela(dias_inicio=-30, dias_fim=-1)
        self.client.force_login(self.desup)

        resp = self.client.get(reverse('core:janela_list'))

        self.assertEqual(resp.status_code, 200)
        vencida.refresh_from_db()
        self.assertEqual(vencida.status, JanelaEntrega.StatusChoices.FECHADO)

    def test_coordenador_nao_acessa_a_area_de_janelas(self):
        self.client.force_login(self.coord)
        for nome in ('janela_list', 'janela_create'):
            with self.subTest(nome=nome):
                resp = self.client.get(reverse(f'core:{nome}'), follow=True)
                self.assertEqual(resp.redirect_chain[-1][0], '/dashboard/unidade/')
                self.assertEqual(resp.status_code, 200)
                self.assertIn(
                    'A área de janelas de entrega é restrita à DESUP.',
                    self.mensagens(resp),
                )

    def test_tela_de_confirmacao_de_exclusao_de_janela_renderiza(self):
        """
        BUG-7 (CORRIGIDO): `GET /core/entregas/<pk>/excluir/` estourava 500.

        `JanelaEntregaDeleteView` apontava para
        `template_name = 'core/janela_confirm_delete.html'`, mas esse arquivo não
        existia em `project_root/templates/core/` (só existia o equivalente de curso,
        `curso_confirm_delete.html`). O GET da confirmação levantava
        `TemplateDoesNotExist` — com DEBUG=False, erro 500. O POST funcionava porque
        a DeleteView não renderiza template ao excluir.

        O template foi criado; o `@expectedFailure` saiu junto com o bug.
        """
        janela = self.criar_janela()
        self.client.force_login(self.desup)

        resp = self.client.get(reverse('core:janela_delete', kwargs={'pk': janela.pk}))

        self.assertEqual(resp.status_code, 200)

    def test_unidade_com_janela_antiga_expirada_pode_ser_reaberta(self):
        """
        BUG-1 (CORRIGIDO): uma unidade que já tivesse QUALQUER janela fechada ficava
        bloqueada para sempre.

        `get_delivery_window` tratava como "override explícito de fechamento"
        qualquer `JanelaEntrega` da unidade com `status='Fechado'`, sem olhar as
        datas. Só que `fechar_janelas_expiradas` muda o status das janelas vencidas
        para 'Fechado'. Resultado: a primeira janela da unidade que expirava virava
        um override permanente e nem uma nova janela da unidade nem uma janela
        global conseguiam reabrir a unidade.

        Repro:
            1. Unidade UJA teve uma janela em 2025 (data_fim no passado, status Aberto).
            2. Qualquer request roda `fechar_janelas_expiradas` -> ela vira 'Fechado'.
            3. DESUP cria uma nova janela ABERTA para UJA (datas de hoje).
            4. Esperado: `get_delivery_window(UJA)` devolve a nova janela.

        Agora o override só vale enquanto a janela Fechado cobrir o dia de hoje.
        """
        from apps.core.services import fechar_janelas_expiradas, get_delivery_window

        self.criar_janela(unidade=self.unidade, dias_inicio=-60, dias_fim=-30, semestre='2025.1')
        fechar_janelas_expiradas()
        nova = self.criar_janela(unidade=self.unidade, dias_inicio=0, dias_fim=10, semestre='2026.1')

        self.assertEqual(get_delivery_window(unidade=self.unidade), nova)


# ══════════════════════════════════════════════════════════════════════════════
# 4) Bloqueio fora da janela -> notificação para a DESUP
# ══════════════════════════════════════════════════════════════════════════════

class JornadaBloqueioNotificaDesupTests(AlocacaoFixtureMixin, BaseE2ETestCase):
    """Coordenador tenta operar com a janela fechada: é barrado e a DESUP é avisada."""

    def setUp(self):
        self.desup = self.criar_desup('e2e_bloq_desup@teste.com')
        self.unidade = Unidade.objects.create(nome='Unidade Bloqueio', sigla='UBQ')
        self.coord = self.criar_coordenador('e2e_bloq_coord@teste.com', unidade=self.unidade)
        self.fixture = self.montar_alocacao(self.unidade, sufixo='BLQ')
        # Nenhuma JanelaEntrega criada => janela fechada para a unidade.

    def test_tentativa_bloqueada_avisa_a_desup_e_o_coordenador_ve_a_mensagem(self):
        self.client.force_login(self.coord)

        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])

        # 1) A ação foi barrada.
        self.assertEqual(resp.status_code, 302)
        self.fixture['matrix_component'].refresh_from_db()
        self.assertIsNone(self.fixture['matrix_component'].docente)

        # 2) O coordenador vê a mensagem de bloqueio.
        self.assertIn(
            'Janela de entrega fechada. A alteração foi bloqueada e a DESUP foi avisada.',
            self.mensagens(resp),
        )

        # 3) Registro para a DESUP.
        notificacao = Notificacao.objects.get(titulo__startswith='Tentativa bloqueada')
        self.assertIn('Alocação', notificacao.titulo)
        self.assertIn(self.coord.email, notificacao.mensagem)
        self.assertIn(self.unidade.sigla, notificacao.mensagem)
        self.assertEqual(notificacao.url_acao, reverse('core:janela_list'))
        self.assertFalse(notificacao.lida)
        # Notificação de sistema: sem destinatário/unidade => visível à DESUP.
        self.assertIsNone(notificacao.destinatario)
        self.assertIsNone(notificacao.unidade_destino)

        # 4) A DESUP enxerga a notificação no seu dashboard...
        self.client.force_login(self.desup)
        resp_desup = self.client.get(reverse('dashboard_desup'))
        self.assertEqual(resp_desup.status_code, 200)
        self.assertIn(notificacao, list(resp_desup.context['notificacoes_nao_lidas']))

        # 5) ...e o coordenador não vê a notificação interna da DESUP.
        self.client.force_login(self.coord)
        resp_coord = self.client.get(reverse('dashboard_unidade'))
        self.assertEqual(resp_coord.status_code, 200)
        self.assertNotIn(notificacao, list(resp_coord.context['notificacoes_nao_lidas']))

    def test_desup_nao_e_bloqueada_e_nao_gera_notificacao(self):
        self.client.force_login(self.desup)

        resp = self.alocar(self.fixture['matrix_component'], self.fixture['professor'])

        self.assertEqual(resp.status_code, 200)
        self.fixture['matrix_component'].refresh_from_db()
        self.assertEqual(self.fixture['matrix_component'].docente, self.fixture['professor'])
        self.assertFalse(Notificacao.objects.filter(titulo__startswith='Tentativa bloqueada').exists())

    def test_cada_tentativa_bloqueada_gera_um_novo_registro(self):
        self.client.force_login(self.coord)

        self.alocar(self.fixture['matrix_component'], self.fixture['professor'])
        self.alocar(self.fixture['matrix_component'], self.fixture['professor'])

        self.assertEqual(
            Notificacao.objects.filter(titulo__startswith='Tentativa bloqueada').count(), 2
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5) Solicitar chamado de alteração com a janela fechada
# ══════════════════════════════════════════════════════════════════════════════

class JornadaSolicitarChamadoTests(BaseE2ETestCase):
    """Bloqueado pela janela, o coordenador pede abertura via chamado para a DESUP."""

    def setUp(self):
        self.desup = self.criar_desup('e2e_chamado_desup@teste.com')
        self.unidade = Unidade.objects.create(nome='Unidade Chamado', sigla='UCH')
        self.coord = self.criar_coordenador('e2e_chamado_coord@teste.com', unidade=self.unidade)
        self.url = reverse('core:solicitar_chamado_alteracao')

    def test_coordenador_abre_chamado_e_a_desup_recebe_a_notificacao(self):
        self.client.force_login(self.coord)

        resp = self.client.post(self.url, {
            'area_label': 'Alocação',
            'action_label': 'Alocar docente',
            'target_label': 'Banco de Dados I',
            'details': 'Professor entrou depois do fechamento da janela.',
            'next': '/alocacao-curricular/',
        })

        # 1) Volta para a tela de onde saiu.
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/alocacao-curricular/')
        self.assertIn(
            'Chamado encaminhado para a DESUP sobre alocar docente.',
            self.mensagens(resp),
        )

        # 2) Registro criado com o conteúdo do chamado.
        chamado = Notificacao.objects.get(titulo='Chamado - Alocação')
        self.assertIn(self.coord.email, chamado.mensagem)
        self.assertIn('Banco de Dados I', chamado.mensagem)
        self.assertIn('Professor entrou depois do fechamento da janela.', chamado.mensagem)
        self.assertIn(f'{self.unidade.sigla} - {self.unidade.nome}', chamado.mensagem)
        self.assertEqual(chamado.url_acao, reverse('core:janela_list'))

        # 3) A DESUP vê o chamado entre as notificações não lidas.
        self.client.force_login(self.desup)
        resp_desup = self.client.get(reverse('dashboard_desup'))
        self.assertIn(chamado, list(resp_desup.context['notificacoes_nao_lidas']))

    def test_chamado_usa_rotulos_padrao_quando_o_post_vem_vazio(self):
        self.client.force_login(self.coord)

        resp = self.client.post(self.url, {})

        self.assertEqual(resp.status_code, 302)
        chamado = Notificacao.objects.get(titulo='Chamado - Alterações')
        self.assertIn('Alvo: registro', chamado.mensagem)
        self.assertIn('Sem detalhes adicionais.', chamado.mensagem)

    def test_next_externo_e_descartado(self):
        """Open redirect: `next` para outro host cai no fallback '/'."""
        self.client.force_login(self.coord)

        resp = self.client.post(self.url, {'next': 'http://evil.example.com/roubado'})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/')

    def test_coordenador_sem_unidade_nao_abre_chamado(self):
        sem_unidade = self.criar_coordenador('e2e_chamado_sem_unid@teste.com', unidade=None)
        self.client.force_login(sem_unidade)

        resp = self.client.post(self.url, {'area_label': 'Alocação'})

        self.assertEqual(resp.status_code, 302)
        self.assertIn('Sua conta não está vinculada a uma unidade.', self.mensagens(resp))
        self.assertFalse(Notificacao.objects.filter(titulo__startswith='Chamado').exists())

    def test_desup_nao_abre_chamado_para_si_mesma(self):
        self.client.force_login(self.desup)

        resp = self.client.post(self.url, {'area_label': 'Alocação'})

        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Notificacao.objects.filter(titulo__startswith='Chamado').exists())


# ══════════════════════════════════════════════════════════════════════════════
# 6) Marcar notificação como lida
# ══════════════════════════════════════════════════════════════════════════════

class JornadaMarcarNotificacaoLidaTests(BaseE2ETestCase):
    def setUp(self):
        self.unidade_a = Unidade.objects.create(nome='Unidade Notif A', sigla='UNA')
        self.unidade_b = Unidade.objects.create(nome='Unidade Notif B', sigla='UNB')
        self.desup = self.criar_desup('e2e_notif_desup@teste.com')
        self.coord_a = self.criar_coordenador('e2e_notif_a@teste.com', unidade=self.unidade_a)
        self.coord_b = self.criar_coordenador('e2e_notif_b@teste.com', unidade=self.unidade_b)

    def _url(self, notificacao):
        return reverse('core:marcar_notificacao_lida', kwargs={'pk': notificacao.pk})

    def test_dono_ve_a_notificacao_e_marca_como_lida(self):
        notificacao = Notificacao.objects.create(
            destinatario=self.coord_a, titulo='Matriz devolvida',
            mensagem='Sua matriz voltou com pendências.',
            url_acao='/dashboard/unidade/',
        )
        self.client.force_login(self.coord_a)

        # Antes: aparece no sino.
        resp = self.client.get(reverse('dashboard_unidade'))
        self.assertEqual(resp.context['total_notificacoes_nao_lidas'], 1)

        resp = self.client.post(self._url(notificacao))
        self.assertEqual(resp.status_code, 302)
        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)

        # Depois: sumiu do sino.
        resp = self.client.get(reverse('dashboard_unidade'))
        self.assertEqual(resp.context['total_notificacoes_nao_lidas'], 0)

    def test_outro_usuario_nao_marca_notificacao_alheia(self):
        notificacao = Notificacao.objects.create(
            destinatario=self.coord_a, titulo='Só do coord A', mensagem='Privado.',
        )
        self.client.force_login(self.coord_b)

        resp = self.client.post(self._url(notificacao))

        # SEC-001: passou a ser 404 (era 302, e o 302 vazava o `url_acao` alheio).
        self.assertEqual(resp.status_code, 404)
        notificacao.refresh_from_db()
        self.assertFalse(notificacao.lida)

    def test_outro_usuario_tambem_nao_marca_via_get(self):
        notificacao = Notificacao.objects.create(
            destinatario=self.coord_a, titulo='Só do coord A', mensagem='Privado.',
            url_acao='/dashboard/unidade/',
        )
        self.client.force_login(self.coord_b)

        resp = self.client.get(self._url(notificacao))

        # SEC-001: 404 e sem header Location — o `url_acao` alheio não vaza mais.
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Location', resp)
        notificacao.refresh_from_db()
        self.assertFalse(notificacao.lida)

    def test_coordenador_marca_notificacao_endereçada_a_sua_unidade(self):
        notificacao = Notificacao.objects.create(
            unidade_destino=self.unidade_a, titulo='Aviso da unidade', mensagem='Leia.',
        )
        self.client.force_login(self.coord_a)

        self.client.post(self._url(notificacao))

        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)

    def test_coordenador_de_outra_unidade_nao_marca_aviso_de_unidade(self):
        notificacao = Notificacao.objects.create(
            unidade_destino=self.unidade_a, titulo='Aviso da unidade A', mensagem='Leia.',
        )
        self.client.force_login(self.coord_b)

        self.client.post(self._url(notificacao))

        notificacao.refresh_from_db()
        self.assertFalse(notificacao.lida)

    def test_desup_marca_notificacao_de_sistema_e_htmx_devolve_a_contagem(self):
        notificacao = Notificacao.objects.create(
            titulo='Tentativa bloqueada - Alocação', mensagem='Alguém tentou fora da janela.',
            url_acao=reverse('core:janela_list'),
        )
        self.client.force_login(self.desup)

        resp = self.client.post(self._url(notificacao), headers={'HX-Request': 'true'})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'')
        self.assertEqual(resp['HX-Trigger'], '{"notifCountUpdate": 0}')
        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)

    def test_anonimo_e_mandado_para_o_login(self):
        notificacao = Notificacao.objects.create(
            destinatario=self.coord_a, titulo='Privada', mensagem='...',
        )

        resp = self.client.post(self._url(notificacao))

        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])
        notificacao.refresh_from_db()
        self.assertFalse(notificacao.lida)


# ══════════════════════════════════════════════════════════════════════════════
# 7) Dashboards — roteamento por perfil e renderização com dados reais
# ══════════════════════════════════════════════════════════════════════════════

class JornadaDashboardsTests(BaseE2ETestCase):
    def setUp(self):
        self.unidade_ok = Unidade.objects.create(nome='Unidade Conforme', sigla='UOK')
        self.unidade_ruim = Unidade.objects.create(nome='Unidade Pendente', sigla='UPE')
        self.desup = self.criar_desup('e2e_dash_desup@teste.com')
        self.coord = self.criar_coordenador('e2e_dash_coord@teste.com', unidade=self.unidade_ok)
        self.admin_ti = self.criar_admin_ti('e2e_dash_admin@teste.com')

        contrato = ContractType.objects.create(
            nome='40h', max_class_hours=20, max_total_hours=40, max_classes=4,
        )
        self.prof_ok = Professor.objects.create(
            id_funcional='IDF-DASH1', rh_matricula='MAT-DASH1', rh_nome='Ana Conforme',
            rh_email='ana@teste.com', unidade_principal=self.unidade_ok,
            tipo_contrato=contrato, ha=20, materia=Professor.MateriaChoices.INFORMATICA,
        )
        self.prof_pendente = Professor.objects.create(
            id_funcional='IDF-DASH2', rh_matricula='MAT-DASH2', rh_nome='Bruno Pendente',
            rh_email='bruno@teste.com', unidade_principal=self.unidade_ruim,
            tipo_contrato=contrato, ha=20,
        )

    def test_dashboard_roteia_cada_perfil_para_o_lugar_certo(self):
        casos = [
            (self.desup, '/dashboard/desup/'),
            (self.coord, '/dashboard/unidade/'),
            (self.admin_ti, '/admin/'),  # CORR-021: TI vai para o admin do Django
        ]
        for user, destino in casos:
            with self.subTest(perfil=user.perfil):
                self.client.force_login(user)
                resp = self.client.get('/dashboard/')
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(resp['Location'], destino)

    def test_dashboard_desup_renderiza_com_dados_reais(self):
        self.client.force_login(self.desup)

        resp = self.client.get(reverse('dashboard_desup'))

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'dashboard/desup.html')
        self.assertEqual(resp.context['total_unidades'], 2)
        self.assertEqual(resp.context['total_professores'], 2)
        # Professores sem alocação => as duas unidades ficam não conformes.
        nao_conformes = {u['nome'] for u in resp.context['unidades_nao_conformes']}
        self.assertEqual(nao_conformes, {'Unidade Conforme', 'Unidade Pendente'})
        self.assertEqual(resp.context['conformidade'], '0%')
        nomes = {item['prof'].rh_nome for item in resp.context['alocacoes_dashboard']}
        self.assertEqual(nomes, {'Ana Conforme', 'Bruno Pendente'})
        self.assertContains(resp, 'Ana Conforme')

    def test_dashboard_desup_conta_como_conforme_a_unidade_sem_professor_ativo(self):
        self.prof_ok.status = Professor.StatusChoices.AFASTADO
        self.prof_ok.save()
        self.prof_pendente.status = Professor.StatusChoices.AFASTADO
        self.prof_pendente.save()
        self.client.force_login(self.desup)

        resp = self.client.get(reverse('dashboard_desup'))

        self.assertEqual(resp.context['unidades_conformes_count'], 2)
        self.assertEqual(resp.context['conformidade'], '100%')

    def test_dashboard_unidade_renderiza_para_o_coordenador(self):
        self.client.force_login(self.coord)

        resp = self.client.get(reverse('dashboard_unidade'))

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'dashboard/unidade.html')
        self.assertContains(resp, self.unidade_ok.sigla)
        self.assertContains(resp, self.coord.email)

    def test_cada_perfil_so_entra_no_proprio_dashboard(self):
        self.client.force_login(self.coord)
        self.assertEqual(self.client.get(reverse('dashboard_desup')).status_code, 403)

        self.client.force_login(self.desup)
        self.assertEqual(self.client.get(reverse('dashboard_unidade')).status_code, 403)

        # CORR-021: o perfil ADMIN é redirecionado (não é falta de permissão).
        self.client.force_login(self.admin_ti)
        resp = self.client.get(reverse('dashboard_desup'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], '/admin/')

    def test_raiz_do_site_leva_ao_dashboard_do_perfil(self):
        self.client.force_login(self.coord)

        resp = self.client.get('/', follow=True)

        self.assertEqual(resp.redirect_chain[-1][0], '/dashboard/unidade/')
        self.assertEqual(resp.status_code, 200)


# ══════════════════════════════════════════════════════════════════════════════
# 8) Atalhos do dashboard DESUP — jornada adicionar/remover
# ══════════════════════════════════════════════════════════════════════════════

class JornadaAtalhosDashboardTests(BaseE2ETestCase):
    def setUp(self):
        self.desup = self.criar_desup('e2e_atalho_desup@teste.com')
        self.url_dashboard = reverse('dashboard_desup')

    def test_jornada_adicionar_e_remover_atalho_pelo_dashboard(self):
        self.client.force_login(self.desup)

        # 1) Dashboard começa sem atalhos e oferece a opção no catálogo.
        resp = self.client.get(self.url_dashboard)
        self.assertEqual(resp.context['atalhos_user'], [])
        self.assertIn('janela_list', {op['chave'] for op in resp.context['atalhos_disponiveis']})

        # 2) Adiciona o atalho.
        resp = self.client.post(reverse('core:atalho_add'), {'chave': 'janela_list'})
        self.assertRedirects(resp, self.url_dashboard)
        atalho = AtalhoDashboard.objects.get(user=self.desup, chave='janela_list')
        self.assertIn('Atalho(s) salvo(s).', self.mensagens(resp))

        # 3) Ele aparece no dashboard, resolvido para label/href/ícone.
        resp = self.client.get(self.url_dashboard)
        atalhos = {a['label']: a for a in resp.context['atalhos_user']}
        self.assertIn('Janelas de Entrega', atalhos)
        self.assertEqual(atalhos['Janelas de Entrega']['href'], reverse('core:janela_list'))
        self.assertNotIn('janela_list', {op['chave'] for op in resp.context['atalhos_disponiveis']})

        # 4) Remove.
        resp = self.client.post(reverse('core:atalho_remove', kwargs={'pk': atalho.pk}))
        self.assertRedirects(resp, self.url_dashboard)
        self.assertFalse(AtalhoDashboard.objects.filter(pk=atalho.pk).exists())

        # 5) Voltou ao estado inicial e o atalho está disponível de novo.
        resp = self.client.get(self.url_dashboard)
        self.assertEqual(resp.context['atalhos_user'], [])
        self.assertIn('janela_list', {op['chave'] for op in resp.context['atalhos_disponiveis']})

    def test_atalho_e_por_usuario_e_nao_vaza_para_outro_desup(self):
        outro = self.criar_desup('e2e_atalho_desup2@teste.com')
        self.client.force_login(self.desup)
        self.client.post(reverse('core:atalho_add'), {'chave': 'unidade_list'})

        self.client.force_login(outro)
        resp = self.client.get(self.url_dashboard)

        self.assertEqual(resp.context['atalhos_user'], [])
        self.assertIn('unidade_list', {op['chave'] for op in resp.context['atalhos_disponiveis']})


# ══════════════════════════════════════════════════════════════════════════════
# 9) e 10) Auditoria + exportação de logs
# ══════════════════════════════════════════════════════════════════════════════

class JornadaAuditoriaEExportacaoTests(BaseE2ETestCase):
    """Ação sensível -> linha em AuditoriaGlobal -> CSV baixado pela DESUP."""

    def setUp(self):
        self.desup = self.criar_desup('e2e_log_desup@teste.com')
        self.unidade = Unidade.objects.create(nome='Unidade Log', sigla='ULG')
        self.coord = self.criar_coordenador('e2e_log_coord@teste.com', unidade=self.unidade)
        self.url = reverse('core:exportar_logs')

        curso = Course.objects.create(nome='Curso Auditado', sigla='CAU')
        self.matriz = CurriculumMatrix.objects.create(
            curso=curso, nome='MC-AUDIT', is_vigente=True,
            periodo_letivo='2026.1', turno='N',
        )
        self.matriz.unidades.add(self.unidade)

    def test_arquivar_matriz_grava_auditoria_e_o_log_sai_no_csv(self):
        self.client.force_login(self.desup)

        # 1) Ação sensível: DESUP arquiva a matriz vigente.
        resp = self.client.post(reverse('courses:matrix_archive', kwargs={'pk': self.matriz.pk}))
        self.assertEqual(resp.status_code, 302)
        self.matriz.refresh_from_db()
        self.assertFalse(self.matriz.is_vigente)

        # 2) Gravou em AuditoriaGlobal, com autor e detalhes.
        log = AuditoriaGlobal.objects.get(acao='MATRIZ_ARQUIVADA')
        self.assertEqual(log.usuario, self.desup)
        self.assertEqual(log.email, self.desup.email)
        self.assertIn('MC-AUDIT', log.detalhes)

        # 3) O log sai na exportação CSV.
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8-sig')
        self.assertIn('auditoria_sistema.csv', resp['Content-Disposition'])

        conteudo = resp.content.decode('utf-8-sig')
        linhas = [linha for linha in conteudo.splitlines() if linha]
        self.assertEqual(linhas[0], 'ID;Data/Hora;Usuario (E-mail);Acao;Detalhes;IP;User-Agent')
        self.assertEqual(len(linhas), 2)
        self.assertIn('MATRIZ_ARQUIVADA', linhas[1])
        self.assertIn(self.desup.email, linhas[1])
        self.assertIn(str(log.pk), linhas[1])

    def test_reativar_matriz_tambem_e_auditado_e_entra_no_csv(self):
        self.matriz.is_vigente = False
        self.matriz.save(update_fields=['is_vigente'])
        self.client.force_login(self.desup)

        self.client.post(reverse('courses:matrix_reactivate', kwargs={'pk': self.matriz.pk}))

        self.assertTrue(AuditoriaGlobal.objects.filter(acao='MATRIZ_REATIVADA').exists())
        conteudo = self.client.get(self.url).content.decode('utf-8-sig')
        self.assertIn('MATRIZ_REATIVADA', conteudo)

    def test_exportacao_vazia_traz_apenas_o_cabecalho(self):
        self.client.force_login(self.desup)

        conteudo = self.client.get(self.url).content.decode('utf-8-sig')

        linhas = [linha for linha in conteudo.splitlines() if linha]
        self.assertEqual(linhas, ['ID;Data/Hora;Usuario (E-mail);Acao;Detalhes;IP;User-Agent'])

    def test_superusuario_desup_tambem_exporta(self):
        super_desup = User.objects.create_superuser(
            email='e2e_log_super@teste.com', password='pw',
            perfil='DESUP', forcar_troca_senha=False,
        )
        self.client.force_login(super_desup)

        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('ID;Data/Hora', resp.content.decode('utf-8-sig'))

    def test_coordenador_de_unidade_nao_exporta_logs(self):
        self.client.force_login(self.coord)

        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 403)

    def test_anonimo_nao_exporta_logs(self):
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_coordenador_nao_arquiva_matriz_e_nao_gera_auditoria(self):
        self.client.force_login(self.coord)

        resp = self.client.post(reverse('courses:matrix_archive', kwargs={'pk': self.matriz.pk}))

        self.assertEqual(resp.status_code, 302)
        self.matriz.refresh_from_db()
        self.assertTrue(self.matriz.is_vigente)
        self.assertFalse(AuditoriaGlobal.objects.filter(acao='MATRIZ_ARQUIVADA').exists())
