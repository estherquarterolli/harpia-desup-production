"""
Testes END-TO-END do app `courses` (matrizes curriculares e componentes).

Enquanto `tests.py` exercita forms/formsets e regras de forma isolada, aqui as
jornadas são percorridas **pela camada HTTP**, do login até o efeito no banco:
criar rascunho → editar → publicar → arquivar → reativar, duplicar matriz,
CRUD de disciplina e os endpoints auxiliares (HTMX/JSON) que as telas consomem.

Regras exercitadas de ponta a ponta:
  • CORR-007 — no componente da matriz só Disciplina e Período são editáveis;
    código, CH total, créditos e CH semanal são `disabled` e derivados no servidor.
  • CORR-008 — a unidade não edita matriz e não enxerga rascunhos.
  • CORR-011 — publicar/duplicar NÃO arquiva as demais matrizes do curso.
  • CORR-012 — arquivar/reativar é manual, DESUP-only e registra auditoria.
"""

import re
from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditoriaGlobal, Unidade
from apps.courses.models import (
    Course,
    CourseUnit,
    CurricularComponent,
    CurriculumMatrix,
    MatrixComponent,
)

PREFIXO = 'componentes'
HX = {'HX-Request': 'true'}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de payload — espelham exatamente o que o formulário da tela envia
# ──────────────────────────────────────────────────────────────────────────────

def linha_componente(disciplina, periodo='1º Semestre', **extra):
    """
    Uma linha do formset como a tela envia.

    CORR-007: a tela só permite digitar **Disciplina** e **Período** — os demais
    campos vão no POST apenas porque são renderizados `disabled` (e por isso o
    Django os ignora). `extra` serve para simular adulteração ou informar
    `id`/`DELETE` na edição.
    """
    dados = {
        'componente_curricular': str(disciplina.id),
        'periodo': periodo,
        'status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
    }
    dados.update({k: str(v) for k, v in extra.items()})
    return dados


def payload_matriz(*, curso, unidades, nome, linhas, rascunho=False, initial_forms=0):
    """Monta o POST completo do formulário de matriz (form + management form + linhas)."""
    data = {
        'curso': str(curso.id),
        'unidades': [str(u.id) for u in unidades],
        'nome': nome,
        f'{PREFIXO}-TOTAL_FORMS': str(len(linhas)),
        f'{PREFIXO}-INITIAL_FORMS': str(initial_forms),
        f'{PREFIXO}-MIN_NUM_FORMS': '1',
        f'{PREFIXO}-MAX_NUM_FORMS': '1000',
    }
    # 'salvar_rascunho' != 'true' significa publicar (a tela envia 'false').
    data['salvar_rascunho'] = 'true' if rascunho else 'false'
    for i, linha in enumerate(linhas):
        for campo, valor in linha.items():
            data[f'{PREFIXO}-{i}-{campo}'] = valor
    return data


def tag_do_campo(html, nome_do_campo):
    """Devolve a tag <input>/<select> renderizada para um campo do formulário."""
    achado = re.search(
        r'<(?:input|select)[^>]*name="%s"[^>]*>' % re.escape(nome_do_campo), html
    )
    return achado.group(0) if achado else ''


# ──────────────────────────────────────────────────────────────────────────────
# Base comum das jornadas
# ──────────────────────────────────────────────────────────────────────────────

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BaseCoursesE2ETests(TestCase):
    """Cenário compartilhado: duas unidades, dois cursos, quatro disciplinas, perfis.

    O hasher rápido vale para as subclasses (cada jornada cria 4 usuários e o PBKDF2
    padrão dominaria o tempo da suíte).
    """

    def setUp(self):
        self.client = Client()

        self.unidade_a = Unidade.objects.create(nome='Unidade E2E Alfa', sigla='UEA')
        self.unidade_b = Unidade.objects.create(nome='Unidade E2E Beta', sigla='UEB')

        self.curso = Course.objects.create(nome='Curso E2E Alfa', sigla='CEA')
        self.curso_b = Course.objects.create(nome='Curso E2E Beta', sigla='CEB')
        CourseUnit.objects.create(curso=self.curso, unidade=self.unidade_a)
        CourseUnit.objects.create(curso=self.curso_b, unidade=self.unidade_b)

        self.algoritmos = CurricularComponent.objects.create(
            nome='Algoritmos e Programacao', codigo='E2E001', carga_horaria_padrao=80, creditos=4,
        )
        self.estrutura = CurricularComponent.objects.create(
            nome='Estrutura de Dados', codigo='E2E002', carga_horaria_padrao=60, creditos=3,
        )
        self.calculo = CurricularComponent.objects.create(
            nome='Calculo Aplicado', codigo='E2E003', carga_horaria_padrao=90, creditos=4,
        )
        self.banco = CurricularComponent.objects.create(
            nome='Banco de Dados', codigo='E2E004', carga_horaria_padrao=40, creditos=2,
        )

        self.desup = User.objects.create_user(
            email='desup_e2e@teste.com', perfil='DESUP', forcar_troca_senha=False,
        )
        self.coord_a = User.objects.create_user(
            email='coord_a_e2e@teste.com', perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade_a, forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email='coord_b_e2e@teste.com', perfil='COORDENADOR_UNIDADE',
            unidade=self.unidade_b, forcar_troca_senha=False,
        )
        self.admin_ti = User.objects.create_user(
            email='admin_ti_e2e@teste.com', perfil='ADMIN', forcar_troca_senha=False,
            is_staff=True, is_superuser=True,
        )

    # ── utilidades ───────────────────────────────────────────────────
    def mensagens(self, resp):
        return [str(m) for m in get_messages(resp.wsgi_request)]

    def pks_da_lista(self, resp):
        return {m.pk for m in resp.context['matrices']}

    def criar_matriz(self, *, nome, curso=None, unidades=None, vigente=True, rascunho=False,
                     disciplinas=()):
        """Cria matriz direto no modelo (fixture), sem passar pela tela."""
        matriz = CurriculumMatrix.objects.create(
            curso=curso or self.curso, nome=nome, is_vigente=vigente, is_rascunho=rascunho,
        )
        for unidade in (unidades or [self.unidade_a]):
            matriz.unidades.add(unidade)
        for disciplina in disciplinas:
            ch = disciplina.carga_horaria_padrao
            MatrixComponent.objects.create(
                matriz=matriz,
                componente_curricular=disciplina,
                periodo='1º Semestre',
                carga_horaria=ch,
                # Mesma derivação que o form aplica (CORR-007).
                creditos=ch // 20,
                carga_horaria_semanal=Decimal(ch) / 20,
            )
        return matriz


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 1 — Ciclo de vida completo da matriz (jornada única, ponta a ponta)
# ══════════════════════════════════════════════════════════════════════════════

