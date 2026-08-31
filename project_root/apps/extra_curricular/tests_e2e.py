"""
Testes END-TO-END do app `extra_curricular`.

Diferente de `tests.py` (que cobre unidades isoladas: cálculo de `ch_aprovada`,
tokens de filtro, matriz de pareceres), aqui o foco são as **jornadas completas**
dos dois perfis operacionais, passando pelas mesmas rotas HTTP que a tela usa:

    COORDENADOR_UNIDADE  →  cria a pendência, adiciona justificativas (TCC,
                            extensão e redução), informa o SEI e envia à DESUP.
    DESUP                →  emite parecer item a item, consolida/reabre e avisa
                            a unidade.

Convenções destes testes:
  · toda escrita da unidade exige janela de entrega aberta (`JanelaEntrega`);
    a DESUP passa por cima (bypass) — ver `apps.core.services`;
  · a pendência vive no `semestre_atual()`, que é o escopo usado por
    `Professor.ch_justificada`;
  · nada é criado direto no ORM quando existe rota para fazer aquilo — o objetivo
    é exercitar o caminho real do usuário.

Os testes comentados com `# CORRIGIDO` nasceram marcados como
`@unittest.expectedFailure` + `# BUG-CANDIDATO`: a asserção já estava no nível
certo (o esperado pelo negócio) e o teste não quebrava a suíte enquanto o bug
não fosse corrigido. Com a correção aplicada eles viraram testes de regressão
comuns — o comentário preserva a causa-raiz para quem mexer no código depois.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import JanelaEntrega, Notificacao, Unidade
from apps.extra_curricular.models import (
    AtividadeExtensionista,
    OrientacaoTCC,
    ParecerChoices,
    PendenciaExtra,
    ReducaoCargaHoraria,
)
from apps.extra_curricular.utils import semestre_atual
from apps.professors.models import ContractType, Professor


# ══════════════════════════════════════════════════════════════════════════════
# Base comum — duas unidades, dois coordenadores, uma DESUP e janela aberta
# ══════════════════════════════════════════════════════════════════════════════
class _BaseFluxoE2E(TestCase):
    """Cenário base compartilhado pelas jornadas.

    Unidade A (com coordenador A) é onde as jornadas acontecem; a Unidade B
    existe para provar o isolamento entre unidades.
    """

    def setUp(self):
        self.client = Client()
        self.semestre = semestre_atual()

        self.unidade_a = Unidade.objects.create(nome="Unidade Alfa E2E", sigla="UAE")
        self.unidade_b = Unidade.objects.create(nome="Unidade Beta E2E", sigla="UBE")

        self.contrato = ContractType.objects.create(
            nome="Ensino Superior E2E",
            max_class_hours=20,
            max_total_hours=40,
            max_classes=10,
        )

        self.prof_a = self._professor("Ana Alfa", "a", self.unidade_a)
        self.prof_a2 = self._professor("Bruno Alfa", "a2", self.unidade_a)
        self.prof_b = self._professor("Carla Beta", "b", self.unidade_b)

        self.coord_a = User.objects.create_user(
            email="coord_a_e2e@teste.com",
            perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade_a,
            forcar_troca_senha=False,
        )
        self.coord_b = User.objects.create_user(
            email="coord_b_e2e@teste.com",
            perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade_b,
            forcar_troca_senha=False,
        )
        self.desup = User.objects.create_user(
            email="desup_e2e@teste.com",
            perfil="DESUP",
            forcar_troca_senha=False,
        )

        self.janela = self._abrir_janela()

    # ── Fábricas ────────────────────────────────────────────────────
    def _professor(self, nome, sufixo, unidade, contrato=None):
        return Professor.objects.create(
            rh_nome=nome,
            rh_email=f"prof_{sufixo}_e2e@teste.com",
            id_funcional=f"E2E-ID-{sufixo}",
            rh_matricula=f"E2E-MAT-{sufixo}",
            unidade_principal=unidade,
            tipo_contrato=contrato or self.contrato,
        )

    def _abrir_janela(self, unidade=None):
        hoje = timezone.now().date()
        return JanelaEntrega.objects.create(
            semestre=self.semestre,
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje + timedelta(days=30),
            status=JanelaEntrega.StatusChoices.ABERTO,
            unidade=unidade,
        )

    # ── Helpers de request ──────────────────────────────────────────
    @staticmethod
    def _mensagens(resp):
        return [m.message for m in get_messages(resp.wsgi_request)]

    def _login(self, user):
        self.client.force_login(user)

    # ── POST dos formsets do detalhe (rotas salvar_*) ───────────────
    def _post_tcc(self, pendencia, orientandos, initial=0, extras=None):
        dados = {
            "tcc-TOTAL_FORMS": str(len(orientandos)),
            "tcc-INITIAL_FORMS": str(initial),
            "tcc-MIN_NUM_FORMS": "0",
            "tcc-MAX_NUM_FORMS": "1000",
        }
        for i, num in enumerate(orientandos):
            dados[f"tcc-{i}-num_orientandos"] = str(num)
            dados[f"tcc-{i}-id"] = ""
        dados.update(extras or {})
        return self.client.post(
            reverse("extra_curricular:salvar_tcc", kwargs={"pk": pendencia.pk}), dados
        )

    def _post_extensao(self, pendencia, estudantes, initial=0, extras=None):
        dados = {
            "ext-TOTAL_FORMS": str(len(estudantes)),
            "ext-INITIAL_FORMS": str(initial),
            "ext-MIN_NUM_FORMS": "0",
            "ext-MAX_NUM_FORMS": "1000",
        }
        for i, num in enumerate(estudantes):
            dados[f"ext-{i}-num_estudantes"] = str(num)
            dados[f"ext-{i}-id"] = ""
        dados.update(extras or {})
        return self.client.post(
            reverse("extra_curricular:salvar_extensao", kwargs={"pk": pendencia.pk}), dados
        )

    def _post_reducao(self, pendencia, reducoes, initial=0, extras=None):
        dados = {
            "red-TOTAL_FORMS": str(len(reducoes)),
            "red-INITIAL_FORMS": str(initial),
            "red-MIN_NUM_FORMS": "0",
            "red-MAX_NUM_FORMS": "1000",
        }
        for i, (motivo, horas) in enumerate(reducoes):
            dados[f"red-{i}-motivo_reducao"] = motivo
            dados[f"red-{i}-horas_reduzidas"] = str(horas)
            dados[f"red-{i}-id"] = ""
        dados.update(extras or {})
        return self.client.post(
            reverse("extra_curricular:salvar_reducao", kwargs={"pk": pendencia.pk}), dados
        )

    # ── POST de parecer da DESUP ────────────────────────────────────
    def _post_parecer(self, tipo, pendencia, item, parecer, aprovados=None, motivo=""):
        rotas = {
            "tcc": ("extra_curricular:parecer_tcc", "ptcc", "num_orientandos_aprovados"),
            "ext": ("extra_curricular:parecer_extensao", "pext", "num_estudantes_aprovados"),
            "red": ("extra_curricular:parecer_reducao", "pred", None),
        }
        url_name, prefixo, campo_aprovados = rotas[tipo]
        url = reverse(url_name, kwargs={"pk": pendencia.pk, "item_pk": item.pk})
        p = f"{prefixo}-{item.pk}"
        dados = {
            f"{p}-parecer_desup": parecer,
            f"{p}-motivo_parecer": motivo,
            f"{p}-horas_aprovadas": (
                "" if (campo_aprovados or aprovados is None) else str(aprovados)
            ),
        }
        if campo_aprovados:
            dados[f"{p}-{campo_aprovados}"] = "" if aprovados is None else str(aprovados)
        return self.client.post(url, dados)

    # ── Atalho: pendência já criada pela rota do coordenador ────────
    def _criar_pendencia_pela_rota(self, professores, user=None):
        self._login(user or self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:pendencia_create"),
            {"professor_id": [str(p.pk) for p in professores]},
        )
        return resp


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 1 e 2 — jornada completa (deferimento e indeferimento)
# ══════════════════════════════════════════════════════════════════════════════
class CicloCompletoUnidadeDesupTests(_BaseFluxoE2E):
    """Da criação da pendência pela unidade até a CH justificada do professor."""

    def test_ciclo_feliz_da_criacao_ate_ch_justificada(self):
        """Jornada completa: unidade cria → 3 justificativas → SEI → envio →
        DESUP defere item a item → status consolida APROVADO → CH do professor
        passa a refletir as horas APROVADAS (não as solicitadas)."""
        # ── 1. Unidade abre a tela de criação e cria a pendência ─────
        self._login(self.coord_a)
        tela = self.client.get(reverse("extra_curricular:pendencia_create"))
        self.assertEqual(tela.status_code, 200)
        self.assertIn(self.prof_a, list(tela.context["professores"]))

        resp = self._criar_pendencia_pela_rota([self.prof_a])
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("extra_curricular:pendencia_lote"), resp.url)

        pendencia = PendenciaExtra.objects.get(professor=self.prof_a, semestre=self.semestre)
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)
        self.assertEqual(pendencia.unidade, self.unidade_a)
        self.assertEqual(pendencia.criado_por, self.coord_a)

        # ── 2. Unidade adiciona TCC + Extensão + Redução ─────────────
        self.assertEqual(self._post_tcc(pendencia, [4]).status_code, 302)
        self.assertEqual(self._post_extensao(pendencia, [10]).status_code, 302)
        self.assertEqual(
            self._post_reducao(pendencia, [("Coordenação de curso — Portaria 12", "3.0")]).status_code,
            302,
        )

        tcc = OrientacaoTCC.objects.get(pendencia=pendencia)
        ext = AtividadeExtensionista.objects.get(pendencia=pendencia)
        red = ReducaoCargaHoraria.objects.get(pendencia=pendencia)
        self.assertEqual(float(tcc.carga_horaria), 2.0)      # 4 × 0,5h
        self.assertEqual(float(ext.carga_horaria), 5.0)      # 10 × 0,5h
        self.assertEqual(float(red.horas_reduzidas), 3.0)
        # Ainda em rascunho: nada bloqueado e nada contabilizado.
        self.assertFalse(any(i.bloqueado for i in (tcc, ext, red)))
        self.assertEqual(pendencia.ch_total_justificada, 0.0)

        # ── 3. Unidade informa o SEI ─────────────────────────────────
        resp_sei = self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk}),
            {"sei_numero": "SEI-123456/654321/2026"},
        )
        self.assertEqual(resp_sei.status_code, 302)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.sei_numero, "SEI-123456/654321/2026")

        # ── 4. Unidade envia para a DESUP ────────────────────────────
        resp_envio = self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": pendencia.pk})
        )
        self.assertEqual(resp_envio.status_code, 302)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        for item in (tcc, ext, red):
            item.refresh_from_db()
            self.assertTrue(item.bloqueado, f"{item} deveria estar travado após o envio")

        # ── 5. DESUP emite parecer item a item ───────────────────────
        self._login(self.desup)
        self.assertEqual(
            self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=4).status_code,
            302,
        )
        pendencia.refresh_from_db()
        self.assertEqual(
            pendencia.status,
            PendenciaExtra.StatusChoices.ENVIADO,
            "Com itens ainda pendentes a pendência não pode ser finalizada",
        )

        self.assertEqual(
            self._post_parecer("ext", pendencia, ext, ParecerChoices.APROVADO, aprovados=8).status_code,
            302,
        )
        self.assertEqual(
            self._post_parecer(
                "red", pendencia, red, ParecerChoices.APROVADO, aprovados="2.5"
            ).status_code,
            302,
        )

        # ── 6. Status consolidado em APROVADO ────────────────────────
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)

        # ── 7. CH do professor reflete as horas APROVADAS ────────────
        tcc.refresh_from_db(); ext.refresh_from_db(); red.refresh_from_db()
        self.assertEqual(tcc.ch_aprovada, 2.0)   # 4 orientandos aprovados
        self.assertEqual(ext.ch_aprovada, 4.0)   # 8 estudantes aprovados (pediu 10)
        self.assertEqual(red.ch_aprovada, 2.5)   # 2,5h aprovadas (pediu 3h)
        self.assertAlmostEqual(pendencia.ch_total_justificada, 8.5)

        self.prof_a.refresh_from_db()
        self.assertAlmostEqual(self.prof_a.ch_justificada, 8.5)
        # Limite efetivo = 20h de sala − 0h alocada; sobram 11,5h.
        self.assertAlmostEqual(pendencia.ch_faltante, 11.5)

        # ── 8. A DESUP consolida com o motivo geral (botão Finalizar) ─
        resp_final = self.client.post(
            reverse("extra_curricular:atualizar_status", kwargs={"pk": pendencia.pk}),
            {"motivo_status_desup": "Deferido conforme Resolução CNE/CES nº 7."},
        )
        self.assertEqual(resp_final.status_code, 302)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.assertEqual(
            pendencia.motivo_status_desup, "Deferido conforme Resolução CNE/CES nº 7."
        )

        # ── 9. A listagem da DESUP mostra as 3 linhas como finalizadas ─
        lista = self.client.get(
            reverse("extra_curricular:pendencia_list"),
            {"semestre": self.semestre, "unidade_id": self.unidade_a.pk},
        )
        linhas = [l for l in lista.context["pendencias_data"] if l["professor"].pk == self.prof_a.pk]
        self.assertEqual(len(linhas), 3)
        self.assertEqual({l["status_token"] for l in linhas}, {"finalizado"})
        self.assertAlmostEqual(sum(float(l["ch_justificada"]) for l in linhas), 8.5)

    def test_ciclo_com_indeferimento_afeta_status_e_ch(self):
        """Mesma jornada, mas a DESUP indefere um dos itens.

        CORR-023: o resultado misto consolida em PARCIAL e a CH do item DEFERIDO
        continua contando — antes, um único indeferimento derrubava o agregado
        para INDEFERIDO e zerava tudo, inclusive o que a DESUP tinha aprovado.
        """
        self._criar_pendencia_pela_rota([self.prof_a])
        pendencia = PendenciaExtra.objects.get(professor=self.prof_a, semestre=self.semestre)

        self._post_tcc(pendencia, [4])
        self._post_extensao(pendencia, [6])
        tcc = OrientacaoTCC.objects.get(pendencia=pendencia)
        ext = AtividadeExtensionista.objects.get(pendencia=pendencia)

        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk}),
            {"sei_numero": "SEI-222222/222222/2026"},
        )
        self.client.post(reverse("extra_curricular:enviar_desup", kwargs={"pk": pendencia.pk}))

        # DESUP defere o TCC e indefere a extensão.
        self._login(self.desup)
        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=4)
        resp = self._post_parecer(
            "ext",
            pendencia,
            ext,
            ParecerChoices.INDEFERIDO,
            motivo="Atividade já prevista na matriz curricular.",
        )
        self.assertEqual(resp.status_code, 302)

        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)
        # O TCC deferido (4 orientandos = 2,0h) conta; a extensão indeferida, não.
        self.assertEqual(pendencia.ch_total_justificada, 2.0)
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 2.0)

        ext.refresh_from_db()
        self.assertEqual(ext.motivo_parecer, "Atividade já prevista na matriz curricular.")

        # A tela mostra a linha indeferida sem CH justificada.
        lista = self.client.get(
            reverse("extra_curricular:pendencia_list"),
            {"semestre": self.semestre, "unidade_id": self.unidade_a.pk},
        )
        tokens = {
            l["status_token"]
            for l in lista.context["pendencias_data"]
            if l["professor"].pk == self.prof_a.pk
        }
        self.assertEqual(tokens, {"finalizado", "indeferido"})

    def test_desup_reverte_indeferimento_e_pendencia_volta_a_aprovado(self):
        """A DESUP pode reavaliar um item indeferido; ao deferir todos, o
        agregado volta a APROVADO e a CH volta a contar."""
        self._criar_pendencia_pela_rota([self.prof_a])
        pendencia = PendenciaExtra.objects.get(professor=self.prof_a, semestre=self.semestre)
        self._post_tcc(pendencia, [2])
        tcc = OrientacaoTCC.objects.get(pendencia=pendencia)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk}),
            {"sei_numero": "SEI-333333/333333/2026"},
        )
        self.client.post(reverse("extra_curricular:enviar_desup", kwargs={"pk": pendencia.pk}))

        self._login(self.desup)
        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.INDEFERIDO, motivo="Sem PPC")
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.INDEFERIDO)

        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=2, motivo="PPC apresentado")
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.assertEqual(pendencia.ch_total_justificada, 1.0)

    def test_item_incluido_depois_da_aprovacao_nao_conta_sem_parecer(self):
        # CORRIGIDO: `PendenciaExtra.ch_total_justificada` testava só o status do
        # CABEÇALHO e somava `ch_aprovada` de TODOS os itens — inclusive PENDENTE
        # e INDEFERIDO. Como o `save()` dos models copia o valor solicitado para
        # `horas_aprovadas`, uma justificativa incluída depois da aprovação
        # (o cabeçalho segue APROVADO até a próxima consolidação) passava a
        # contar como CH aprovada na hora, sem nenhum parecer da DESUP.
        # REPRO: TCC aprovado = 1,0h → a unidade posta uma redução de 10h →
        #        `ch_total_justificada` virava 11,0h.
        self._criar_pendencia_pela_rota([self.prof_a])
        pendencia = PendenciaExtra.objects.get(professor=self.prof_a, semestre=self.semestre)
        self._post_tcc(pendencia, [2])
        tcc = OrientacaoTCC.objects.get(pendencia=pendencia)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk}),
            {"sei_numero": "SEI-191919/191919/2026"},
        )
        self.client.post(reverse("extra_curricular:enviar_desup", kwargs={"pk": pendencia.pk}))

        self._login(self.desup)
        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=2)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.assertEqual(pendencia.ch_total_justificada, 1.0)

        # A unidade inclui uma redução de 10h DEPOIS da aprovação.
        self._login(self.coord_a)
        resp = self._post_reducao(pendencia, [("Portaria posterior ao parecer", "10.0")])
        self.assertEqual(resp.status_code, 302)
        red = ReducaoCargaHoraria.objects.get(pendencia=pendencia)
        self.assertEqual(red.parecer_desup, ParecerChoices.PENDENTE)

        # O cabeçalho ainda está APROVADO (só reconsolida no próximo parecer),
        # mas o item novo não tem parecer nenhum: não pode entrar na conta.
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.ch_total_justificada, 1.0)
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 3 — reabertura pela DESUP
# ══════════════════════════════════════════════════════════════════════════════
class ReaberturaFluxoCompletoTests(_BaseFluxoE2E):
    """Jornada de reabertura: finalizada → reaberta → reavaliada → finalizada."""

    def _pendencia_finalizada(self):
        self._criar_pendencia_pela_rota([self.prof_a])
        pendencia = PendenciaExtra.objects.get(professor=self.prof_a, semestre=self.semestre)
        self._post_tcc(pendencia, [4])
        tcc = OrientacaoTCC.objects.get(pendencia=pendencia)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": pendencia.pk}),
            {"sei_numero": "SEI-444444/444444/2026"},
        )
        self.client.post(reverse("extra_curricular:enviar_desup", kwargs={"pk": pendencia.pk}))
        self._login(self.desup)
        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=4)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        return pendencia, tcc

    def test_reabertura_completa_ate_nova_aprovacao(self):
        """Reabrir volta a ENVIADO e zera a contagem; ao deferir de novo (com
        menos horas), a CH do professor passa a refletir o novo valor."""
        pendencia, tcc = self._pendencia_finalizada()
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 2.0)

        # DESUP reabre.
        resp = self.client.post(
            reverse("extra_curricular:reabrir_pendencia", kwargs={"pk": pendencia.pk})
        )
        self.assertEqual(resp.status_code, 302)
        pendencia.refresh_from_db()
        tcc.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)

        # A CH aprovada deixa de contar enquanto não houver nova aprovação.
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 0.0)
        self.assertEqual(pendencia.ch_total_justificada, 0.0)
        lista = self.client.get(
            reverse("extra_curricular:pendencia_list"),
            {"semestre": self.semestre, "unidade_id": self.unidade_a.pk},
        )
        linha = [
            l for l in lista.context["pendencias_data"] if l["professor"].pk == self.prof_a.pk
        ][0]
        self.assertEqual(linha["ch_justificada"], 0)
        self.assertEqual(linha["status_token"], "pendente")

        # Nova avaliação, agora com menos horas.
        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=1)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 0.5)

    def test_apos_reabertura_unidade_volta_a_incluir_justificativa(self):
        """Depois da reabertura a unidade consegue editar de novo: adicionar uma
        nova justificativa volta a ser possível (e o novo item entra PENDENTE,
        segurando o agregado até a DESUP avaliar)."""
        pendencia, tcc = self._pendencia_finalizada()
        self.client.post(reverse("extra_curricular:reabrir_pendencia", kwargs={"pk": pendencia.pk}))

        self._login(self.coord_a)
        resp = self._post_extensao(pendencia, [6])
        self.assertEqual(resp.status_code, 302)
        ext = AtividadeExtensionista.objects.get(pendencia=pendencia)
        self.assertFalse(ext.bloqueado, "Item novo, ainda não enviado, não pode nascer travado")

        # O item antigo continua travado (foi enviado em definitivo).
        tcc.refresh_from_db()
        self.assertTrue(tcc.bloqueado)
        resp_del = self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": pendencia.pk, "tipo": "tcc", "item_pk": tcc.pk},
            )
        )
        self.assertEqual(resp_del.status_code, 302)
        self.assertTrue(OrientacaoTCC.objects.filter(pk=tcc.pk).exists())
        self.assertTrue(
            any("enviada em definitivo" in m for m in self._mensagens(resp_del))
        )

        # DESUP defere os dois e a pendência finaliza de novo.
        self._login(self.desup)
        self._post_parecer("tcc", pendencia, tcc, ParecerChoices.APROVADO, aprovados=4)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self._post_parecer("ext", pendencia, ext, ParecerChoices.APROVADO, aprovados=6)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.prof_a.refresh_from_db()
        self.assertAlmostEqual(self.prof_a.ch_justificada, 2.0 + 3.0)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 4 — mesa de trabalho em lote (fluxo do dia a dia da unidade)
# ══════════════════════════════════════════════════════════════════════════════
class FluxoLoteUnidadeTests(_BaseFluxoE2E):
    """Jornada em lote: dois docentes de uma vez, do rascunho ao envio."""

    def _ids(self, *professores):
        return ",".join(str(p.pk) for p in professores)

    def test_jornada_em_lote_dois_docentes(self):
        resp = self._criar_pendencia_pela_rota([self.prof_a, self.prof_a2])
        ids = self._ids(self.prof_a, self.prof_a2)
        self.assertEqual(
            resp.url, f"{reverse('extra_curricular:pendencia_lote')}?ids={ids}"
        )

        # ── Mesa de trabalho carrega os dois docentes ────────────────
        mesa = self.client.get(reverse("extra_curricular:pendencia_lote"), {"ids": ids})
        self.assertEqual(mesa.status_code, 200)
        self.assertEqual(
            {p.pk for p in mesa.context["professores"]}, {self.prof_a.pk, self.prof_a2.pk}
        )

        pend_a = PendenciaExtra.objects.get(professor=self.prof_a, semestre=self.semestre)
        pend_a2 = PendenciaExtra.objects.get(professor=self.prof_a2, semestre=self.semestre)

        # ── Justificativas pelos endpoints de lote ───────────────────
        r_tcc = self.client.post(
            reverse("extra_curricular:salvar_tcc_lote"),
            {"ids": ids, "pendencia_id": str(pend_a.pk), "num_orientandos": "4"},
        )
        self.assertEqual(r_tcc.status_code, 302)
        self.assertIn("open=tcc", r_tcc.url)

        self.client.post(
            reverse("extra_curricular:salvar_extensao_lote"),
            {"ids": ids, "pendencia_id": str(pend_a2.pk), "num_estudantes": "12"},
        )
        self.client.post(
            reverse("extra_curricular:salvar_reducao_lote"),
            {
                "ids": ids,
                "pendencia_id": str(pend_a2.pk),
                "motivo_reducao": "Chefia de departamento",
                "horas_reduzidas": "2,5",  # vírgula decimal, como vem da tela
            },
        )

        tcc = OrientacaoTCC.objects.get(pendencia=pend_a)
        ext = AtividadeExtensionista.objects.get(pendencia=pend_a2)
        red = ReducaoCargaHoraria.objects.get(pendencia=pend_a2)
        self.assertEqual(float(tcc.carga_horaria), 2.0)
        self.assertEqual(float(ext.carga_horaria), 6.0)
        self.assertEqual(float(red.horas_reduzidas), 2.5)

        # ── Um item é removido antes do envio ────────────────────────
        r_del = self.client.post(
            reverse(
                "extra_curricular:deletar_item_lote",
                kwargs={"tipo": "red", "item_pk": red.pk},
            ),
            {"ids": ids},
        )
        self.assertEqual(r_del.status_code, 302)
        self.assertFalse(ReducaoCargaHoraria.objects.filter(pk=red.pk).exists())

        # ── Envio sem SEI é recusado ─────────────────────────────────
        r_envio = self.client.post(reverse("extra_curricular:enviar_desup_lote"), {"ids": ids})
        self.assertEqual(r_envio.status_code, 302)
        self.assertIn("sei_error=1", r_envio.url)
        for p in (pend_a, pend_a2):
            p.refresh_from_db()
            self.assertEqual(p.status, PendenciaExtra.StatusChoices.RASCUNHO)

        # ── SEI em lote ──────────────────────────────────────────────
        r_sei = self.client.post(
            reverse("extra_curricular:editar_sei_lote"),
            {"ids": ids, "sei_numero": "SEI-555555/555555/2026"},
        )
        self.assertEqual(r_sei.status_code, 302)
        for p in (pend_a, pend_a2):
            p.refresh_from_db()
            self.assertEqual(p.sei_numero, "SEI-555555/555555/2026")

        # ── Envio em lote ────────────────────────────────────────────
        r_envio = self.client.post(reverse("extra_curricular:enviar_desup_lote"), {"ids": ids})
        self.assertEqual(r_envio.status_code, 302)
        self.assertEqual(r_envio.url, reverse("extra_curricular:pendencia_list"))
        for p in (pend_a, pend_a2):
            p.refresh_from_db()
            self.assertEqual(p.status, PendenciaExtra.StatusChoices.ENVIADO)
        tcc.refresh_from_db()
        ext.refresh_from_db()
        self.assertTrue(tcc.bloqueado)
        self.assertTrue(ext.bloqueado)

        # A DESUP é notificada do envio.
        aviso = Notificacao.objects.filter(titulo__contains="Pendência Extracurricular").first()
        self.assertIsNotNone(aviso)
        self.assertIn("2 justificativa(s)", aviso.mensagem)

        # ── DESUP defere tudo pela mesa e ambos finalizam ────────────
        self._login(self.desup)
        self._post_parecer("tcc", pend_a, tcc, ParecerChoices.APROVADO, aprovados=4)
        self._post_parecer("ext", pend_a2, ext, ParecerChoices.APROVADO, aprovados=12)
        for p in (pend_a, pend_a2):
            p.refresh_from_db()
            self.assertEqual(p.status, PendenciaExtra.StatusChoices.APROVADO)
        self.prof_a.refresh_from_db()
        self.prof_a2.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 2.0)
        self.assertEqual(self.prof_a2.ch_justificada, 6.0)

    def test_lote_ignora_pendencia_de_outra_unidade(self):
        """`pendencia_id` de outra unidade não pode ser manipulado pelo lote."""
        PendenciaExtra.objects.create(
            professor=self.prof_b, unidade=self.unidade_b, semestre=self.semestre
        )
        pend_b = PendenciaExtra.objects.get(professor=self.prof_b)

        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:salvar_tcc_lote"),
            {"ids": str(self.prof_b.pk), "pendencia_id": str(pend_b.pk), "num_orientandos": "3"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(OrientacaoTCC.objects.filter(pendencia=pend_b).exists())

    def test_mesa_de_lote_sem_ids_volta_para_a_listagem(self):
        self._login(self.coord_a)
        resp = self.client.get(reverse("extra_curricular:pendencia_lote"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("extra_curricular:pendencia_list"))

    def test_mesa_de_lote_do_coordenador_filtra_docentes_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self.client.get(
            reverse("extra_curricular:pendencia_lote"),
            {"ids": self._ids(self.prof_a, self.prof_b)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({p.pk for p in resp.context["professores"]}, {self.prof_a.pk})

    def test_sei_em_lote_nao_vaza_para_outra_unidade(self):
        """O coordenador A envia o pk do docente da unidade B junto: o SEI só
        pode ser gravado na pendência da própria unidade."""
        PendenciaExtra.objects.create(
            professor=self.prof_b, unidade=self.unidade_b, semestre=self.semestre
        )
        self._criar_pendencia_pela_rota([self.prof_a])
        self.client.post(
            reverse("extra_curricular:editar_sei_lote"),
            {
                "ids": self._ids(self.prof_a, self.prof_b),
                "sei_numero": "SEI-777777/777777/2026",
            },
        )
        pend_b = PendenciaExtra.objects.get(professor=self.prof_b)
        pend_a = PendenciaExtra.objects.get(professor=self.prof_a)
        self.assertEqual(pend_a.sei_numero, "SEI-777777/777777/2026")
        self.assertFalse(pend_b.sei_numero)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 5 — exclusão de item e efeito no total
# ══════════════════════════════════════════════════════════════════════════════
class DeletarItemEfeitoNoTotalTests(_BaseFluxoE2E):
    def setUp(self):
        super().setUp()
        self._criar_pendencia_pela_rota([self.prof_a])
        self.pendencia = PendenciaExtra.objects.get(
            professor=self.prof_a, semestre=self.semestre
        )

    def test_excluir_item_em_rascunho_reduz_o_total_solicitado(self):
        self._post_tcc(self.pendencia, [4])
        self._post_extensao(self.pendencia, [10])
        tcc = OrientacaoTCC.objects.get(pendencia=self.pendencia)
        ext = AtividadeExtensionista.objects.get(pendencia=self.pendencia)

        soma_antes = float(tcc.carga_horaria) + float(ext.carga_horaria)
        self.assertEqual(soma_antes, 7.0)

        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": self.pendencia.pk, "tipo": "ext", "item_pk": ext.pk},
            )
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AtividadeExtensionista.objects.filter(pk=ext.pk).exists())
        self.assertTrue(any("Item removido" in m for m in self._mensagens(resp)))

        restante = sum(
            float(i.carga_horaria) for i in OrientacaoTCC.objects.filter(pendencia=self.pendencia)
        )
        self.assertEqual(restante, 2.0)

    def test_excluir_ultimo_item_pendente_consolida_o_agregado(self):
        """Item aprovado + item pendente (incluído depois do envio): ao excluir
        o pendente, o agregado passa a APROVADO e o total passa a contar."""
        self._post_tcc(self.pendencia, [4])
        tcc = OrientacaoTCC.objects.get(pendencia=self.pendencia)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pendencia.pk}),
            {"sei_numero": "SEI-888888/888888/2026"},
        )
        self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": self.pendencia.pk})
        )
        # Item incluído após o envio: não fica travado.
        self._post_extensao(self.pendencia, [4])
        ext = AtividadeExtensionista.objects.get(pendencia=self.pendencia)
        self.assertFalse(ext.bloqueado)

        self._login(self.desup)
        self._post_parecer("tcc", self.pendencia, tcc, ParecerChoices.APROVADO, aprovados=4)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)

        # A unidade desiste da extensão e a remove.
        self._login(self.coord_a)
        self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": self.pendencia.pk, "tipo": "ext", "item_pk": ext.pk},
            )
        )
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.assertEqual(self.pendencia.ch_total_justificada, 2.0)
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 2.0)

    def test_excluir_item_bloqueado_e_recusado(self):
        self._post_tcc(self.pendencia, [4])
        tcc = OrientacaoTCC.objects.get(pendencia=self.pendencia)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pendencia.pk}),
            {"sei_numero": "SEI-999999/999999/2026"},
        )
        self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": self.pendencia.pk})
        )

        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": self.pendencia.pk, "tipo": "tcc", "item_pk": tcc.pk},
            )
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OrientacaoTCC.objects.filter(pk=tcc.pk).exists())
        self.assertTrue(any("não pode ser excluída" in m for m in self._mensagens(resp)))

    def test_excluir_com_tipo_invalido_nao_quebra(self):
        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": self.pendencia.pk, "tipo": "xpto", "item_pk": 1},
            )
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(any("Tipo inválido" in m for m in self._mensagens(resp)))


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 6 — janela de entrega fechada
# ══════════════════════════════════════════════════════════════════════════════
class JanelaFechadaBloqueiaUnidadeTests(_BaseFluxoE2E):
    """Sem janela ativa a unidade não escreve nada; a DESUP passa por cima."""

    def setUp(self):
        super().setUp()
        # Monta o estado ANTES de fechar a janela (a jornada real já teria dados).
        self._criar_pendencia_pela_rota([self.prof_a])
        self.pendencia = PendenciaExtra.objects.get(
            professor=self.prof_a, semestre=self.semestre
        )
        self._post_tcc(self.pendencia, [2])
        self.tcc = OrientacaoTCC.objects.get(pendencia=self.pendencia)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pendencia.pk}),
            {"sei_numero": "SEI-101010/101010/2026"},
        )
        # Janela fecha.
        JanelaEntrega.objects.all().delete()
        Notificacao.objects.all().delete()

    def test_criar_pendencia_bloqueado(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:pendencia_create"), {"professor_id": [str(self.prof_a2.pk)]}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("extra_curricular:pendencia_create"))
        self.assertFalse(PendenciaExtra.objects.filter(professor=self.prof_a2).exists())
        self.assertTrue(
            any("Janela de entrega fechada" in m for m in self._mensagens(resp))
        )
        # A tentativa é registrada para a DESUP.
        self.assertTrue(Notificacao.objects.filter(titulo__startswith="Tentativa bloqueada").exists())

    def test_salvar_item_bloqueado(self):
        self._login(self.coord_a)
        resp = self._post_extensao(self.pendencia, [8])
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AtividadeExtensionista.objects.filter(pendencia=self.pendencia).exists())
        self.assertTrue(any("Janela de entrega fechada" in m for m in self._mensagens(resp)))

    def test_enviar_para_desup_bloqueado(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": self.pendencia.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)

    def test_envio_em_lote_bloqueado(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:enviar_desup_lote"), {"ids": str(self.prof_a.pk)}
        )
        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)

    def test_salvar_item_em_lote_bloqueado(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:salvar_tcc_lote"),
            {
                "ids": str(self.prof_a.pk),
                "pendencia_id": str(self.pendencia.pk),
                "num_orientandos": "3",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(OrientacaoTCC.objects.filter(pendencia=self.pendencia).count(), 1)

    def test_excluir_item_bloqueado_pela_janela(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item_lote",
                kwargs={"tipo": "tcc", "item_pk": self.tcc.pk},
            ),
            {"ids": str(self.prof_a.pk)},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OrientacaoTCC.objects.filter(pk=self.tcc.pk).exists())

    def test_editar_sei_bloqueado(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pendencia.pk}),
            {"sei_numero": "SEI-121212/121212/2026"},
        )
        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.sei_numero, "SEI-101010/101010/2026")

    def test_excluir_item_pelo_detalhe_bloqueado_pela_janela(self):
        # CORRIGIDO: `DeletarItemView` era a ÚNICA rota de escrita do app sem
        # `enforce_window_or_redirect` — a gêmea de lote (`DeletarItemLoteView`)
        # já a tinha. Como os botões da lixeira eram `type="button"` +
        # `this.form.submit()` (que não dispara o evento `submit`), o modal do
        # front também não abria: dois cliques normais apagavam a justificativa
        # fora do prazo, sem notificar a DESUP.
        self._login(self.coord_a)
        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": self.pendencia.pk, "tipo": "tcc", "item_pk": self.tcc.pk},
            )
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(OrientacaoTCC.objects.filter(pk=self.tcc.pk).exists())
        self.assertTrue(any("Janela de entrega fechada" in m for m in self._mensagens(resp)))
        # E a tentativa vira registro para a DESUP, como nas demais rotas.
        self.assertTrue(
            Notificacao.objects.filter(titulo__startswith="Tentativa bloqueada").exists()
        )

    def test_tela_da_unidade_sinaliza_janela_fechada(self):
        self._login(self.coord_a)
        resp = self.client.get(
            reverse("extra_curricular:pendencia_detail", kwargs={"pk": self.pendencia.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["window_fechada"])

    # ── Bypass da DESUP ─────────────────────────────────────────────
    def test_desup_passa_por_cima_da_janela(self):
        """A DESUP grava item, SEI e parecer mesmo com a janela fechada."""
        self._login(self.desup)

        resp_item = self._post_extensao(self.pendencia, [6])
        self.assertEqual(resp_item.status_code, 302)
        ext = AtividadeExtensionista.objects.get(pendencia=self.pendencia)
        self.assertEqual(float(ext.carga_horaria), 3.0)

        resp_sei = self.client.post(
            reverse("extra_curricular:editar_sei_lote"),
            {"ids": str(self.prof_a.pk), "sei_numero": "SEI-131313/131313/2026"},
        )
        self.assertEqual(resp_sei.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.sei_numero, "SEI-131313/131313/2026")

        self.assertEqual(
            self._post_parecer(
                "ext", self.pendencia, ext, ParecerChoices.APROVADO, aprovados=6
            ).status_code,
            302,
        )
        ext.refresh_from_db()
        self.assertEqual(ext.parecer_desup, ParecerChoices.APROVADO)

        # Nenhuma tentativa bloqueada foi registrada para a DESUP.
        self.assertFalse(
            Notificacao.objects.filter(titulo__startswith="Tentativa bloqueada").exists()
        )

    def test_desup_avisa_unidade_mesmo_com_janela_fechada(self):
        self._login(self.desup)
        resp = self.client.post(
            reverse("extra_curricular:avisar_unidade", kwargs={"pk": self.pendencia.pk}),
            {"next": reverse("extra_curricular:pendencia_list")},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Notificacao.objects.filter(unidade_destino=self.unidade_a).exists()
        )


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 7 — permissões cruzadas entre unidades e perfis
# ══════════════════════════════════════════════════════════════════════════════
class PermissoesCruzadasTests(_BaseFluxoE2E):
    def setUp(self):
        super().setUp()
        self.pend_b = PendenciaExtra.objects.create(
            professor=self.prof_b,
            unidade=self.unidade_b,
            semestre=self.semestre,
            sei_numero="SEI-141414/141414/2026",
        )
        self.tcc_b = OrientacaoTCC.objects.create(pendencia=self.pend_b, num_orientandos=4)

    # ── Unidade A × Unidade B ───────────────────────────────────────
    def test_coordenador_nao_ve_detalhe_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self.client.get(
            reverse("extra_curricular:pendencia_detail", kwargs={"pk": self.pend_b.pk})
        )
        self.assertEqual(resp.status_code, 404)

    def test_coordenador_nao_salva_item_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self._post_tcc(self.pend_b, [2])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(OrientacaoTCC.objects.filter(pendencia=self.pend_b).count(), 1)

    def test_coordenador_nao_deleta_item_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item",
                kwargs={"pk": self.pend_b.pk, "tipo": "tcc", "item_pk": self.tcc_b.pk},
            )
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(OrientacaoTCC.objects.filter(pk=self.tcc_b.pk).exists())

    def test_coordenador_nao_deleta_item_de_outra_unidade_pelo_lote(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse(
                "extra_curricular:deletar_item_lote",
                kwargs={"tipo": "tcc", "item_pk": self.tcc_b.pk},
            ),
            {"ids": str(self.prof_b.pk)},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(OrientacaoTCC.objects.filter(pk=self.tcc_b.pk).exists())

    def test_coordenador_nao_envia_pendencia_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": self.pend_b.pk})
        )
        self.assertEqual(resp.status_code, 403)
        self.pend_b.refresh_from_db()
        self.assertEqual(self.pend_b.status, PendenciaExtra.StatusChoices.RASCUNHO)

    def test_coordenador_nao_edita_sei_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pend_b.pk}),
            {"sei_numero": "SEI-151515/151515/2026"},
        )
        self.assertEqual(resp.status_code, 403)
        self.pend_b.refresh_from_db()
        self.assertEqual(self.pend_b.sei_numero, "SEI-141414/141414/2026")

    def test_coordenador_nao_cria_pendencia_para_docente_de_outra_unidade(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:pendencia_create"), {"professor_id": [str(self.prof_b.pk)]}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            PendenciaExtra.objects.filter(professor=self.prof_b).count(),
            1,  # apenas a criada no setUp
        )

    def test_listagem_do_coordenador_e_restrita_a_sua_unidade(self):
        """Mesmo forçando ?unidade_id= de outra unidade, o coordenador só vê a sua."""
        self._login(self.coord_a)
        resp = self.client.get(
            reverse("extra_curricular:pendencia_list"),
            {"semestre": self.semestre, "unidade_id": self.unidade_b.pk},
        )
        self.assertEqual(resp.status_code, 200)
        pks = {l["professor"].pk for l in resp.context["pendencias_data"]}
        self.assertEqual(pks, {self.prof_a.pk, self.prof_a2.pk})
        self.assertNotIn(self.prof_b.pk, pks)

    # ── Unidade não emite parecer ───────────────────────────────────
    def test_unidade_nao_emite_parecer_na_propria_pendencia(self):
        pend_a = PendenciaExtra.objects.create(
            professor=self.prof_a, unidade=self.unidade_a, semestre=self.semestre
        )
        tcc_a = OrientacaoTCC.objects.create(pendencia=pend_a, num_orientandos=2)
        self._login(self.coord_a)
        resp = self._post_parecer("tcc", pend_a, tcc_a, ParecerChoices.APROVADO, aprovados=2)
        self.assertEqual(resp.status_code, 403)
        tcc_a.refresh_from_db()
        self.assertEqual(tcc_a.parecer_desup, ParecerChoices.PENDENTE)

    def test_unidade_nao_avisa_unidade(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:avisar_unidade", kwargs={"pk": self.pend_b.pk})
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Notificacao.objects.exists())

    # ── DESUP não usa as rotas exclusivas da unidade ────────────────
    def test_desup_nao_cria_pendencia(self):
        self._login(self.desup)
        self.assertEqual(
            self.client.get(reverse("extra_curricular:pendencia_create")).status_code, 403
        )
        resp = self.client.post(
            reverse("extra_curricular:pendencia_create"), {"professor_id": [str(self.prof_a.pk)]}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(PendenciaExtra.objects.filter(professor=self.prof_a).exists())

    def test_desup_nao_envia_para_si_mesma(self):
        self._login(self.desup)
        resp = self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": self.pend_b.pk})
        )
        self.assertEqual(resp.status_code, 403)
        self.pend_b.refresh_from_db()
        self.assertEqual(self.pend_b.status, PendenciaExtra.StatusChoices.RASCUNHO)

    def test_desup_nao_usa_rotas_de_lote_da_unidade(self):
        self._login(self.desup)
        for rota, dados in (
            ("extra_curricular:salvar_tcc_lote", {"pendencia_id": str(self.pend_b.pk), "num_orientandos": "2"}),
            ("extra_curricular:salvar_extensao_lote", {"pendencia_id": str(self.pend_b.pk), "num_estudantes": "2"}),
            (
                "extra_curricular:salvar_reducao_lote",
                {"pendencia_id": str(self.pend_b.pk), "motivo_reducao": "x", "horas_reduzidas": "1"},
            ),
            ("extra_curricular:enviar_desup_lote", {"ids": str(self.prof_b.pk)}),
        ):
            with self.subTest(rota=rota):
                resp = self.client.post(reverse(rota), dados)
                self.assertEqual(resp.status_code, 403)

    def test_anonimo_e_redirecionado_para_login_nas_rotas_de_escrita(self):
        self.client.logout()
        for rota, kwargs in (
            ("extra_curricular:pendencia_list", {}),
            ("extra_curricular:pendencia_create", {}),
            ("extra_curricular:pendencia_detail", {"pk": self.pend_b.pk}),
        ):
            with self.subTest(rota=rota):
                resp = self.client.get(reverse(rota, kwargs=kwargs))
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/login/", resp["Location"])


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 8 — validações (SEI, limite de horas, teto de orientandos)
# ══════════════════════════════════════════════════════════════════════════════
class ValidacoesDeEntradaTests(_BaseFluxoE2E):
    def setUp(self):
        super().setUp()
        self._criar_pendencia_pela_rota([self.prof_a])
        self.pendencia = PendenciaExtra.objects.get(
            professor=self.prof_a, semestre=self.semestre
        )

    # ── SEI ─────────────────────────────────────────────────────────
    def test_sei_em_formato_invalido_e_recusado_no_detalhe(self):
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pendencia.pk}),
            {"sei_numero": "12345/2026"},
        )
        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertFalse(self.pendencia.sei_numero)
        self.assertTrue(
            any("SEI-999999/999999/9999" in m for m in self._mensagens(resp)),
            "O usuário precisa saber qual é o formato esperado",
        )

    def test_sei_valido_e_aceito(self):
        self._login(self.coord_a)
        self.client.post(
            reverse("extra_curricular:editar_sei", kwargs={"pk": self.pendencia.pk}),
            {"sei_numero": "SEI-160010/000123/2026"},
        )
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.sei_numero, "SEI-160010/000123/2026")

    def test_sei_em_formato_invalido_e_recusado_no_lote(self):
        # CORRIGIDO: `PendenciaSEIUpdateLoteView` gravava o SEI com
        # `qs.update(sei_numero=sei_numero)`, e `QuerySet.update()` NÃO roda os
        # validators do model — o RegexValidator de `PendenciaExtra.sei_numero`
        # (models.py:62-67) era ignorado. A mesma tela, no caminho individual
        # (`editar_sei`), recusava o valor. Resultado: pela mesa de trabalho a
        # unidade gravava qualquer texto como número SEI, e esse SEI inválido é o
        # que libera o `enviar_desup_lote` (basta ser truthy).
        # A view agora roda os validators do campo antes do `update()`.
        self._login(self.coord_a)
        resp = self.client.post(
            reverse("extra_curricular:editar_sei_lote"),
            {"ids": str(self.prof_a.pk), "sei_numero": "processo qualquer"},
        )
        self.pendencia.refresh_from_db()
        self.assertNotEqual(self.pendencia.sei_numero, "processo qualquer")
        self.assertTrue(
            any("SEI-999999/999999/9999" in m for m in self._mensagens(resp)),
            "O usuário precisa saber qual é o formato esperado",
        )

    def test_envio_sem_sei_e_recusado(self):
        self._login(self.coord_a)
        self._post_tcc(self.pendencia, [2])
        resp = self.client.post(
            reverse("extra_curricular:enviar_desup", kwargs={"pk": self.pendencia.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("sei_error=1", resp.url)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)

    def test_sem_sei_por_mais_de_cinco_dias_bloqueia_novas_justificativas(self):
        PendenciaExtra.objects.filter(pk=self.pendencia.pk).update(
            data_criacao=timezone.now() - timedelta(days=6)
        )
        self._login(self.coord_a)
        resp = self._post_tcc(self.pendencia, [2])
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(OrientacaoTCC.objects.filter(pendencia=self.pendencia).exists())
        self.assertTrue(any("Prazo de 5 dias" in m for m in self._mensagens(resp)))

    # ── Teto de 8 orientandos ───────────────────────────────────────
    def test_tcc_com_mais_de_oito_orientandos_e_recusado_no_detalhe(self):
        self._login(self.coord_a)
        resp = self._post_tcc(self.pendencia, [9])
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(OrientacaoTCC.objects.filter(pendencia=self.pendencia).exists())

    def test_tcc_com_exatamente_oito_orientandos_e_aceito_e_teto_de_4h(self):
        self._login(self.coord_a)
        self._post_tcc(self.pendencia, [8])
        tcc = OrientacaoTCC.objects.get(pendencia=self.pendencia)
        self.assertEqual(float(tcc.carga_horaria), 4.0)
        self.assertEqual(tcc.ch_aprovada, 4.0)

    def test_tcc_com_mais_de_oito_orientandos_e_recusado_no_lote(self):
        # CORRIGIDO: `SalvarTCCLoteView.post` fazia
        # `OrientacaoTCC.objects.create(..., num_orientandos=int(num_orientandos))`
        # sem `full_clean()` e sem form — o `MaxValueValidator(8)`
        # (models.py:149) e o `OrientacaoTCCForm.clean_num_orientandos`
        # só rodavam no caminho do detalhe. Pela mesa de trabalho (o caminho do
        # dia a dia) gravava-se 9+ orientandos; a CH era capada em 4h no save,
        # mas o registro ficava inconsistente com a regra de negócio e era
        # exibido na tela como "9 orientandos".
        # As três views de lote passaram a usar o mesmo `ModelForm` do detalhe.
        self._login(self.coord_a)
        self.client.post(
            reverse("extra_curricular:salvar_tcc_lote"),
            {
                "ids": str(self.prof_a.pk),
                "pendencia_id": str(self.pendencia.pk),
                "num_orientandos": "9",
            },
        )
        self.assertFalse(OrientacaoTCC.objects.filter(pendencia=self.pendencia).exists())

    def test_orientandos_nao_numerico_no_lote_nao_pode_dar_500(self):
        # CORRIGIDO: `SalvarTCCLoteView.post` fazia `int(num_orientandos)` direto
        # no valor cru do POST. Qualquer coisa não numérica levantava
        # `ValueError` → HTTP 500 (erro não tratado), em vez de uma mensagem de
        # validação. Agora o valor passa pelo `OrientacaoTCCForm`.
        client = Client(raise_request_exception=False)
        client.force_login(self.coord_a)
        resp = client.post(
            reverse("extra_curricular:salvar_tcc_lote"),
            {
                "ids": str(self.prof_a.pk),
                "pendencia_id": str(self.pendencia.pk),
                "num_orientandos": "abc",
            },
        )
        self.assertNotEqual(resp.status_code, 500)

    def test_horas_reduzidas_invalidas_no_lote_nao_pode_dar_500(self):
        # CORRIGIDO: `SalvarReducaoLoteView.post` fazia
        # `Decimal(horas_reduzidas.replace(',', '.'))` no valor cru do POST.
        # Texto não numérico levantava `decimal.InvalidOperation` → HTTP 500.
        # Agora o valor (já com a vírgula decimal normalizada) passa pelo
        # `ReducaoCargaHorariaForm`.
        client = Client(raise_request_exception=False)
        client.force_login(self.coord_a)
        resp = client.post(
            reverse("extra_curricular:salvar_reducao_lote"),
            {
                "ids": str(self.prof_a.pk),
                "pendencia_id": str(self.pendencia.pk),
                "motivo_reducao": "Portaria",
                "horas_reduzidas": "duas horas",
            },
        )
        self.assertNotEqual(resp.status_code, 500)

    def test_lote_recusa_horas_negativas_e_numeros_absurdos(self):
        # CORRIGIDO (mesma causa-raiz do POST cru nas views de lote): as outras
        # duas primitivas medidas na auditoria.
        #  · horas_reduzidas="-8" era gravado como Decimal('-8.0') — uma CH
        #    negativa ABATE o total já aprovado e libera qualquer aprovação
        #    abaixo do limite de horas extras (primitiva de bypass);
        #  · num_estudantes="300000" estourava o `max_digits=6` de
        #    `carga_horaria` (300000 × 0,5 = 150000,0h) → HTTP 500 no save.
        client = Client(raise_request_exception=False)
        client.force_login(self.coord_a)

        resp_neg = client.post(
            reverse("extra_curricular:salvar_reducao_lote"),
            {
                "ids": str(self.prof_a.pk),
                "pendencia_id": str(self.pendencia.pk),
                "motivo_reducao": "Portaria",
                "horas_reduzidas": "-8",
            },
        )
        self.assertNotEqual(resp_neg.status_code, 500)
        self.assertFalse(ReducaoCargaHoraria.objects.filter(pendencia=self.pendencia).exists())

        resp_absurdo = client.post(
            reverse("extra_curricular:salvar_extensao_lote"),
            {
                "ids": str(self.prof_a.pk),
                "pendencia_id": str(self.pendencia.pk),
                "num_estudantes": "300000",
            },
        )
        self.assertNotEqual(resp_absurdo.status_code, 500)
        self.assertFalse(
            AtividadeExtensionista.objects.filter(pendencia=self.pendencia).exists()
        )

    # ── Aprovado × solicitado ───────────────────────────────────────
    def test_desup_nao_aprova_mais_do_que_o_solicitado(self):
        # CORRIGIDO: nem `ParecerTCCForm` nem `ParecerExtensaoForm` cruzavam o
        # valor aprovado com o solicitado, e `num_estudantes_aprovados` não tinha
        # teto nenhum. Como `ch_aprovada` é recalculada a partir do nº aprovado,
        # a DESUP concedia CH que a unidade nunca pediu.
        # REPRO: item com num_orientandos=2 (1,0h) → POST
        #        num_orientandos_aprovados=8 → ch_aprovada virava 4,0h.
        tcc = OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=2)
        ext = AtividadeExtensionista.objects.create(
            pendencia=self.pendencia, num_estudantes=4
        )
        self._login(self.desup)

        resp_tcc = self._post_parecer(
            "tcc", self.pendencia, tcc, ParecerChoices.APROVADO, aprovados=8
        )
        self.assertEqual(resp_tcc.status_code, 302)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)   # nada gravado
        self.assertIsNone(tcc.num_orientandos_aprovados)
        self.assertEqual(tcc.ch_aprovada, 1.0)                          # 2 × 0,5h

        self._post_parecer("ext", self.pendencia, ext, ParecerChoices.APROVADO, aprovados=40)
        ext.refresh_from_db()
        self.assertEqual(ext.parecer_desup, ParecerChoices.PENDENTE)
        self.assertIsNone(ext.num_estudantes_aprovados)
        self.assertEqual(ext.ch_aprovada, 2.0)                          # 4 × 0,5h

        # Contraprova: aprovar exatamente o solicitado (ou menos) continua valendo.
        self._post_parecer("tcc", self.pendencia, tcc, ParecerChoices.APROVADO, aprovados=2)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.APROVADO)
        self.assertEqual(tcc.ch_aprovada, 1.0)

    # ── Rascunho não é promovido ────────────────────────────────────
    def test_rascunho_nao_vira_aprovado_sem_sei_e_sem_envio(self):
        # CORRIGIDO: em `sincronizar_status_pendencia` o ramo `all(APROVADO)`
        # vinha ANTES da proteção de rascunho, então uma pendência ainda em
        # RASCUNHO (nunca enviada, sem SEI) era promovida a APROVADO assim que a
        # DESUP emitisse parecer nos itens — furando a regra "SEI obrigatório
        # para enviar" e fazendo a CH contar para o docente.
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)
        self.assertFalse(self.pendencia.sei_numero)
        tcc = OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=2)

        self._login(self.desup)
        resp = self._post_parecer(
            "tcc", self.pendencia, tcc, ParecerChoices.APROVADO, aprovados=2
        )
        self.assertEqual(resp.status_code, 302)

        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.APROVADO)  # o parecer vale
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.RASCUNHO)
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)
        self.prof_a.refresh_from_db()
        self.assertEqual(self.prof_a.ch_justificada, 0.0)

    # ── Limite de horas extras (limite_horas_extra_efetivo) ─────────
    def test_limite_efetivo_do_contrato_barra_aprovacao_excessiva(self):
        """Sem `limite_horas_extra` manual, o limite efetivo é
        `max_class_hours - ch_alocada`. Aprovar acima disso deve avisar, não 500."""
        contrato_curto = ContractType.objects.create(
            nome="Contrato curto E2E", max_class_hours=2, max_total_hours=40, max_classes=4
        )
        prof = self._professor("Docente Curto", "curto", self.unidade_a, contrato_curto)
        self.assertEqual(prof.limite_horas_extra_efetivo, 2.0)

        pend = PendenciaExtra.objects.create(
            professor=prof, unidade=self.unidade_a, semestre=self.semestre
        )
        tcc = OrientacaoTCC.objects.create(pendencia=pend, num_orientandos=8)  # 4h

        self._login(self.desup)
        resp = self._post_parecer("tcc", pend, tcc, ParecerChoices.APROVADO, aprovados=8)

        self.assertEqual(resp.status_code, 302)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)  # nada gravado
        mensagens = self._mensagens(resp)
        self.assertTrue(any("Limite de horas extras excedido" in m for m in mensagens))
        # A mensagem precisa dizer quantas horas o docente ainda tem (2h aqui).
        self.assertTrue(any("2h disponíveis" in m for m in mensagens), mensagens)
        pend.refresh_from_db()
        self.assertEqual(pend.ch_total_justificada, 0.0)

    def test_aprovacao_dentro_do_limite_efetivo_passa(self):
        contrato_curto = ContractType.objects.create(
            nome="Contrato curto 2 E2E", max_class_hours=2, max_total_hours=40, max_classes=4
        )
        prof = self._professor("Docente Curto 2", "curto2", self.unidade_a, contrato_curto)
        pend = PendenciaExtra.objects.create(
            professor=prof,
            unidade=self.unidade_a,
            semestre=self.semestre,
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        tcc = OrientacaoTCC.objects.create(pendencia=pend, num_orientandos=8)

        self._login(self.desup)
        # 4 orientandos aprovados = 2h, exatamente o limite.
        self._post_parecer("tcc", pend, tcc, ParecerChoices.APROVADO, aprovados=4)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.APROVADO)
        pend.refresh_from_db()
        self.assertEqual(pend.ch_total_justificada, 2.0)

    def test_formset_da_unidade_barra_limite_manual_de_horas_extras(self):
        """`limite_horas_extra` manual também trava a inclusão pela unidade."""
        self.prof_a.limite_horas_extra = Decimal("1.0")
        self.prof_a.save(update_fields=["limite_horas_extra"])

        self._login(self.coord_a)
        resp = self._post_extensao(self.pendencia, [10])  # 5h > 1h
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(AtividadeExtensionista.objects.filter(pendencia=self.pendencia).exists())

    def _cenario_limite_curto(self, sufixo):
        """Docente com limite efetivo de 2h e uma pendência enviada."""
        contrato_curto = ContractType.objects.create(
            nome=f"Contrato curto {sufixo} E2E",
            max_class_hours=2,
            max_total_hours=40,
            max_classes=4,
        )
        prof = self._professor(f"Docente Curto {sufixo}", sufixo, self.unidade_a, contrato_curto)
        pend = PendenciaExtra.objects.create(
            professor=prof,
            unidade=self.unidade_a,
            semestre=self.semestre,
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        return prof, pend

    def test_indeferir_item_acima_do_limite_nao_pode_ser_bloqueado(self):
        # CORRIGIDO: `_BaseParecerView.post` aplicava a trava de limite ANTES de
        # olhar o parecer: mesmo quando a DESUP escolhia INDEFERIDO, a view
        # somava `outros + instance.ch_aprovada` e, se estourasse
        # `limite_horas_extra_efetivo`, descartava o parecer. Ou seja: a DESUP
        # ficava IMPEDIDA de indeferir justamente o item excessivo — que é a ação
        # correta nesse caso. Nenhuma hora é concedida num indeferimento, então a
        # trava agora só roda quando o parecer gravado é APROVADO.
        _, pend = self._cenario_limite_curto("indef")
        tcc = OrientacaoTCC.objects.create(pendencia=pend, num_orientandos=8)  # 4h

        self._login(self.desup)
        resp = self._post_parecer(
            "tcc", pend, tcc, ParecerChoices.INDEFERIDO, motivo="Fora do PPC"
        )
        self.assertEqual(resp.status_code, 302)
        tcc.refresh_from_db()
        self.assertEqual(
            tcc.parecer_desup,
            ParecerChoices.INDEFERIDO,
            "Indeferir não concede horas — o limite não pode barrar o indeferimento",
        )

    def test_item_indeferido_nao_deveria_consumir_o_limite_de_horas(self):
        # CORRIGIDO: `_ch_aprovada_outros` somava `ch_aprovada` de TODOS os demais
        # itens, sem olhar o `parecer_desup`. Um item INDEFERIDO continua com
        # `horas_aprovadas` preenchido (o `save()` do model copia a CH calculada
        # — models.py:226/317/389), então ele consumia o limite do docente e
        # impedia a DESUP de deferir os itens seguintes, mesmo que o total
        # efetivamente concedido fosse zero (`ch_total_justificada` ignora tudo
        # que não está APROVADO). A soma agora filtra por `parecer_desup`.
        _, pend = self._cenario_limite_curto("consome")
        # Estado de partida: TCC já indeferido (aqui pelo ORM porque a própria
        # rota de parecer também travava — ver teste acima).
        OrientacaoTCC.objects.create(
            pendencia=pend, num_orientandos=8, parecer_desup=ParecerChoices.INDEFERIDO
        )
        ext = AtividadeExtensionista.objects.create(pendencia=pend, num_estudantes=2)  # 1h

        self._login(self.desup)
        self._post_parecer("ext", pend, ext, ParecerChoices.APROVADO, aprovados=2)
        ext.refresh_from_db()
        self.assertEqual(
            ext.parecer_desup,
            ParecerChoices.APROVADO,
            "Horas de um item INDEFERIDO não podem consumir o limite do docente",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 9 — AvisarUnidadeView e PendenciaStatusUpdateView no fluxo real
# ══════════════════════════════════════════════════════════════════════════════
class AvisoEConsolidacaoDesupTests(_BaseFluxoE2E):
    def setUp(self):
        super().setUp()
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="SEI-171717/171717/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )

    # ── AvisarUnidadeView ───────────────────────────────────────────
    def test_desup_avisa_unidade_e_volta_para_a_tela_de_origem(self):
        origem = f"{reverse('extra_curricular:pendencia_list')}?semestre={self.semestre}"
        self._login(self.desup)
        resp = self.client.post(
            reverse("extra_curricular:avisar_unidade", kwargs={"pk": self.pendencia.pk}),
            {"next": origem},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, origem)

        aviso = Notificacao.objects.get(unidade_destino=self.unidade_a)
        self.assertEqual(aviso.titulo, "Aviso de Pendência Extracurricular")
        self.assertIn(self.prof_a.nome, aviso.mensagem)
        self.assertIn(self.semestre, aviso.mensagem)
        self.assertEqual(
            aviso.url_acao,
            reverse("extra_curricular:pendencia_detail", args=[self.pendencia.pk]),
        )
        self.assertTrue(
            any(self.unidade_a.sigla in m for m in self._mensagens(resp))
        )

    def test_aviso_nao_redireciona_para_host_externo(self):
        self._login(self.desup)
        resp = self.client.post(
            reverse("extra_curricular:avisar_unidade", kwargs={"pk": self.pendencia.pk}),
            {"next": "https://exemplo-malicioso.com/roubar"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/")

    def test_aviso_em_pendencia_inexistente_da_404(self):
        self._login(self.desup)
        resp = self.client.post(
            reverse("extra_curricular:avisar_unidade", kwargs={"pk": 999999})
        )
        self.assertEqual(resp.status_code, 404)

    # ── PendenciaStatusUpdateView ───────────────────────────────────
    def test_consolidar_sem_itens_mantem_status_e_grava_motivo(self):
        self._login(self.desup)
        resp = self.client.post(
            reverse("extra_curricular:atualizar_status", kwargs={"pk": self.pendencia.pk}),
            {"motivo_status_desup": "Aguardando documentação complementar."},
        )
        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.assertEqual(
            self.pendencia.motivo_status_desup, "Aguardando documentação complementar."
        )

    def test_consolidar_e_idempotente(self):
        tcc = OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=2)
        self._login(self.desup)
        self._post_parecer("tcc", self.pendencia, tcc, ParecerChoices.APROVADO, aprovados=2)

        url = reverse("extra_curricular:atualizar_status", kwargs={"pk": self.pendencia.pk})
        self.client.post(url, {"motivo_status_desup": "Deferido"})
        self.client.post(url, {"motivo_status_desup": "Deferido"})

        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.assertEqual(self.pendencia.motivo_status_desup, "Deferido")
        self.assertEqual(self.pendencia.ch_total_justificada, 1.0)

    def test_consolidacao_apos_novo_item_volta_para_enviado(self):
        """Aprovada, ganha um item novo da unidade e volta a ficar pendente."""
        tcc = OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=2)
        self._login(self.desup)
        self._post_parecer("tcc", self.pendencia, tcc, ParecerChoices.APROVADO, aprovados=2)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.APROVADO)

        self._login(self.coord_a)
        self._post_extensao(self.pendencia, [4])

        self._login(self.desup)
        self.client.post(
            reverse("extra_curricular:atualizar_status", kwargs={"pk": self.pendencia.pk}),
            {"motivo_status_desup": ""},
        )
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 10 — CalcularCHView (API consumida pela tela)
# ══════════════════════════════════════════════════════════════════════════════
class CalcularCHEndpointTests(_BaseFluxoE2E):
    def setUp(self):
        super().setUp()
        self.url = reverse("extra_curricular:calcular_ch")
        self._login(self.coord_a)

    def _ch(self, **params):
        resp = self.client.get(self.url, params)
        self.assertEqual(resp.status_code, 200)
        return resp.json()["ch"]

    def test_tcc_valores_de_borda(self):
        for n, esperado in ((0, 0.0), (1, 0.5), (7, 3.5), (8, 4.0), (9, 4.0), (100, 4.0)):
            with self.subTest(n=n):
                self.assertEqual(self._ch(tipo="tcc", n=n), esperado)

    def test_extensao_sem_teto(self):
        for n, esperado in ((0, 0.0), (1, 0.5), (11, 5.5), (200, 100.0)):
            with self.subTest(n=n):
                self.assertEqual(self._ch(tipo="extensao", n=n), esperado)

    def test_tipo_invalido_retorna_400(self):
        for tipo in ("reducao", "", "TCC"):
            with self.subTest(tipo=tipo):
                resp = self.client.get(self.url, {"tipo": tipo, "n": 2})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("error", resp.json())

    def test_n_ausente_ou_invalido_cai_para_zero(self):
        self.assertEqual(self._ch(tipo="tcc"), 0.0)
        self.assertEqual(self._ch(tipo="tcc", n="abc"), 0.0)
        self.assertEqual(self._ch(tipo="extensao", n="3.5"), 0.0)

    def test_anonimo_e_redirecionado_para_login(self):
        self.client.logout()
        resp = self.client.get(self.url, {"tipo": "tcc", "n": 4})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_desup_tambem_consulta_o_endpoint(self):
        self._login(self.desup)
        self.assertEqual(self._ch(tipo="tcc", n=6), 3.0)

    def test_quantidade_negativa_nao_pode_gerar_ch_negativa(self):
        # CORRIGIDO: `calcular_ch_tcc`/`calcular_ch_extensao` multiplicavam direto
        # por 0.5 sem piso em 0, e `CalcularCHView` só protegia contra valor não
        # inteiro. Com `n` negativo a API devolvia carga horária negativa
        # ({"ch": -1.0}), valor impossível que a tela exibe como prévia de CH.
        # As duas funções passaram a aplicar `max(n, 0)`.
        self.assertGreaterEqual(self._ch(tipo="tcc", n=-2), 0.0)
        self.assertGreaterEqual(self._ch(tipo="extensao", n=-4), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# Cenário 11 — listagem (escopo por unidade/semestre e token por linha)
# ══════════════════════════════════════════════════════════════════════════════
class ListagemPendenciasTests(_BaseFluxoE2E):
    def setUp(self):
        super().setUp()
        self.url = reverse("extra_curricular:pendencia_list")

    def _linhas(self, resp, professor=None):
        linhas = resp.context["pendencias_data"]
        if professor:
            linhas = [l for l in linhas if l["professor"].pk == professor.pk]
        return linhas

    def test_coordenador_ve_apenas_os_docentes_da_sua_unidade(self):
        self._login(self.coord_a)
        resp = self.client.get(self.url, {"semestre": self.semestre})
        self.assertEqual(resp.status_code, 200)
        pks = {l["professor"].pk for l in self._linhas(resp)}
        self.assertEqual(pks, {self.prof_a.pk, self.prof_a2.pk})
        self.assertEqual(resp.context["unidade_selecionada"], self.unidade_a)
        self.assertFalse(resp.context["is_desup"])

    def test_desup_ve_todas_as_unidades_e_filtra_por_unidade(self):
        self._login(self.desup)
        todas = self.client.get(self.url, {"semestre": self.semestre})
        pks = {l["professor"].pk for l in self._linhas(todas)}
        self.assertEqual(pks, {self.prof_a.pk, self.prof_a2.pk, self.prof_b.pk})
        self.assertTrue(todas.context["is_desup"])

        so_b = self.client.get(self.url, {"semestre": self.semestre, "unidade_id": self.unidade_b.pk})
        self.assertEqual({l["professor"].pk for l in self._linhas(so_b)}, {self.prof_b.pk})

    def test_uma_linha_por_item_com_token_de_status_correto(self):
        """Cada justificativa vira uma linha, com o token do parecer daquele item."""
        pend = PendenciaExtra.objects.create(
            professor=self.prof_a,
            unidade=self.unidade_a,
            semestre=self.semestre,
            sei_numero="SEI-181818/181818/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        OrientacaoTCC.objects.create(
            pendencia=pend, num_orientandos=4, parecer_desup=ParecerChoices.APROVADO
        )
        AtividadeExtensionista.objects.create(
            pendencia=pend, num_estudantes=6, parecer_desup=ParecerChoices.INDEFERIDO
        )
        ReducaoCargaHoraria.objects.create(
            pendencia=pend, motivo_reducao="Portaria 45", horas_reduzidas=Decimal("1.5")
        )

        self._login(self.coord_a)
        resp = self.client.get(self.url, {"semestre": self.semestre})
        linhas = self._linhas(resp, self.prof_a)
        self.assertEqual(len(linhas), 3)

        por_tipo = {l["item_tipo"]: l for l in linhas}
        self.assertEqual(por_tipo["tcc"]["status_token"], "finalizado")
        self.assertEqual(por_tipo["ext"]["status_token"], "indeferido")
        self.assertEqual(por_tipo["red"]["status_token"], "pendente")
        self.assertEqual(por_tipo["tcc"]["justificativa_token"], "tcc")
        self.assertEqual(por_tipo["ext"]["justificativa_token"], "extensao")
        self.assertEqual(por_tipo["red"]["justificativa_token"], "reducao")
        # Pendência não APROVADA => nenhuma linha conta CH justificada.
        self.assertEqual({l["ch_justificada"] for l in linhas}, {0})
        # E o SEI aparece em todas as linhas do docente.
        self.assertEqual(
            {l["sei_numero"] for l in linhas}, {"SEI-181818/181818/2026"}
        )

        html = resp.content.decode()
        self.assertIn('data-status="finalizado"', html)
        self.assertIn('data-justificativa="reducao"', html)

    def test_docente_sem_pendencia_aparece_como_sem_registro(self):
        self._login(self.coord_a)
        resp = self.client.get(self.url, {"semestre": self.semestre})
        linha = self._linhas(resp, self.prof_a2)[0]
        self.assertIsNone(linha["pendencia"])
        self.assertEqual(linha["status_token"], "sem_registro")
        self.assertEqual(linha["ch_pendente"], 20)
        self.assertEqual(linha["ch_faltante"], 20)

    def test_pendencia_de_outro_semestre_nao_aparece_no_semestre_atual(self):
        outro = "2019.1"
        pend = PendenciaExtra.objects.create(
            professor=self.prof_a, unidade=self.unidade_a, semestre=outro,
            status=PendenciaExtra.StatusChoices.APROVADO,
        )
        OrientacaoTCC.objects.create(
            pendencia=pend, num_orientandos=4, parecer_desup=ParecerChoices.APROVADO
        )

        self._login(self.coord_a)
        atual = self.client.get(self.url, {"semestre": self.semestre})
        self.assertEqual(self._linhas(atual, self.prof_a)[0]["status_token"], "sem_registro")

        antigo = self.client.get(self.url, {"semestre": outro})
        linha = self._linhas(antigo, self.prof_a)[0]
        self.assertEqual(linha["status_token"], "finalizado")
        self.assertEqual(linha["ch_justificada"], 2.0)

    def test_busca_por_nome_filtra_os_docentes(self):
        self._login(self.coord_a)
        resp = self.client.get(self.url, {"semestre": self.semestre, "q": "Bruno"})
        pks = {l["professor"].pk for l in self._linhas(resp)}
        self.assertEqual(pks, {self.prof_a2.pk})

    def test_coordenador_sem_unidade_e_mandado_para_o_dashboard(self):
        orfao = User.objects.create_user(
            email="orfao_e2e@teste.com",
            perfil="COORDENADOR_UNIDADE",
            forcar_troca_senha=False,
        )
        self._login(orfao)
        resp = self.client.get(self.url, {"semestre": self.semestre})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("dashboard"))

    def test_semestres_disponiveis_incluem_o_atual(self):
        self._login(self.coord_a)
        resp = self.client.get(self.url)
        self.assertIn(self.semestre, resp.context["semestres"])
        self.assertEqual(resp.context["semestre"], self.semestre)