class MatrizCicloDeVidaE2ETests(BaseCoursesE2ETests):
    """DESUP: rascunho → edição → publicação → arquivamento → reativação."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.desup)

    def test_jornada_completa_do_rascunho_a_reativacao(self):
        # ── Passo 1: abrir o formulário de nova matriz ────────────────
        resp = self.client.get(reverse('courses:matrix_create'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_desup'])
        # A tela nasce com 4 linhas em branco: max(initial, min_num=1) + extra=3.
        self.assertEqual(resp.context['component_formset'].total_form_count(), 4)

        # ── Passo 2: salvar como RASCUNHO com 1 componente ────────────
        resp = self.client.post(
            reverse('courses:matrix_create'),
            data=payload_matriz(
                curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-2026',
                linhas=[linha_componente(self.algoritmos, '1º Semestre')],
                rascunho=True,
            ),
        )
        self.assertEqual(resp.status_code, 302, resp.content[:400])
        self.assertEqual(resp.url, reverse('courses:matrix_list'))

        matriz = CurriculumMatrix.objects.get(nome='MC-CEA-2026')
        self.assertTrue(matriz.is_rascunho)
        self.assertFalse(matriz.is_vigente)
        self.assertEqual(matriz.curso_id, self.curso.id)
        self.assertEqual([u.pk for u in matriz.unidades.all()], [self.unidade_a.pk])

        # CORR-007: código/CH/créditos/CH semanal derivados da disciplina no servidor.
        comp = matriz.componentes_da_matriz.get()
        self.assertEqual(comp.componente_curricular_id, self.algoritmos.id)
        self.assertEqual(comp.periodo, '1º Semestre')
        self.assertEqual(comp.codigo, 'E2E001')
        self.assertEqual(comp.carga_horaria, 80)
        self.assertEqual(comp.creditos, 4)
        self.assertEqual(comp.carga_horaria_semanal, Decimal('4'))

        # ── Passo 3: o rascunho só aparece na aba Rascunhos ───────────
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'rascunho'})
        self.assertIn(matriz.pk, self.pks_da_lista(resp))
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'vigente'})
        self.assertNotIn(matriz.pk, self.pks_da_lista(resp))

        # ── Passo 4: editar o rascunho ADICIONANDO um componente ──────
        url_edicao = reverse('courses:matrix_update', kwargs={'pk': matriz.pk})
        self.assertEqual(self.client.get(url_edicao).status_code, 200)

        resp = self.client.post(url_edicao, data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-2026',
            linhas=[
                linha_componente(self.algoritmos, '1º Semestre', id=comp.pk),
                linha_componente(self.estrutura, '2º Semestre'),
            ],
            rascunho=True, initial_forms=1,
        ))
        self.assertEqual(resp.status_code, 302, resp.content[:400])
        self.assertEqual(matriz.componentes_da_matriz.count(), 2)
        novo = matriz.componentes_da_matriz.get(componente_curricular=self.estrutura)
        self.assertEqual(novo.carga_horaria, 60)   # CH padrão da disciplina
        self.assertEqual(novo.creditos, 3)         # 60 // 20
        self.assertEqual(novo.periodo, '2º Semestre')

        # ── Passo 5: editar o rascunho REMOVENDO o componente (DELETE) ─
        resp = self.client.post(url_edicao, data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-2026',
            linhas=[
                linha_componente(self.algoritmos, '1º Semestre', id=comp.pk),
                linha_componente(self.estrutura, '2º Semestre', id=novo.pk, DELETE='on'),
            ],
            rascunho=True, initial_forms=2,
        ))
        self.assertEqual(resp.status_code, 302, resp.content[:400])
        self.assertEqual(matriz.componentes_da_matriz.count(), 1)
        self.assertFalse(MatrixComponent.objects.filter(pk=novo.pk).exists())
        matriz.refresh_from_db()
        self.assertTrue(matriz.is_rascunho, 'Salvar rascunho não pode publicar a matriz.')

        # ── Passo 6: PUBLICAR (salvar_rascunho='false') ───────────────
        resp = self.client.post(url_edicao, data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-2026',
            linhas=[
                linha_componente(self.algoritmos, '1º Semestre', id=comp.pk),
                linha_componente(self.calculo, '2º Semestre'),
            ],
            rascunho=False, initial_forms=1,
        ))
        self.assertEqual(resp.status_code, 302, resp.content[:400])
        matriz.refresh_from_db()
        self.assertTrue(matriz.is_vigente)
        self.assertFalse(matriz.is_rascunho)
        self.assertEqual(matriz.componentes_da_matriz.count(), 2)

        # 90h não é múltiplo de 20 — créditos truncam, CH semanal não.
        calc = matriz.componentes_da_matriz.get(componente_curricular=self.calculo)
        self.assertEqual(calc.creditos, 4)
        self.assertEqual(calc.carga_horaria_semanal, Decimal('4.5'))

        # ── Passo 7: publicada, aparece em Vigentes e sai de Rascunhos ─
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'vigente'})
        self.assertIn(matriz.pk, self.pks_da_lista(resp))
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'rascunho'})
        self.assertNotIn(matriz.pk, self.pks_da_lista(resp))

        # ── Passo 8: matriz publicada não é mais editável ─────────────
        resp = self.client.get(url_edicao)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:matrix_list'))
        self.assertIn('Somente matrizes com status Rascunho podem ser editadas.',
                      self.mensagens(resp))

        # ── Passo 9: detalhe da matriz publicada ──────────────────────
        resp = self.client.get(reverse('courses:matrix_detail', kwargs={'pk': matriz.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['componentes']), 2)

        # ── Passo 10: ARQUIVAR (CORR-012) → vai para Histórico ────────
        resp = self.client.post(reverse('courses:matrix_archive', kwargs={'pk': matriz.pk}))
        self.assertEqual(resp.status_code, 302)
        matriz.refresh_from_db()
        self.assertFalse(matriz.is_vigente)
        self.assertFalse(matriz.is_rascunho)

        auditoria = AuditoriaGlobal.objects.get(acao='MATRIZ_ARQUIVADA')
        self.assertEqual(auditoria.usuario_id, self.desup.id)
        self.assertEqual(auditoria.email, self.desup.email)
        self.assertIn(f'#{matriz.pk}', auditoria.detalhes)
        self.assertIn('MC-CEA-2026', auditoria.detalhes)
        self.assertIn('CEA', auditoria.detalhes)

        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'historico'})
        self.assertIn(matriz.pk, self.pks_da_lista(resp))
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'vigente'})
        self.assertNotIn(matriz.pk, self.pks_da_lista(resp))

        # ── Passo 11: REATIVAR → volta para Vigentes ──────────────────
        resp = self.client.post(reverse('courses:matrix_reactivate', kwargs={'pk': matriz.pk}))
        self.assertEqual(resp.status_code, 302)
        matriz.refresh_from_db()
        self.assertTrue(matriz.is_vigente)
        self.assertFalse(matriz.is_rascunho)

        auditoria = AuditoriaGlobal.objects.get(acao='MATRIZ_REATIVADA')
        self.assertEqual(auditoria.usuario_id, self.desup.id)
        self.assertIn(f'#{matriz.pk}', auditoria.detalhes)

        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'vigente'})
        self.assertIn(matriz.pk, self.pks_da_lista(resp))
        # A matriz volta inteira: os componentes não se perdem no ciclo.
        self.assertEqual(matriz.componentes_da_matriz.count(), 2)

    def test_arquivar_e_reativar_sao_idempotentes_e_auditam_uma_vez(self):
        """Arquivar duas vezes seguidas não gera auditoria duplicada nem muda estado."""
        matriz = self.criar_matriz(nome='MC-IDEMP', disciplinas=[self.algoritmos])
        url = reverse('courses:matrix_archive', kwargs={'pk': matriz.pk})

        self.client.post(url)
        resp = self.client.post(url)
        self.assertIn('Esta matriz já está no histórico.', self.mensagens(resp))

        matriz.refresh_from_db()
        self.assertFalse(matriz.is_vigente)
        self.assertEqual(AuditoriaGlobal.objects.filter(acao='MATRIZ_ARQUIVADA').count(), 1)

        url_reativar = reverse('courses:matrix_reactivate', kwargs={'pk': matriz.pk})
        self.client.post(url_reativar)
        resp = self.client.post(url_reativar)
        self.assertIn('Esta matriz já está vigente.', self.mensagens(resp))
        self.assertEqual(AuditoriaGlobal.objects.filter(acao='MATRIZ_REATIVADA').count(), 1)

    def test_rascunho_nao_pode_ser_arquivado_nem_reativado(self):
        """CORR-012: o fluxo de status é para matrizes publicadas; rascunho fica de fora."""
        rascunho = self.criar_matriz(
            nome='MC-RASC', vigente=False, rascunho=True, disciplinas=[self.algoritmos],
        )
        resp = self.client.post(reverse('courses:matrix_archive', kwargs={'pk': rascunho.pk}))
        self.assertIn('Rascunhos não podem ser arquivados.', self.mensagens(resp))

        resp = self.client.post(reverse('courses:matrix_reactivate', kwargs={'pk': rascunho.pk}))
        self.assertIn(
            'Rascunhos não são reativados por aqui — use o fluxo de publicação.',
            self.mensagens(resp),
        )
        rascunho.refresh_from_db()
        self.assertTrue(rascunho.is_rascunho)
        self.assertFalse(rascunho.is_vigente)
        self.assertFalse(AuditoriaGlobal.objects.exclude(acao='LOGIN').exists())

    def test_arquivar_volta_para_a_tela_de_origem(self):
        """A ação volta para o referer (a lista filtrada de onde o usuário clicou)."""
        matriz = self.criar_matriz(nome='MC-REFER', disciplinas=[self.algoritmos])
        origem = reverse('courses:matrix_list') + '?status=vigente'
        resp = self.client.post(
            reverse('courses:matrix_archive', kwargs={'pk': matriz.pk}),
            headers={'Referer': origem},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, origem)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 2 — Duplicação / cópia de matriz (CORR-011)
# ══════════════════════════════════════════════════════════════════════════════

class MatrizDuplicacaoE2ETests(BaseCoursesE2ETests):
    """
    Jornada real de duplicar: a tela consulta a matriz existente do curso, baixa os
    componentes por JSON e reenvia tudo como uma matriz nova (turno diferente).
    As duas precisam terminar VIGENTES — CORR-011 removeu o auto-arquivamento.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.desup)
        # Matriz de origem publicada pela própria tela.
        self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-MANHA',
            linhas=[
                linha_componente(self.algoritmos, '1º Semestre'),
                linha_componente(self.estrutura, '2º Semestre'),
            ],
        ))
        self.origem = CurriculumMatrix.objects.get(nome='MC-CEA-MANHA')

    def test_jornada_de_duplicacao_mantem_as_duas_vigentes(self):
        # ── Passo 1: a tela pergunta se já existe matriz para o curso ──
        resp = self.client.get(reverse('courses:matrix_buscar_existente'),
                               {'curso_id': self.curso.id})
        dados = resp.json()
        self.assertTrue(dados['existe'])
        self.assertEqual(dados['matriz_id'], self.origem.pk)
        self.assertIn('MC-CEA-MANHA', dados['nome'])

        # ── Passo 2: baixa os componentes da matriz escolhida ─────────
        resp = self.client.get(
            reverse('courses:matrix_dados_copiar', kwargs={'pk': self.origem.pk})
        )
        self.assertEqual(resp.status_code, 200)
        componentes = resp.json()['componentes']
        self.assertEqual(len(componentes), 2)
        por_codigo = {c['codigo']: c for c in componentes}
        self.assertEqual(por_codigo['E2E001']['carga_horaria'], 80)
        self.assertEqual(por_codigo['E2E001']['creditos'], 4)
        self.assertEqual(por_codigo['E2E002']['periodo'], '2º Semestre')

        # ── Passo 3: reenvia como matriz nova (turno da noite) ────────
        linhas = [
            linha_componente(
                CurricularComponent.objects.get(pk=c['componente_curricular']),
                c['periodo'],
            )
            for c in componentes
        ]
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-NOITE', linhas=linhas,
        ))
        self.assertEqual(resp.status_code, 302, resp.content[:400])

        # ── Passo 4: CORR-011 — as duas coexistem como vigentes ───────
        self.origem.refresh_from_db()
        self.assertTrue(self.origem.is_vigente,
                        'Publicar a duplicata NÃO pode arquivar a matriz de origem.')
        copia = CurriculumMatrix.objects.get(nome='MC-CEA-NOITE')
        self.assertTrue(copia.is_vigente)
        self.assertFalse(copia.is_rascunho)
        self.assertEqual(
            CurriculumMatrix.objects.filter(curso=self.curso, is_vigente=True).count(), 2,
        )

        # ── Passo 5: a cópia carrega os mesmos componentes derivados ──
        self.assertEqual(copia.componentes_da_matriz.count(), 2)
        self.assertEqual(
            sorted(copia.componentes_da_matriz.values_list('codigo', flat=True)),
            ['E2E001', 'E2E002'],
        )
        self.assertEqual(
            copia.componentes_da_matriz.get(codigo='E2E001').carga_horaria_semanal,
            Decimal('4'),
        )

        # ── Passo 6: ambas aparecem na aba Vigente ────────────────────
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'vigente'})
        self.assertLessEqual({self.origem.pk, copia.pk}, self.pks_da_lista(resp))

    def test_arquivar_uma_duplicata_nao_afeta_a_outra(self):
        """CORR-012 é cirúrgico: arquivar a matriz da manhã não mexe na da noite."""
        self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-CEA-NOITE',
            linhas=[linha_componente(self.algoritmos, '1º Semestre')],
        ))
        noite = CurriculumMatrix.objects.get(nome='MC-CEA-NOITE')

        self.client.post(reverse('courses:matrix_archive', kwargs={'pk': self.origem.pk}))
        self.origem.refresh_from_db()
        noite.refresh_from_db()
        self.assertFalse(self.origem.is_vigente)
        self.assertTrue(noite.is_vigente, 'Arquivar uma matriz não pode arquivar as demais.')

    def test_reativar_historico_nao_arquiva_a_vigente_do_curso(self):
        """CORR-011 na volta: reativar convive com a vigente que já existia."""
        historico = self.criar_matriz(
            nome='MC-CEA-2025', vigente=False, disciplinas=[self.banco],
        )
        self.client.post(reverse('courses:matrix_reactivate', kwargs={'pk': historico.pk}))
        self.origem.refresh_from_db()
        historico.refresh_from_db()
        self.assertTrue(historico.is_vigente)
        self.assertTrue(self.origem.is_vigente)
        self.assertEqual(
            CurriculumMatrix.objects.filter(curso=self.curso, is_vigente=True).count(), 2,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 3 — Visibilidade e permissão por perfil (CORR-008 / CORR-012 / CORR-021)
# ══════════════════════════════════════════════════════════════════════════════

class MatrizPermissoesPorPerfilE2ETests(BaseCoursesE2ETests):
    """Coordenador de unidade só lê o que é seu e publicado; DESUP faz tudo; ADMIN vai para o /admin/."""

    def setUp(self):
        super().setUp()
        self.vigente_a = self.criar_matriz(nome='MC-A-VIG', disciplinas=[self.algoritmos])
        self.historico_a = self.criar_matriz(nome='MC-A-HIST', vigente=False,
                                             disciplinas=[self.estrutura])
        self.rascunho_a = self.criar_matriz(nome='MC-A-RASC', vigente=False, rascunho=True,
                                            disciplinas=[self.calculo])
        self.vigente_b = self.criar_matriz(nome='MC-B-VIG', curso=self.curso_b,
                                           unidades=[self.unidade_b], disciplinas=[self.banco])

    # ── Coordenador de unidade: leitura restrita ─────────────────────
    def test_coordenador_ve_apenas_matrizes_publicadas_da_sua_unidade(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse('courses:matrix_list'))
        pks = self.pks_da_lista(resp)
        self.assertIn(self.vigente_a.pk, pks)
        self.assertIn(self.historico_a.pk, pks)
        self.assertNotIn(self.rascunho_a.pk, pks, 'CORR-008: unidade não vê rascunho.')
        self.assertNotIn(self.vigente_b.pk, pks, 'Escopo por unidade: não vê a UEB.')

        # Nem forçando o filtro de rascunhos, nem forçando outra unidade.
        pks_forcado = self.pks_da_lista(
            self.client.get(reverse('courses:matrix_list'), {'status': 'rascunho'})
        )
        self.assertEqual(pks_forcado, set())
        pks_outra_unidade = self.pks_da_lista(
            self.client.get(reverse('courses:matrix_list'), {'unidade_id': self.unidade_b.id})
        )
        self.assertNotIn(self.vigente_b.pk, pks_outra_unidade)

    def test_coordenador_acessa_detalhe_da_sua_matriz_e_leva_404_nas_demais(self):
        self.client.force_login(self.coord_a)
        url = lambda pk: reverse('courses:matrix_detail', kwargs={'pk': pk})
        self.assertEqual(self.client.get(url(self.vigente_a.pk)).status_code, 200)
        self.assertEqual(self.client.get(url(self.rascunho_a.pk)).status_code, 404)
        self.assertEqual(self.client.get(url(self.vigente_b.pk)).status_code, 404)

    def test_coordenador_sem_unidade_nao_ve_nada(self):
        sem_unidade = User.objects.create_user(
            email='coord_sem_unidade@teste.com', perfil='COORDENADOR_UNIDADE',
            forcar_troca_senha=False,
        )
        self.client.force_login(sem_unidade)
        resp = self.client.get(reverse('courses:matrix_list'))
        self.assertEqual(self.pks_da_lista(resp), set())
        self.assertEqual(
            self.client.get(
                reverse('courses:matrix_detail', kwargs={'pk': self.vigente_a.pk})
            ).status_code,
            404,
        )

    # ── Coordenador de unidade: nenhuma escrita ──────────────────────
    def test_coordenador_nao_cria_matriz(self):
        self.client.force_login(self.coord_a)
        antes = CurriculumMatrix.objects.count()

        resp = self.client.get(reverse('courses:matrix_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:matrix_list'))
        self.assertIn('Somente a DESUP pode cadastrar nova matriz.', self.mensagens(resp))

        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-INVASOR',
            linhas=[linha_componente(self.algoritmos)],
        ))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CurriculumMatrix.objects.count(), antes)
        self.assertFalse(CurriculumMatrix.objects.filter(nome='MC-INVASOR').exists())

    def test_coordenador_nao_edita_matriz(self):
        self.client.force_login(self.coord_a)
        url = reverse('courses:matrix_update', kwargs={'pk': self.rascunho_a.pk})

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Somente a DESUP pode editar matrizes.', self.mensagens(resp))

        resp = self.client.post(url, data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-A-RASC-EDITADA',
            linhas=[linha_componente(self.algoritmos)], rascunho=True,
        ))
        self.assertEqual(resp.status_code, 302)
        self.rascunho_a.refresh_from_db()
        self.assertEqual(self.rascunho_a.nome, 'MC-A-RASC')

    def test_coordenador_nao_arquiva_nem_reativa(self):
        self.client.force_login(self.coord_a)
        for rota, matriz in (('courses:matrix_archive', self.vigente_a),
                             ('courses:matrix_reactivate', self.historico_a)):
            with self.subTest(rota=rota):
                resp = self.client.post(reverse(rota, kwargs={'pk': matriz.pk}))
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(resp.url, reverse('courses:matrix_list'))
                self.assertIn('Somente a DESUP pode alterar o status de matrizes.',
                              self.mensagens(resp))
        self.vigente_a.refresh_from_db()
        self.historico_a.refresh_from_db()
        self.assertTrue(self.vigente_a.is_vigente)
        self.assertFalse(self.historico_a.is_vigente)
        self.assertFalse(AuditoriaGlobal.objects.filter(acao__startswith='MATRIZ_').exists())

    # ── DESUP: enxerga tudo ──────────────────────────────────────────
    def test_desup_enxerga_todas_as_unidades_e_os_rascunhos(self):
        self.client.force_login(self.desup)
        pks = self.pks_da_lista(self.client.get(reverse('courses:matrix_list')))
        self.assertLessEqual(
            {self.vigente_a.pk, self.historico_a.pk, self.rascunho_a.pk, self.vigente_b.pk},
            pks,
        )
        # E consegue filtrar por unidade (privilégio exclusivo da DESUP).
        pks_b = self.pks_da_lista(self.client.get(
            reverse('courses:matrix_list'), {'unidade_id': self.unidade_b.id},
        ))
        self.assertEqual(pks_b, {self.vigente_b.pk})

        # Detalhe de rascunho e de outra unidade: liberado.
        for pk in (self.rascunho_a.pk, self.vigente_b.pk):
            self.assertEqual(
                self.client.get(reverse('courses:matrix_detail', kwargs={'pk': pk})).status_code,
                200,
            )

    def test_filtro_por_curso_funciona_para_a_desup(self):
        self.client.force_login(self.desup)
        pks = self.pks_da_lista(self.client.get(
            reverse('courses:matrix_list'), {'curso_id': self.curso_b.id},
        ))
        self.assertEqual(pks, {self.vigente_b.pk})

    # ── ADMIN (TI): rota operacional redireciona para o /admin/ ──────
    def test_admin_ti_e_redirecionado_para_o_admin_do_django(self):
        self.client.force_login(self.admin_ti)
        for rota, kwargs in (
            ('courses:matrix_list', {}),
            ('courses:matrix_detail', {'pk': self.vigente_a.pk}),
            ('courses:load_duplicate_options', {}),
        ):
            with self.subTest(rota=rota):
                resp = self.client.get(reverse(rota, kwargs=kwargs))
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(resp.url, '/admin/')

    def test_admin_ti_em_requisicao_htmx_recebe_hx_redirect(self):
        self.client.force_login(self.admin_ti)
        resp = self.client.get(reverse('courses:matrix_list_partial'), headers=HX)
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp['HX-Redirect'], '/admin/')

    # ── Anônimo ─────────────────────────────────────────────────────
    def test_anonimo_e_mandado_para_o_login(self):
        for rota, kwargs in (
            ('courses:matrix_list', {}),
            ('courses:matrix_detail', {'pk': self.vigente_a.pk}),
            ('courses:component_list', {}),
            ('courses:buscar_componente', {}),
        ):
            with self.subTest(rota=rota):
                resp = self.client.get(reverse(rota, kwargs=kwargs), follow=True)
                destino = resp.redirect_chain[-1][0]
                self.assertTrue(destino.startswith('/login/'), destino)

    # CORRIGIDO: as views DESUP-only de matriz sobrescrevem `dispatch()` e liam
    # `request.user.perfil` ANTES de chamar `super().dispatch()` — ou seja, antes do
    # LoginRequiredMixin. Para um visitante anônimo, `AnonymousUser` não tem `perfil`
    # e a rota estourava AttributeError (HTTP 500) em vez de redirecionar para o login.
    # Afetava: GET /courses/matrices/add/, GET /courses/matrices/<pk>/edit/,
    #          POST /courses/matrices/<pk>/arquivar/ e .../reativar/.
    # Correção: cada `dispatch()` delega ao `super()` quando o usuário não está
    # autenticado, deixando o LoginRequiredMixin fazer o redirecionamento.
    # Arquivos: project_root/apps/courses/views.py (CurriculumMatrixCreateView,
    #           CurriculumMatrixUpdateView, _MatrixDesupActionView).
    def test_anonimo_na_criacao_de_matriz_vai_para_o_login(self):
        resp = self.client.get(reverse('courses:matrix_create'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/login/'), resp.url)

    # CORRIGIDO: mesma causa do teste acima, agora numa rota de ESCRITA.
    # Antes: POST /courses/matrices/<pk>/arquivar/ sem sessão → AttributeError (500).
    # Arquivo: project_root/apps/courses/views.py (_MatrixDesupActionView.dispatch).
    def test_anonimo_nao_arquiva_matriz(self):
        resp = self.client.post(
            reverse('courses:matrix_archive', kwargs={'pk': self.vigente_a.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/login/'))
        self.vigente_a.refresh_from_db()
        self.assertTrue(self.vigente_a.is_vigente)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 4 — CRUD completo de Componente Curricular (disciplina), DESUP-only
# ══════════════════════════════════════════════════════════════════════════════

class ComponenteCurricularCrudE2ETests(BaseCoursesE2ETests):
    """Criar → listar/filtrar → editar → excluir, com créditos derivados da CH."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.desup)

    def test_jornada_crud_completa(self):
        # ── Criar ─────────────────────────────────────────────────────
        self.assertEqual(self.client.get(reverse('courses:component_create')).status_code, 200)
        resp = self.client.post(reverse('courses:component_create'), data={
            'nome': 'Engenharia de Software',
            'codigo': 'E2E100',
            'carga_horaria_padrao': '60',
            'creditos': '99',          # adulterado: deve virar 60 // 20 = 3
            'obrigatoria': 'on',
            'ementa': 'Processos de software.',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:component_list'))
        self.assertIn('Componente curricular criado com sucesso.', self.mensagens(resp))

        criado = CurricularComponent.objects.get(codigo='E2E100')
        self.assertEqual(criado.carga_horaria_padrao, 60)
        self.assertEqual(criado.creditos, 3)
        self.assertTrue(criado.obrigatoria)

        # ── Listar e filtrar ──────────────────────────────────────────
        resp = self.client.get(reverse('courses:component_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(criado, list(resp.context['componentes']))

        resp = self.client.get(reverse('courses:component_list'), {'q': 'Engenharia'})
        self.assertEqual([c.pk for c in resp.context['componentes']], [criado.pk])
        resp = self.client.get(reverse('courses:component_list'), {'q': 'E2E100'})
        self.assertEqual([c.pk for c in resp.context['componentes']], [criado.pk])
        resp = self.client.get(reverse('courses:component_list'), {'q': 'inexistente-zzz'})
        self.assertEqual(list(resp.context['componentes']), [])

        # ── Editar (créditos re-derivados da nova CH) ─────────────────
        url_edicao = reverse('courses:component_edit', kwargs={'pk': criado.pk})
        self.assertEqual(self.client.get(url_edicao).status_code, 200)
        resp = self.client.post(url_edicao, data={
            'nome': 'Engenharia de Software II',
            'codigo': 'E2E101',
            'carga_horaria_padrao': '100',
            'creditos': '0',
            'obrigatoria': 'on',
            'pre_requisitos': [str(self.algoritmos.id)],
            'ementa': 'Processos e qualidade.',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn('Componente curricular atualizado com sucesso.', self.mensagens(resp))

        criado.refresh_from_db()
        self.assertEqual(criado.nome, 'Engenharia de Software II')
        self.assertEqual(criado.codigo, 'E2E101')
        self.assertEqual(criado.carga_horaria_padrao, 100)
        self.assertEqual(criado.creditos, 5)              # 100 // 20
        self.assertEqual([p.pk for p in criado.pre_requisitos.all()], [self.algoritmos.pk])

        # ── Excluir: a tela de confirmação abre normalmente ───────────
        # (o POST da exclusão está isolado em test_excluir_disciplina.)
        url_exclusao = reverse('courses:component_delete', kwargs={'pk': criado.pk})
        resp = self.client.get(url_exclusao)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['object'].pk, criado.pk)

    # CORRIGIDO: `CurricularComponentDeleteView.form_valid` começava com
    # `from django.db import ProtectedError`, mas `ProtectedError` mora em
    # `django.db.models` (`django.db.models.deletion`) e NUNCA foi exportado por
    # `django.db`. O import era a primeira linha do método, fora do `try` — logo
    # QUALQUER exclusão de componente curricular estourava ImportError (HTTP 500),
    # inclusive as que deveriam funcionar: "excluir disciplina" estava 100% quebrada.
    # Correção: `from django.db.models import ProtectedError`.
    # Arquivo: project_root/apps/courses/views.py (CurricularComponentDeleteView).
    def test_excluir_disciplina(self):
        disciplina = CurricularComponent.objects.create(
            nome='Disciplina Descartavel', codigo='E2E400', carga_horaria_padrao=40,
        )
        resp = self.client.post(
            reverse('courses:component_delete', kwargs={'pk': disciplina.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:component_list'))
        self.assertFalse(CurricularComponent.objects.filter(pk=disciplina.pk).exists())

    def test_creditos_sao_sempre_a_divisao_inteira_por_20(self):
        casos = {20: 1, 45: 2, 80: 4, 90: 4, 15: 0}
        for i, (ch, creditos) in enumerate(casos.items()):
            with self.subTest(carga_horaria=ch):
                self.client.post(reverse('courses:component_create'), data={
                    'nome': f'Disciplina Derivada {i}',
                    'codigo': f'E2E2{i:02d}',
                    'carga_horaria_padrao': str(ch),
                    'creditos': '7',
                    'obrigatoria': 'on',
                    'ementa': '',
                })
                comp = CurricularComponent.objects.get(codigo=f'E2E2{i:02d}')
                self.assertEqual(comp.carga_horaria_padrao, ch)
                self.assertEqual(comp.creditos, creditos)

    def test_carga_horaria_invalida_barra_a_criacao(self):
        antes = CurricularComponent.objects.count()
        resp = self.client.post(reverse('courses:component_create'), data={
            'nome': 'Disciplina Sem CH',
            'codigo': 'E2E300',
            'carga_horaria_padrao': '0',
            'creditos': '0',
            'ementa': '',
        })
        self.assertEqual(resp.status_code, 200)   # re-renderiza com erro
        self.assertIn('carga_horaria_padrao', resp.context['form'].errors)
        self.assertEqual(CurricularComponent.objects.count(), antes)

    # CORRIGIDO (mesma causa de test_excluir_disciplina): o `except ProtectedError`
    # nem chegava a ser avaliado, porque o `from django.db import ProtectedError` da
    # linha anterior já estourava. Em vez da mensagem amigável, o usuário recebia 500.
    # Arquivo: project_root/apps/courses/views.py (CurricularComponentDeleteView).
    def test_nao_exclui_disciplina_vinculada_a_matriz(self):
        """PROTECT: a disciplina usada em uma matriz não pode sumir do catálogo."""
        self.criar_matriz(nome='MC-PROTECT', disciplinas=[self.algoritmos])
        resp = self.client.post(
            reverse('courses:component_delete', kwargs={'pk': self.algoritmos.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:component_list'))
        self.assertIn(
            'Não é possível excluir este componente pois ele está vinculado a uma ou mais matrizes.',
            self.mensagens(resp),
        )
        self.assertTrue(CurricularComponent.objects.filter(pk=self.algoritmos.pk).exists())

    def test_crud_de_disciplina_e_exclusivo_da_desup(self):
        self.client.force_login(self.coord_a)
        rotas = (
            ('courses:component_list', {}),
            ('courses:component_create', {}),
            ('courses:component_edit', {'pk': self.algoritmos.pk}),
            ('courses:component_delete', {'pk': self.algoritmos.pk}),
        )
        for rota, kwargs in rotas:
            with self.subTest(rota=rota):
                resp = self.client.get(reverse(rota, kwargs=kwargs))
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(resp.url, reverse('dashboard'))
                self.assertIn('Acesso restrito à equipe DESUP.', self.mensagens(resp))

        # E o POST também não passa.
        resp = self.client.post(reverse('courses:component_delete',
                                        kwargs={'pk': self.algoritmos.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(CurricularComponent.objects.filter(pk=self.algoritmos.pk).exists())


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 5 — Autocomplete de disciplinas (courses:buscar_componente)
# ══════════════════════════════════════════════════════════════════════════════

class AutocompleteComponenteE2ETests(BaseCoursesE2ETests):
    """JSON consumido pelo campo 'Pesquisar disciplina...' do formulário de matriz."""

    def setUp(self):
        super().setUp()
        self.url = reverse('courses:buscar_componente')
        self.client.force_login(self.desup)

    def test_exige_login(self):
        self.client.logout()
        resp = self.client.get(self.url, {'q': 'Algo'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/login/'))

    def test_minimo_de_dois_caracteres(self):
        for termo in ('', ' ', 'A', ' a '):
            with self.subTest(q=termo):
                resp = self.client.get(self.url, {'q': termo})
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.json()['resultados'], [])

    def test_busca_por_nome_retorna_payload_completo(self):
        resp = self.client.get(self.url, {'q': 'Algor'})
        resultados = resp.json()['resultados']
        self.assertEqual(len(resultados), 1)
        item = resultados[0]
        self.assertEqual(item['id'], self.algoritmos.id)
        self.assertEqual(item['nome'], 'Algoritmos e Programacao')
        self.assertEqual(item['codigo'], 'E2E001')
        self.assertEqual(item['carga_horaria'], 80)
        self.assertEqual(item['creditos'], 4)
        self.assertEqual(item['label'], 'E2E001 — Algoritmos e Programacao (80h)')

    def test_busca_por_codigo_e_filtragem(self):
        resp = self.client.get(self.url, {'q': 'E2E00'})
        ids = {r['id'] for r in resp.json()['resultados']}
        self.assertEqual(
            ids,
            {self.algoritmos.id, self.estrutura.id, self.calculo.id, self.banco.id},
        )

        resp = self.client.get(self.url, {'q': 'E2E003'})
        self.assertEqual([r['id'] for r in resp.json()['resultados']], [self.calculo.id])

        resp = self.client.get(self.url, {'q': 'nao-existe'})
        self.assertEqual(resp.json()['resultados'], [])

    def test_resultado_ordenado_por_nome_e_limitado_a_30(self):
        CurricularComponent.objects.bulk_create([
            CurricularComponent(nome=f'Topicos Especiais {i:02d}', codigo=f'TOP{i:03d}',
                                carga_horaria_padrao=40)
            for i in range(40)
        ])
        resultados = self.client.get(self.url, {'q': 'Topicos'}).json()['resultados']
        self.assertEqual(len(resultados), 30)
        nomes = [r['nome'] for r in resultados]
        self.assertEqual(nomes, sorted(nomes))

    def test_coordenador_tambem_consulta_o_autocomplete(self):
        """O endpoint é catálogo global de disciplinas — basta estar autenticado."""
        self.client.force_login(self.coord_a)
        resp = self.client.get(self.url, {'q': 'Banco'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([r['id'] for r in resp.json()['resultados']], [self.banco.id])


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 6 — Endpoints auxiliares consumidos pelas telas (HTMX / JSON)
# ══════════════════════════════════════════════════════════════════════════════

class EndpointsAuxiliaresE2ETests(BaseCoursesE2ETests):
    """matrix_list_partial, load_courses_by_unit, load_duplicate_options,
    matrix_buscar_existente, matrix_dados_copiar e matrix_add_row."""

    def setUp(self):
        super().setUp()
        self.vigente_a = self.criar_matriz(nome='MC-AUX-A', disciplinas=[self.algoritmos,
                                                                         self.estrutura])
        self.rascunho_a = self.criar_matriz(nome='MC-AUX-RASC', vigente=False, rascunho=True,
                                            disciplinas=[self.calculo])
        self.vigente_b = self.criar_matriz(nome='MC-AUX-B', curso=self.curso_b,
                                           unidades=[self.unidade_b], disciplinas=[self.banco])

    # ── matrix_list_partial ──────────────────────────────────────────
    def test_partial_exige_cabecalho_htmx(self):
        self.client.force_login(self.desup)
        resp = self.client.get(reverse('courses:matrix_list_partial'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('courses:matrix_list'))

    def test_partial_renderiza_a_tabela_filtrada_para_a_desup(self):
        self.client.force_login(self.desup)
        resp = self.client.get(reverse('courses:matrix_list_partial'),
                               {'status': 'vigente'}, headers=HX)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('MC-AUX-A', html)
        self.assertIn('MC-AUX-B', html)
        self.assertNotIn('MC-AUX-RASC', html)
        # A tabela traz os agregados anotados na view.
        self.assertIn('140h', html)   # 80 + 60 da matriz MC-AUX-A

    def test_partial_respeita_o_escopo_do_coordenador(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(reverse('courses:matrix_list_partial'), headers=HX)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('MC-AUX-A', html)
        self.assertNotIn('MC-AUX-B', html)
        self.assertNotIn('MC-AUX-RASC', html, 'CORR-008: rascunho não pode vazar no partial.')

    # ── load_courses_by_unit ─────────────────────────────────────────
    def test_cursos_por_unidade_em_json(self):
        self.client.force_login(self.desup)
        url = reverse('courses:load_courses_by_unit')

        cursos = self.client.get(url, {'unidade_id': self.unidade_a.id}).json()
        self.assertEqual([c['sigla'] for c in cursos], ['CEA'])
        self.assertEqual(cursos[0]['id'], self.curso.id)

        cursos = self.client.get(url, {'unidade_id': self.unidade_b.id}).json()
        self.assertEqual([c['sigla'] for c in cursos], ['CEB'])

        # Sem unidade: todos os cursos com vínculo ativo.
        cursos = self.client.get(url).json()
        self.assertEqual({c['sigla'] for c in cursos}, {'CEA', 'CEB'})

    def test_cursos_por_unidade_ignora_vinculo_inativo(self):
        self.client.force_login(self.desup)
        CourseUnit.objects.filter(curso=self.curso, unidade=self.unidade_a).update(ativo=False)
        cursos = self.client.get(
            reverse('courses:load_courses_by_unit'), {'unidade_id': self.unidade_a.id}
        ).json()
        self.assertEqual(cursos, [])

        # Com global=1 o filtro de vínculo ativo não se aplica (catálogo completo).
        cursos = self.client.get(
            reverse('courses:load_courses_by_unit'),
            {'unidade_id': self.unidade_a.id, 'global': '1'},
        ).json()
        self.assertEqual([c['sigla'] for c in cursos], ['CEA'])

    # CORRIGIDO: `format_html()` sem argumentos foi descontinuado no Django 5.0 e
    # REMOVIDO no 6.0 (o projeto roda Django 6.0.3 — ver requirements.txt). A primeira
    # linha do ramo HTMX chamava `format_html('<option value="">Todos os Cursos</option>')`
    # e levantava `TypeError: args or kwargs must be provided` → HTTP 500. O filtro de
    # cursos por unidade da tela de matrizes (hx-get) ficava quebrado.
    # Correção: o rótulo fixo virou argumento de `format_html` e a lista saiu por
    # `format_html_join`, que escapa sigla/nome do curso.
    # Arquivo: project_root/apps/courses/views.py (LoadCoursesByUnitView).
    def test_cursos_por_unidade_em_htmx_retorna_options(self):
        self.client.force_login(self.desup)
        resp = self.client.get(reverse('courses:load_courses_by_unit'),
                               {'unidade_id': self.unidade_a.id}, headers=HX)
        html = resp.content.decode()
        self.assertIn('<option value="">Todos os Cursos</option>', html)
        self.assertIn(f'<option value="{self.curso.id}">CEA - Curso E2E Alfa</option>', html)

    def test_cursos_por_unidade_exige_login(self):
        resp = self.client.get(reverse('courses:load_courses_by_unit'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/login/'))

    # ── load_duplicate_options ───────────────────────────────────────
    # CORRIGIDO: mesma causa do endpoint de cursos — `format_html()` sem argumentos
    # foi removido no Django 6.0 (projeto em 6.0.3). A view montava a primeira <option>
    # com `format_html('<option value="">Nao duplicar (criar em branco)</option>')` e
    # estourava `TypeError: args or kwargs must be provided` → HTTP 500 SEMPRE (não há
    # caminho alternativo aqui): o <select> "Duplicar a partir de outra Matriz" nunca
    # era populado.
    # Arquivo: project_root/apps/courses/views.py (LoadMatricesForDuplicateView).
    def test_opcoes_de_duplicacao_para_a_desup(self):
        self.client.force_login(self.desup)
        html = self.client.get(reverse('courses:load_duplicate_options')).content.decode()
        self.assertIn('Nao duplicar (criar em branco)', html)
        self.assertIn(f'<option value="{self.vigente_a.pk}">CEA - MC-AUX-A (UEA)</option>', html)
        self.assertIn('MC-AUX-B', html)

        # Filtrando por curso, só as do curso escolhido.
        html = self.client.get(
            reverse('courses:load_duplicate_options'), {'curso_id': self.curso_b.id}
        ).content.decode()
        self.assertIn('MC-AUX-B', html)
        self.assertNotIn('MC-AUX-A', html)

    # CORRIGIDO (duas causas empilhadas):
    #  1) a requisição nem chegava a responder — 500 do `format_html()` acima;
    #  2) mesmo sem o 500, `LoadMatricesForDuplicateView` filtrava só por unidade e
    #     NÃO excluía rascunhos, então o coordenador da UEA recebia no <select> a
    #     matriz 'MC-AUX-RASC', que ele não pode nem listar nem abrir (o detalhe
    #     devolve 404) — contrariava a CORR-008.
    # Correção: `.exclude(is_rascunho=True)` para quem não é DESUP, como já era feito
    # em CurriculumMatrixListView._apply_filters.
    # Arquivo: project_root/apps/courses/views.py (LoadMatricesForDuplicateView).
    def test_opcoes_de_duplicacao_escopo_da_unidade_e_sem_rascunho(self):
        self.client.force_login(self.coord_a)
        html = self.client.get(reverse('courses:load_duplicate_options')).content.decode()
        self.assertIn('MC-AUX-A', html)
        self.assertNotIn('MC-AUX-B', html)
        self.assertNotIn('MC-AUX-RASC', html)

    # ── matrix_buscar_existente ──────────────────────────────────────
    def test_buscar_matriz_existente(self):
        self.client.force_login(self.desup)
        url = reverse('courses:matrix_buscar_existente')

        self.assertEqual(self.client.get(url).json(), {'existe': False})

        curso_sem_matriz = Course.objects.create(nome='Curso Sem Matriz', sigla='CSM')
        self.assertEqual(
            self.client.get(url, {'curso_id': curso_sem_matriz.id}).json(), {'existe': False},
        )

        dados = self.client.get(url, {'curso_id': self.curso.id}).json()
        self.assertTrue(dados['existe'])
        # Devolve a mais recente do curso (maior id).
        self.assertEqual(dados['matriz_id'], self.rascunho_a.pk)

    def test_buscar_matriz_existente_exige_login(self):
        resp = self.client.get(reverse('courses:matrix_buscar_existente'),
                               {'curso_id': self.curso.id})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/login/'))

    # CORRIGIDO (CORR-008 + escopo por unidade): `BuscarMatrizExistenteView` não
    # aplicava NENHUM escopo — nem de unidade, nem de rascunho. Qualquer usuário logado
    # descobria a existência, o id e o nome (via `str(matriz)`) de matrizes de outras
    # unidades e de rascunhos que a DESUP ainda não publicou.
    # Correção: filtro por `unidades=request.user.unidade` e `.exclude(is_rascunho=True)`
    # para quem não é DESUP.
    # Arquivo: project_root/apps/courses/views.py (BuscarMatrizExistenteView).
    def test_buscar_matriz_existente_respeita_unidade_e_rascunho(self):
        self.client.force_login(self.coord_b)
        dados = self.client.get(
            reverse('courses:matrix_buscar_existente'), {'curso_id': self.curso.id},
        ).json()
        self.assertFalse(
            dados['existe'],
            'Coordenador da UEB não pode descobrir matrizes/rascunhos do curso da UEA.',
        )

    # ── matrix_dados_copiar ──────────────────────────────────────────
    def test_dados_para_copiar_retornam_componentes_derivados(self):
        self.client.force_login(self.desup)
        resp = self.client.get(
            reverse('courses:matrix_dados_copiar', kwargs={'pk': self.vigente_a.pk})
        )
        self.assertEqual(resp.status_code, 200)
        componentes = resp.json()['componentes']
        self.assertEqual(len(componentes), 2)
        por_codigo = {c['codigo']: c for c in componentes}
        self.assertEqual(por_codigo['E2E001']['componente_curricular'], self.algoritmos.id)
        self.assertEqual(por_codigo['E2E001']['componente_curricular_nome'],
                         'Algoritmos e Programacao')
        self.assertEqual(por_codigo['E2E001']['carga_horaria'], 80)
        self.assertEqual(por_codigo['E2E001']['creditos'], 4)
        self.assertEqual(por_codigo['E2E001']['carga_horaria_semanal'], '4.00')
        self.assertEqual(por_codigo['E2E002']['carga_horaria'], 60)

    def test_dados_para_copiar_de_outra_unidade_dao_404(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(
            reverse('courses:matrix_dados_copiar', kwargs={'pk': self.vigente_b.pk})
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {'componentes': []})

    def test_dados_para_copiar_sem_unidade_dao_403(self):
        sem_unidade = User.objects.create_user(
            email='coord_sem_unid_aux@teste.com', perfil='COORDENADOR_UNIDADE',
            forcar_troca_senha=False,
        )
        self.client.force_login(sem_unidade)
        resp = self.client.get(
            reverse('courses:matrix_dados_copiar', kwargs={'pk': self.vigente_a.pk})
        )
        self.assertEqual(resp.status_code, 403)

    # CORRIGIDO (CORR-008): `DadosMatrizCopiarView` escopava por unidade, mas não
    # excluía rascunhos — o coordenador da UEA lia a composição completa de um rascunho
    # que a DESUP ainda não publicou (o detalhe da mesma matriz devolve 404 para ele).
    # Arquivo: project_root/apps/courses/views.py (DadosMatrizCopiarView).
    def test_dados_para_copiar_de_rascunho_negado_para_a_unidade(self):
        self.client.force_login(self.coord_a)
        resp = self.client.get(
            reverse('courses:matrix_dados_copiar', kwargs={'pk': self.rascunho_a.pk})
        )
        self.assertEqual(resp.status_code, 404)

    # ── matrix_add_row ───────────────────────────────────────────────
    def test_add_row_exige_htmx_e_login(self):
        resp = self.client.get(reverse('courses:matrix_add_row'))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith('/login/'))

        self.client.force_login(self.desup)
        self.assertEqual(self.client.get(reverse('courses:matrix_add_row')).status_code, 400)

    def test_add_row_usa_o_indice_pedido_no_prefixo_dos_campos(self):
        self.client.force_login(self.desup)
        resp = self.client.get(reverse('courses:matrix_add_row'),
                               {'prefix': PREFIXO, 'row_index': '3'}, headers=HX)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-row-index="3"', html)
        self.assertIn('name="componentes-3-periodo"', html)
        # CORR-007: os campos derivados continuam bloqueados também na linha nova.
        self.assertIn('disabled', tag_do_campo(html, 'componentes-3-carga_horaria'))
        self.assertIn('disabled', tag_do_campo(html, 'componentes-3-creditos'))

    # CORRIGIDO: o template `courses/matrix/partials/_formset_row.html` renderizava
    # `{{ form_row.disciplina_nome }}`, campo que não existe mais em
    # `MatrixComponentForm` (hoje o campo é `componente_curricular`). Como o Django
    # silencia atributos inexistentes no template, a linha voltava SEM o seletor de
    # disciplina — o endpoint devolvia uma linha impossível de preencher e o POST
    # cairia em "componente_curricular obrigatório".
    # Correção: o parcial passou a renderizar o hidden `componente_curricular` + o
    # input de busca `.cc-search-input`, igual ao matrix_form.html.
    # Arquivo: project_root/templates/courses/matrix/partials/_formset_row.html
    # Obs.: o mesmo template é usado por `courses:matrix_import_previous`.
    def test_add_row_devolve_o_seletor_de_disciplina(self):
        self.client.force_login(self.desup)
        html = self.client.get(
            reverse('courses:matrix_add_row'), {'prefix': PREFIXO, 'row_index': '0'}, headers=HX,
        ).content.decode()
        self.assertIn('name="componentes-0-componente_curricular"', html)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 7 — Formset da matriz pela tela (mínimo, múltiplos, remoção)
# ══════════════════════════════════════════════════════════════════════════════

class FormsetMatrizE2ETests(BaseCoursesE2ETests):
    """min_num=1, publicação com vários componentes e remoção via DELETE — via HTTP."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.desup)

    def test_publicar_matriz_com_tres_componentes(self):
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a, self.unidade_b], nome='MC-MULTI',
            linhas=[
                linha_componente(self.algoritmos, '1º Semestre'),
                linha_componente(self.estrutura, '2º Semestre'),
                linha_componente(self.calculo, '3º Semestre'),
            ],
        ))
        self.assertEqual(resp.status_code, 302, resp.content[:400])

        matriz = CurriculumMatrix.objects.get(nome='MC-MULTI')
        self.assertTrue(matriz.is_vigente)
        self.assertEqual(matriz.componentes_da_matriz.count(), 3)
        self.assertEqual(
            {u.sigla for u in matriz.unidades.all()}, {'UEA', 'UEB'},
        )
        derivados = {
            c.codigo: (c.carga_horaria, c.creditos, c.carga_horaria_semanal, c.periodo)
            for c in matriz.componentes_da_matriz.all()
        }
        self.assertEqual(derivados['E2E001'], (80, 4, Decimal('4'), '1º Semestre'))
        self.assertEqual(derivados['E2E002'], (60, 3, Decimal('3'), '2º Semestre'))
        self.assertEqual(derivados['E2E003'], (90, 4, Decimal('4.5'), '3º Semestre'))

        # CH total agregada aparece na listagem (80 + 60 + 90 = 230).
        resp = self.client.get(reverse('courses:matrix_list'), {'status': 'vigente'})
        linha = [m for m in resp.context['matrices'] if m.pk == matriz.pk][0]
        self.assertEqual(linha.qtd_componentes, 3)
        self.assertEqual(linha.ch_total, 230)

    def test_matriz_sem_nenhum_componente_e_recusada(self):
        """min_num=1 + validate_min: a matriz não pode ser criada vazia."""
        antes = CurriculumMatrix.objects.count()
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-VAZIA', linhas=[],
        ))
        self.assertEqual(resp.status_code, 200, 'Deveria re-renderizar o formulário com erro.')
        self.assertTrue(resp.context['component_formset'].non_form_errors())
        self.assertEqual(CurriculumMatrix.objects.count(), antes)
        self.assertFalse(CurriculumMatrix.objects.filter(nome='MC-VAZIA').exists())

    def test_matriz_com_linha_em_branco_e_recusada(self):
        """Publicar sem tocar nas linhas extras (o browser envia o status default) barra."""
        antes = CurriculumMatrix.objects.count()
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-BRANCO',
            linhas=[{
                'componente_curricular': '',
                'periodo': '',
                'status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            }],
        ))
        self.assertEqual(resp.status_code, 200)
        # Linha intocada = formulário vazio → cai no validate_min do formset.
        self.assertTrue(resp.context['component_formset'].non_form_errors())
        self.assertEqual(CurriculumMatrix.objects.count(), antes)

    def test_matriz_com_linha_pela_metade_e_recusada(self):
        """Preencheu só o período e mandou publicar: o erro é da linha (disciplina)."""
        antes = CurriculumMatrix.objects.count()
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-METADE',
            linhas=[{
                'componente_curricular': '',
                'periodo': '1º Semestre',
                'status': MatrixComponent.StatusChoices.SEM_PROFESSOR,
            }],
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('componente_curricular', resp.context['component_formset'].errors[0])
        self.assertEqual(CurriculumMatrix.objects.count(), antes)

    def test_remover_todos_os_componentes_na_edicao_e_recusado(self):
        """Marcar DELETE em todas as linhas deixaria a matriz vazia — validate_min barra."""
        self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-DEL-TUDO',
            linhas=[linha_componente(self.algoritmos)], rascunho=True,
        ))
        matriz = CurriculumMatrix.objects.get(nome='MC-DEL-TUDO')
        comp = matriz.componentes_da_matriz.get()

        resp = self.client.post(
            reverse('courses:matrix_update', kwargs={'pk': matriz.pk}),
            data=payload_matriz(
                curso=self.curso, unidades=[self.unidade_a], nome='MC-DEL-TUDO',
                linhas=[linha_componente(self.algoritmos, id=comp.pk, DELETE='on')],
                rascunho=True, initial_forms=1,
            ),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['component_formset'].non_form_errors())
        self.assertEqual(matriz.componentes_da_matriz.count(), 1)

    def test_disciplina_repetida_na_mesma_matriz_e_recusada(self):
        """unique_together (matriz, componente_curricular) barra duplicidade."""
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-DUP',
            linhas=[
                linha_componente(self.algoritmos, '1º Semestre'),
                linha_componente(self.algoritmos, '2º Semestre'),
            ],
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['component_formset'].non_form_errors())
        self.assertFalse(CurriculumMatrix.objects.filter(nome='MC-DUP').exists())

    def _trocar_disciplina_do_rascunho(self):
        """Cria um rascunho com Algoritmos (80h) e troca a linha para Banco (40h)."""
        self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-TROCA',
            linhas=[linha_componente(self.algoritmos)], rascunho=True,
        ))
        matriz = CurriculumMatrix.objects.get(nome='MC-TROCA')
        comp = matriz.componentes_da_matriz.get()

        self.client.post(
            reverse('courses:matrix_update', kwargs={'pk': matriz.pk}),
            data=payload_matriz(
                curso=self.curso, unidades=[self.unidade_a], nome='MC-TROCA',
                linhas=[linha_componente(self.banco, '4º Semestre', id=comp.pk)],
                rascunho=True, initial_forms=1,
            ),
        )
        comp.refresh_from_db()
        return comp

    def test_troca_de_disciplina_na_edicao_grava_disciplina_periodo_e_codigo(self):
        """A troca de disciplina é aceita: disciplina, período e código acompanham."""
        comp = self._trocar_disciplina_do_rascunho()
        self.assertEqual(comp.componente_curricular_id, self.banco.id)
        self.assertEqual(comp.periodo, '4º Semestre')
        self.assertEqual(comp.codigo, 'E2E004')   # código da NOVA disciplina

    # CORRIGIDO (regressão da CORR-007): ao TROCAR a disciplina de uma linha existente,
    # o `MatrixComponentForm.clean()` atualizava o `codigo` para o da nova disciplina,
    # mas mantinha a CH (e, por consequência, créditos e CH semanal) da disciplina
    # ANTIGA — o `if ch is None` só caía na CH padrão quando não havia valor gravado, e
    # na edição sempre há (o campo é `disabled`, então o valor vem do instance).
    # Resultado: a linha ficava inconsistente — código/nome de "Banco de Dados" (40h)
    # com carga horária 80h e 4 créditos, herdados de "Algoritmos e Programacao".
    # Correção: o `clean()` re-deriva a CH de `cc.carga_horaria_padrao` sempre que a
    # disciplina da linha muda; a CH gravada só é preservada quando ela não muda
    # (matriz legada com CH fora do padrão — ver
    # AdulteracaoDeCamposBloqueadosE2ETests.test_post_forjado_na_edicao_preserva_a_ch_ja_gravada).
    # Arquivo: project_root/apps/courses/forms.py (MatrixComponentForm.clean).
    def test_troca_de_disciplina_na_edicao_redriva_a_carga_horaria(self):
        comp = self._trocar_disciplina_do_rascunho()
        self.assertEqual(comp.carga_horaria, 40)                  # CH padrão de Banco
        self.assertEqual(comp.creditos, 2)                        # 40 // 20
        self.assertEqual(comp.carga_horaria_semanal, Decimal('2'))


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 8 — Adulteração de POST nos campos bloqueados (CORR-007) pela tela
# ══════════════════════════════════════════════════════════════════════════════

class AdulteracaoDeCamposBloqueadosE2ETests(BaseCoursesE2ETests):
    """Os campos derivados são `disabled`: o valor do POST é descartado pelo servidor."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.desup)

    def test_formulario_renderiza_os_campos_derivados_bloqueados(self):
        html = self.client.get(reverse('courses:matrix_create')).content.decode()
        for campo in ('codigo', 'carga_horaria', 'creditos', 'carga_horaria_semanal'):
            with self.subTest(campo=campo):
                tag = tag_do_campo(html, f'componentes-0-{campo}')
                self.assertTrue(tag, f'Campo {campo} não foi renderizado.')
                self.assertIn('disabled', tag)
        # Disciplina e período seguem editáveis.
        self.assertNotIn('disabled', tag_do_campo(html, 'componentes-0-componente_curricular'))
        self.assertNotIn('disabled', tag_do_campo(html, 'componentes-0-periodo'))

    def test_post_forjado_na_criacao_nao_altera_os_derivados(self):
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-HACK',
            linhas=[linha_componente(
                self.estrutura, '1º Semestre',
                codigo='HACKED', carga_horaria=999, creditos=99, carga_horaria_semanal=777,
            )],
        ))
        self.assertEqual(resp.status_code, 302, resp.content[:400])

        comp = CurriculumMatrix.objects.get(nome='MC-HACK').componentes_da_matriz.get()
        self.assertEqual(comp.codigo, 'E2E002')                      # não 'HACKED'
        self.assertEqual(comp.carga_horaria, 60)                     # não 999
        self.assertEqual(comp.creditos, 3)                           # não 99
        self.assertEqual(comp.carga_horaria_semanal, Decimal('3'))   # não 777

    def test_post_forjado_na_edicao_preserva_a_ch_ja_gravada(self):
        matriz = self.criar_matriz(nome='MC-HACK-EDIT', vigente=False, rascunho=True)
        comp = MatrixComponent.objects.create(
            matriz=matriz,
            componente_curricular=self.algoritmos,
            periodo='1º Semestre',
            carga_horaria=60,     # legado, diferente da CH padrão (80)
            creditos=3,
        )
        resp = self.client.post(
            reverse('courses:matrix_update', kwargs={'pk': matriz.pk}),
            data=payload_matriz(
                curso=self.curso, unidades=[self.unidade_a], nome='MC-HACK-EDIT',
                linhas=[linha_componente(
                    self.algoritmos, '2º Semestre', id=comp.pk,
                    carga_horaria=999, creditos=99, codigo='HACKED',
                )],
                rascunho=True, initial_forms=1,
            ),
        )
        self.assertEqual(resp.status_code, 302, resp.content[:400])

        comp.refresh_from_db()
        self.assertEqual(comp.carga_horaria, 60)   # nem 999 nem 80
        self.assertEqual(comp.creditos, 3)
        self.assertEqual(comp.codigo, 'E2E001')
        self.assertEqual(comp.periodo, '2º Semestre')   # período é editável, esse muda

    def test_post_forjado_no_componente_curricular_respeita_o_catalogo(self):
        """Disciplina inexistente no catálogo é recusada (não cria matriz órfã)."""
        resp = self.client.post(reverse('courses:matrix_create'), data=payload_matriz(
            curso=self.curso, unidades=[self.unidade_a], nome='MC-FANTASMA',
            linhas=[{'componente_curricular': '999999', 'periodo': '1º Semestre',
                     'status': MatrixComponent.StatusChoices.SEM_PROFESSOR}],
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(CurriculumMatrix.objects.filter(nome='MC-FANTASMA').exists())
