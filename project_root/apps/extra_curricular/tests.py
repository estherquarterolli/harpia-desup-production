from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import TestCase, Client
from django.urls import reverse

from apps.extra_curricular.models import (
    OrientacaoTCC,
    AtividadeExtensionista,
    ReducaoCargaHoraria,
    ParecerChoices,
    PendenciaExtra,
)
from apps.extra_curricular.forms import ReducaoCargaHorariaFormSet
from apps.extra_curricular.services import sincronizar_status_pendencia
from apps.extra_curricular.utils import semestre_atual
from apps.professors.models import Professor, ContractType
from apps.core.models import Unidade
from apps.accounts.models import User


class ExtraCurricularApprovedTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade Teste", sigla="UT")
        self.contrato = ContractType.objects.create(
            nome="Ensino Superior",
            max_class_hours=20,
            max_classes=10
        )
        self.professor = Professor.objects.create(
            rh_nome="Professor Teste",
            rh_email="teste@teste.com",
            id_funcional="12345",
            rh_matricula="M12345",
            unidade_principal=self.unidade,
            tipo_contrato=self.contrato
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre="2026.1"
        )

    def test_orientacao_tcc_approved_calculation(self):
        """Test calculation of approved hours for TCC based on approved students."""
        # 1. Default: approved students is None, use requested students
        tcc = OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4
        )
        # 4 * 0.5 = 2.0
        self.assertEqual(tcc.carga_horaria, 2.0)
        self.assertEqual(tcc.horas_aprovadas, 2.0)
        self.assertEqual(tcc.ch_aprovada, 2.0)

        # 2. Set approved students
        tcc.num_orientandos_aprovados = 2
        tcc.save()
        # 2 * 0.5 = 1.0
        self.assertEqual(tcc.horas_aprovadas, 1.0)
        self.assertEqual(tcc.ch_aprovada, 1.0)

        # 3. Max limit (8 students -> 4h)
        tcc.num_orientandos_aprovados = 10 # Should be capped at 8 if we use logic, but field has validator.
        # Logic in plan says: min(round(num_orientandos_aprovados * 0.5, 1), 4.0)
        tcc.save()
        self.assertEqual(tcc.horas_aprovadas, 4.0)
        self.assertEqual(tcc.ch_aprovada, 4.0)

    def test_atividade_extensionista_approved_calculation(self):
        """Test calculation of approved hours for Extension based on approved students."""
        # 1. Default
        ext = AtividadeExtensionista.objects.create(
            pendencia=self.pendencia,
            num_estudantes=10
        )
        # 10 * 0.5 = 5.0
        self.assertEqual(ext.carga_horaria, 5.0)
        self.assertEqual(ext.horas_aprovadas, 5.0)
        self.assertEqual(ext.ch_aprovada, 5.0)

        # 2. Set approved students
        ext.num_estudantes_aprovados = 6
        ext.save()
        # 6 * 0.5 = 3.0
        self.assertEqual(ext.horas_aprovadas, 3.0)
        self.assertEqual(ext.ch_aprovada, 3.0)


# ════════════════════════════════════════════════════════════════════
# Entrega 1 — Decisão da DESUP (INDEFERIDO + consolidação no detalhe)
# ════════════════════════════════════════════════════════════════════
class DecisaoDesupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.unidade = Unidade.objects.create(nome="Unidade Decisão", sigla="UD")
        self.contrato = ContractType.objects.create(
            nome="Ensino Superior D",
            max_class_hours=20,
            max_classes=10,
        )
        self.professor = Professor.objects.create(
            rh_nome="Docente Decisão",
            rh_email="decisao@teste.com",
            id_funcional="99999",
            rh_matricula="M99999",
            unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre=semestre_atual(),
            sei_numero="SEI-123456/123456/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        self.desup = User.objects.create_user(
            email="desup@teste.com",
            perfil="DESUP",
            forcar_troca_senha=False,
        )
        self.coord = User.objects.create_user(
            email="coord@teste.com",
            perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade,
            forcar_troca_senha=False,
        )

    # ── Lista: coluna Status somente leitura ────────────────────────
    def test_lista_desup_sem_form_de_status(self):
        """A lista para DESUP não deve conter o form de status nem os inputs."""
        OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=4)
        self.client.force_login(self.desup)
        url = reverse("extra_curricular:pendencia_list")
        resp = self.client.get(url, {"semestre": semestre_atual()})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Não deve conter o form de finalização inline nem seus inputs
        self.assertNotIn('name="status"', html)
        self.assertNotIn('name="item_horas_aprovadas"', html)
        self.assertNotIn('name="item_tipo"', html)
        # Deve exibir o docente (a linha existe) e o badge somente-leitura
        self.assertIn("Docente Decisão", html)
        self.assertIn("badge-enviado", html)

    # ── Finalizar (consolidação) DESUP-only ─────────────────────────
    def test_atualizar_status_finaliza_sem_sobrescrever_pareceres(self):
        """Finalizar consolida via sincronizar e não sobrescreve parecer dos itens."""
        tcc_aprovado = OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4,
            parecer_desup=ParecerChoices.APROVADO,
        )
        tcc_pendente = OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=2,
            parecer_desup=ParecerChoices.PENDENTE,
        )
        self.client.force_login(self.desup)
        url = reverse("extra_curricular:atualizar_status", kwargs={"pk": self.pendencia.pk})
        resp = self.client.post(url, {"motivo_status_desup": "Analisado"})

        # Redireciona ao detalhe
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            resp.url,
            reverse("extra_curricular:pendencia_detail", kwargs={"pk": self.pendencia.pk}),
        )

        # Pareceres dos itens NÃO foram sobrescritos
        tcc_aprovado.refresh_from_db()
        tcc_pendente.refresh_from_db()
        self.assertEqual(tcc_aprovado.parecer_desup, ParecerChoices.APROVADO)
        self.assertEqual(tcc_pendente.parecer_desup, ParecerChoices.PENDENTE)

        # Status consolidado: nem todos aprovados e nenhum indeferido -> permanece ENVIADO
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.assertEqual(self.pendencia.motivo_status_desup, "Analisado")

    def test_atualizar_status_finaliza_aprovado(self):
        """Com todos os itens aprovados, Finalizar consolida como APROVADO."""
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4,
            parecer_desup=ParecerChoices.APROVADO,
        )
        self.client.force_login(self.desup)
        url = reverse("extra_curricular:atualizar_status", kwargs={"pk": self.pendencia.pk})
        self.client.post(url, {"motivo_status_desup": ""})
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.APROVADO)

    # ── Reabrir (DESUP): CH deixa de contar, horas preservadas ──────
    def test_reabrir_zera_contagem_e_preserva_horas(self):
        """
        Reabrir uma pendência finalizada volta o parecer dos itens para PENDENTE,
        o status agregado para ENVIADO e faz a CH aprovada deixar de contar — mas
        preserva as horas aprovadas anteriores como ponto de partida.
        """
        tcc = OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4,
            num_orientandos_aprovados=4,
            parecer_desup=ParecerChoices.APROVADO,
        )
        sincronizar_status_pendencia(self.pendencia)
        self.pendencia.refresh_from_db()

        # Pré-condição: finalizada e contando CH
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.APROVADO)
        self.assertGreater(self.pendencia.ch_total_justificada, 0.0)
        self.assertGreater(self.professor.ch_justificada, 0.0)

        # Reabrir
        self.client.force_login(self.desup)
        url = reverse("extra_curricular:reabrir_pendencia", kwargs={"pk": self.pendencia.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        tcc.refresh_from_db()
        self.pendencia.refresh_from_db()
        self.professor.refresh_from_db()

        # Parecer volta a PENDENTE, status agregado a ENVIADO
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)

        # CH deixa de contar enquanto não for aprovada de novo
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)
        self.assertEqual(self.professor.ch_justificada, 0.0)

        # Horas aprovadas anteriores preservadas (ponto de partida)
        self.assertEqual(tcc.num_orientandos_aprovados, 4)
        self.assertEqual(tcc.horas_aprovadas, 2.0)

    # ── Escopo por semestre: justificativa antiga não conta ─────────
    def test_justificativa_semestre_anterior_nao_conta_no_professor(self):
        """A CH justificada do professor é escopada pelo semestre atual: uma
        pendência APROVADA de um semestre anterior não deve mais contar quando
        o semestre vira (as justificativas seguem a matriz/semestre, não ficam
        acumuladas no professor)."""
        atual = semestre_atual()
        ano, s = int(atual.split(".")[0]), int(atual.split(".")[1])
        anterior = f"{ano - 1}.2" if s == 1 else f"{ano}.1"

        pend_antiga = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre=anterior,
            status=PendenciaExtra.StatusChoices.APROVADO,
        )
        OrientacaoTCC.objects.create(
            pendencia=pend_antiga,
            num_orientandos=4,
            num_orientandos_aprovados=4,
            parecer_desup=ParecerChoices.APROVADO,
        )

        # A pendência antiga está APROVADA e tem CH própria...
        self.assertGreater(pend_antiga.ch_total_justificada, 0.0)
        # ...mas por ser de semestre anterior, NÃO conta no total do professor.
        self.professor.refresh_from_db()
        self.assertEqual(self.professor.ch_justificada, 0.0)

    def test_justificativa_semestre_atual_conta_no_professor(self):
        """Contraprova: uma pendência APROVADA no semestre atual conta normalmente.

        A pendência do setUp já é do semestre atual — basta aprová-la.
        """
        self.pendencia.status = PendenciaExtra.StatusChoices.APROVADO
        self.pendencia.save()
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4,
            num_orientandos_aprovados=4,
            parecer_desup=ParecerChoices.APROVADO,
        )
        self.professor.refresh_from_db()
        self.assertGreater(self.professor.ch_justificada, 0.0)

    def test_ch_justificada_usa_horas_aprovadas_nao_solicitadas(self):
        """CORR-001: ch_justificada deve somar as horas APROVADAS pela DESUP
        (ch_aprovada), não as solicitadas.

        Solicitado: 8 orientandos → carga_horaria = 4.0h (teto TCC).
        Aprovado:   2 orientandos → ch_aprovada   = 1.0h.
        O total do professor deve refletir 1.0h (aprovado), não 4.0h (solicitado).
        """
        self.pendencia.status = PendenciaExtra.StatusChoices.APROVADO
        self.pendencia.save()
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=8,          # solicitado (carga_horaria = 4.0h)
            num_orientandos_aprovados=2,  # aprovado pela DESUP (ch_aprovada = 1.0h)
            parecer_desup=ParecerChoices.APROVADO,
        )
        self.professor.refresh_from_db()
        self.assertEqual(self.professor.ch_justificada, 1.0)

    def test_reabrir_recusa_quando_nao_finalizada(self):
        """Reabrir só é permitido em pendência APROVADO; ENVIADO é recusado."""
        OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=4)
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)
        self.client.force_login(self.desup)
        url = reverse("extra_curricular:reabrir_pendencia", kwargs={"pk": self.pendencia.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)

    def test_reabrir_coordenador_recebe_403(self):
        """Coordenador não pode reabrir (DESUP-only)."""
        self.pendencia.status = PendenciaExtra.StatusChoices.APROVADO
        self.pendencia.save(update_fields=["status"])
        self.client.force_login(self.coord)
        url = reverse("extra_curricular:reabrir_pendencia", kwargs={"pk": self.pendencia.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_atualizar_status_coordenador_recebe_403(self):
        """Coordenador não pode consolidar decisão (DESUP-only)."""
        self.client.force_login(self.coord)
        url = reverse("extra_curricular:atualizar_status", kwargs={"pk": self.pendencia.pk})
        resp = self.client.post(url, {"motivo_status_desup": "x"})
        self.assertEqual(resp.status_code, 403)

    # ── Indeferimento por item ──────────────────────────────────────
    def test_indeferir_item_via_parecer_endpoint(self):
        """Indeferir um item pelo endpoint parecer_* consolida a pendência como INDEFERIDO."""
        tcc = OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=4)
        self.client.force_login(self.desup)
        url = reverse(
            "extra_curricular:parecer_tcc",
            kwargs={"pk": self.pendencia.pk, "item_pk": tcc.pk},
        )
        prefix = f"ptcc-{tcc.pk}"
        resp = self.client.post(url, {
            f"{prefix}-parecer_desup": ParecerChoices.INDEFERIDO,
            f"{prefix}-num_orientandos_aprovados": "",
            f"{prefix}-horas_aprovadas": "",
            f"{prefix}-motivo_parecer": "Fora do escopo",
        })
        self.assertEqual(resp.status_code, 302)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.INDEFERIDO)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.INDEFERIDO)

    def test_sincronizar_resultado_misto_vira_parcial(self):
        """CORR-023: aprovado + indeferido => PARCIAL (antes virava INDEFERIDO).

        A regra anterior ("qualquer item indeferido derruba a pendência") fazia o
        item indeferido zerar a CH que a DESUP já tinha deferido nos outros.
        """
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4,
            parecer_desup=ParecerChoices.APROVADO,
        )
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=2,
            parecer_desup=ParecerChoices.INDEFERIDO,
        )
        status = sincronizar_status_pendencia(self.pendencia)
        self.assertEqual(status, PendenciaExtra.StatusChoices.PARCIAL)

    def test_ch_total_justificada_soma_so_o_aprovado_no_parcial(self):
        """CORR-023: no PARCIAL, o item aprovado conta e o indeferido fica de fora."""
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=4,
            parecer_desup=ParecerChoices.APROVADO,
        )
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia,
            num_orientandos=2,
            parecer_desup=ParecerChoices.INDEFERIDO,
        )
        sincronizar_status_pendencia(self.pendencia)
        self.pendencia.refresh_from_db()
        # Resultado misto => PARCIAL, e só o TCC aprovado (4 orientandos = 2,0h) conta.
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)
        self.assertEqual(self.pendencia.ch_total_justificada, 2.0)


# ════════════════════════════════════════════════════════════════════
# CORR-004 — ch_aprovada: tipo consistente (float), sem TypeError na soma
# ════════════════════════════════════════════════════════════════════
class ChAprovadaTipoConsistenteTests(TestCase):
    """
    Regressão do HTTP 500 ao emitir parecer misturando aprovado/indeferido do
    mesmo professor. Causa-raiz: `ch_aprovada` retornava `float` (quando os
    "aprovados" estavam setados) e `Decimal` (vindo dos DecimalFields). Ao somar
    itens de tipos diferentes → `TypeError: unsupported operand type(s) for +:
    'decimal.Decimal' and 'float'`.
    """

    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade CORR004", sigla="U4")
        self.contrato = ContractType.objects.create(
            nome="ES CORR004", max_class_hours=20, max_classes=10,
        )
        self.professor = Professor.objects.create(
            rh_nome="Docente CORR004",
            rh_email="corr004@teste.com",
            id_funcional="44444",
            rh_matricula="M44444",
            unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre=semestre_atual(),
            sei_numero="SEI-444444/444444/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )

    def test_ch_aprovada_sempre_float_nos_tres_modelos(self):
        """`ch_aprovada` deve ser `float` em todos os caminhos (aprovado e fallback)."""
        # TCC: com aprovados (caminho round -> float) e sem (fallback DecimalField)
        tcc_aprov = OrientacaoTCC.objects.create(
            pendencia=self.pendencia, num_orientandos=4, num_orientandos_aprovados=4,
        )
        tcc_calc = OrientacaoTCC.objects.create(
            pendencia=self.pendencia, num_orientandos=2,
        )
        self.assertIsInstance(tcc_aprov.ch_aprovada, float)
        self.assertIsInstance(tcc_calc.ch_aprovada, float)

        # Extensão: idem
        ext_aprov = AtividadeExtensionista.objects.create(
            pendencia=self.pendencia, num_estudantes=10, num_estudantes_aprovados=6,
        )
        ext_calc = AtividadeExtensionista.objects.create(
            pendencia=self.pendencia, num_estudantes=10,
        )
        self.assertIsInstance(ext_aprov.ch_aprovada, float)
        self.assertIsInstance(ext_calc.ch_aprovada, float)

        # Redução: com aprovadas e sem (fallback horas_reduzidas)
        red = ReducaoCargaHoraria.objects.create(
            pendencia=self.pendencia, motivo_reducao="Lei X",
            horas_reduzidas=Decimal("2.0"),
        )
        self.assertIsInstance(red.ch_aprovada, float)

    def test_ch_total_justificada_com_tipos_mistos_nao_estoura(self):
        """A soma de ch_aprovada de itens de tipos originalmente mistos (float +
        Decimal) não deve levantar TypeError e deve bater o valor esperado."""
        # TCC aprovado -> antes era float
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia, num_orientandos=4, num_orientandos_aprovados=4,
            parecer_desup=ParecerChoices.APROVADO,
        )  # ch_aprovada = 2.0
        # Extensão sem aprovados -> antes caía no Decimal (horas_aprovadas)
        AtividadeExtensionista.objects.create(
            pendencia=self.pendencia, num_estudantes=6,
            parecer_desup=ParecerChoices.APROVADO,
        )  # ch_aprovada = 3.0
        # Redução -> DecimalField
        ReducaoCargaHoraria.objects.create(
            pendencia=self.pendencia, motivo_reducao="Lei Y",
            horas_reduzidas=Decimal("1.5"),
            parecer_desup=ParecerChoices.APROVADO,
        )  # ch_aprovada = 1.5
        self.pendencia.status = PendenciaExtra.StatusChoices.APROVADO
        self.pendencia.save(update_fields=["status"])

        total = self.pendencia.ch_total_justificada  # não pode estourar TypeError
        self.assertIsInstance(total, float)
        self.assertAlmostEqual(total, 2.0 + 3.0 + 1.5)

    def test_formset_clean_soma_mista_nao_estoura_typeerror(self):
        """Reproduz o ponto concreto de crash (BasePendenciaFormSet.clean).

        Cenário do bug: um TCC aprovado (ch_aprovada float) e uma Extensão sem
        aprovados (ch_aprovada Decimal antes do fix). Ao salvar o formset de
        Redução, o clean soma ch_outros = float(tcc) + Decimal(ext) → TypeError.
        Após a normalização, `is_valid()` roda sem exceção.
        """
        OrientacaoTCC.objects.create(
            pendencia=self.pendencia, num_orientandos=4, num_orientandos_aprovados=4,
        )  # float antes do fix
        AtividadeExtensionista.objects.create(
            pendencia=self.pendencia, num_estudantes=6,
        )  # Decimal antes do fix

        data = {
            "red-TOTAL_FORMS": "1",
            "red-INITIAL_FORMS": "0",
            "red-MIN_NUM_FORMS": "0",
            "red-MAX_NUM_FORMS": "1000",
            "red-0-motivo_reducao": "Redução por lei",
            "red-0-horas_reduzidas": "1.0",
        }
        formset = ReducaoCargaHorariaFormSet(
            data, instance=self.pendencia, prefix="red",
        )
        # Antes do fix, is_valid() levantava TypeError dentro de clean().
        self.assertTrue(formset.is_valid(), msg=formset.errors)

    def test_fluxo_parecer_aprovar_tcc_depois_indeferir_extensao(self):
        """Regressão end-to-end do relato: aprovar TCC e, em seguida, indeferir
        uma Extensão do mesmo professor não pode retornar 500."""
        desup = User.objects.create_user(
            email="desup004@teste.com", perfil="DESUP", forcar_troca_senha=False,
        )
        tcc = OrientacaoTCC.objects.create(pendencia=self.pendencia, num_orientandos=4)
        ext = AtividadeExtensionista.objects.create(
            pendencia=self.pendencia, num_estudantes=6,
        )
        client = Client()
        client.force_login(desup)

        # 1) Aprovar o TCC (define num_orientandos_aprovados -> ch_aprovada float)
        url_tcc = reverse(
            "extra_curricular:parecer_tcc",
            kwargs={"pk": self.pendencia.pk, "item_pk": tcc.pk},
        )
        p_tcc = f"ptcc-{tcc.pk}"
        resp1 = client.post(url_tcc, {
            f"{p_tcc}-parecer_desup": ParecerChoices.APROVADO,
            f"{p_tcc}-num_orientandos_aprovados": "4",
            f"{p_tcc}-horas_aprovadas": "",
            f"{p_tcc}-motivo_parecer": "",
        })
        self.assertEqual(resp1.status_code, 302)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.APROVADO)

        # 2) Indeferir a Extensão do mesmo professor -> não pode dar 500
        url_ext = reverse(
            "extra_curricular:parecer_extensao",
            kwargs={"pk": self.pendencia.pk, "item_pk": ext.pk},
        )
        p_ext = f"pext-{ext.pk}"
        resp2 = client.post(url_ext, {
            f"{p_ext}-parecer_desup": ParecerChoices.INDEFERIDO,
            f"{p_ext}-num_estudantes_aprovados": "",
            f"{p_ext}-horas_aprovadas": "",
            f"{p_ext}-motivo_parecer": "Fora do escopo",
        })
        self.assertEqual(resp2.status_code, 302)
        ext.refresh_from_db()
        self.assertEqual(ext.parecer_desup, ParecerChoices.INDEFERIDO)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)


# ══════════════════════════════════════════════════════════════════════════════
# CORR-015 — Filtro "Sem registro" na lista de pendências
# ══════════════════════════════════════════════════════════════════════════════
class FiltroStatusPendenciaTests(TestCase):
    """
    Regressão do CORR-015: filtrar por "Sem registro" não retornava nada.

    Causa-raiz: cada camada usava um vocabulário próprio —
      · `<option value="Sem registro">` no template,
      · `status_filtro == 'sem_registro'` na view,
      · `data-justificativa=""` nas linhas (nunca igual a "Sem registro").
    A correção centralizou os tokens em `services.status_token/justificativa_token`.
    """

    def setUp(self):
        self.client = Client()
        self.unidade = Unidade.objects.create(nome="Unidade CORR015", sigla="U15")
        self.contrato = ContractType.objects.create(
            nome="ES CORR015", max_class_hours=20, max_classes=10,
        )
        self.desup = User.objects.create_user(
            email="desup_corr015@teste.com", perfil="DESUP", forcar_troca_senha=False,
        )
        self.url = reverse("extra_curricular:pendencia_list")

    def _professor(self, sufixo):
        return Professor.objects.create(
            rh_nome=f"Docente {sufixo}",
            rh_email=f"corr015_{sufixo}@teste.com".lower(),
            id_funcional=f"1501{sufixo}",
            rh_matricula=f"M1501{sufixo}",
            unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )

    def _pendencia(self, professor, status):
        return PendenciaExtra.objects.create(
            professor=professor,
            unidade=self.unidade,
            semestre=semestre_atual(),
            sei_numero="SEI-150000/150000/2026",
            status=status,
        )

    def _get(self, **params):
        params.setdefault("semestre", semestre_atual())
        params.setdefault("unidade_id", self.unidade.pk)
        self.client.force_login(self.desup)
        return self.client.get(self.url, params)

    # ── O caso relatado ─────────────────────────────────────────────
    def test_filtro_sem_registro_retorna_professores_sem_pendencia(self):
        """?status=sem_registro deve listar quem não tem PendenciaExtra no semestre."""
        sem_registro = self._professor("A")
        com_pendencia = self._professor("B")
        self._pendencia(com_pendencia, PendenciaExtra.StatusChoices.ENVIADO)

        resp = self._get(status="sem_registro")

        self.assertEqual(resp.status_code, 200)
        nomes = [d["professor"].pk for d in resp.context["pendencias_data"]]
        self.assertIn(sem_registro.pk, nomes)
        self.assertNotIn(com_pendencia.pk, nomes)

    def test_filtro_sem_registro_com_todos_nesse_estado(self):
        """Cenário do relato: todos sem registro → o filtro devolve todos."""
        esperados = {self._professor("C").pk, self._professor("D").pk}

        resp = self._get(status="sem_registro")

        retornados = {d["professor"].pk for d in resp.context["pendencias_data"]}
        self.assertEqual(retornados, esperados)

    # ── Alinhamento entre as 3 camadas ──────────────────────────────
    def test_option_do_select_usa_o_mesmo_token_da_view(self):
        """O <option value> precisa ser exatamente o token comparado no servidor."""
        self._professor("E")
        html = self._get().content.decode()

        self.assertIn('<option value="sem_registro"', html)
        # O value antigo (com espaço e maiúscula) não pode voltar.
        self.assertNotIn('<option value="Sem registro"', html)

    def test_data_status_da_linha_usa_o_mesmo_token(self):
        """O data-status lido pelo filtro em JS usa o token canônico."""
        self._professor("F")
        html = self._get().content.decode()

        self.assertIn('data-status="sem_registro"', html)
        self.assertIn('data-justificativa="sem_registro"', html)

    def test_selected_do_option_bate_com_o_proprio_value(self):
        """Antes, o option marcava selected por 'sem_registro' mas valia 'Sem registro'."""
        self._professor("G")
        html = self._get(status="sem_registro").content.decode()

        self.assertIn('<option value="sem_registro" selected', html)

    # ── Demais opções continuam funcionando ─────────────────────────
    def test_demais_status_continuam_filtrando(self):
        casos = [
            ("rascunho", PendenciaExtra.StatusChoices.RASCUNHO),
            ("pendente", PendenciaExtra.StatusChoices.ENVIADO),
            ("finalizado", PendenciaExtra.StatusChoices.APROVADO),
            ("indeferido", PendenciaExtra.StatusChoices.INDEFERIDO),
        ]
        professores = {}
        for i, (token, status) in enumerate(casos):
            prof = self._professor(f"H{i}")
            self._pendencia(prof, status)
            professores[token] = prof

        for token, prof in professores.items():
            with self.subTest(status=token):
                resp = self._get(status=token)
                retornados = {d["professor"].pk for d in resp.context["pendencias_data"]}
                self.assertEqual(retornados, {prof.pk})

    def test_sem_filtro_retorna_todos(self):
        esperados = {self._professor("I").pk, self._professor("J").pk}
        prof_com = self._professor("K")
        self._pendencia(prof_com, PendenciaExtra.StatusChoices.ENVIADO)
        esperados.add(prof_com.pk)

        resp = self._get()

        retornados = {d["professor"].pk for d in resp.context["pendencias_data"]}
        self.assertEqual(retornados, esperados)

    # ── Tokens por tipo de justificativa ────────────────────────────
    def test_justificativa_token_por_tipo_de_item(self):
        prof = self._professor("L")
        pend = self._pendencia(prof, PendenciaExtra.StatusChoices.ENVIADO)
        OrientacaoTCC.objects.create(pendencia=pend, num_orientandos=2)
        AtividadeExtensionista.objects.create(
            pendencia=pend, num_estudantes=10, carga_horaria=Decimal("2.0"),
        )

        resp = self._get()
        tokens = {d["justificativa_token"] for d in resp.context["pendencias_data"]}

        self.assertIn("tcc", tokens)
        self.assertIn("extensao", tokens)

    def test_status_token_helper(self):
        from apps.extra_curricular.services import justificativa_token, status_token

        self.assertEqual(status_token({"pendencia": None, "status_item": ""}), "sem_registro")
        self.assertEqual(status_token({"pendencia": object(), "status_item": "ENVIADO"}), "pendente")
        self.assertEqual(status_token({"pendencia": object(), "status_item": "PENDENTE"}), "pendente")
        self.assertEqual(status_token({"pendencia": object(), "status_item": "APROVADO"}), "finalizado")
        self.assertEqual(status_token({"pendencia": object(), "status_item": "RASCUNHO"}), "rascunho")
        self.assertEqual(status_token({"pendencia": object(), "status_item": "INDEFERIDO"}), "indeferido")
        # Status desconhecido não pode explodir nem virar outra categoria.
        self.assertEqual(status_token({"pendencia": object(), "status_item": "XPTO"}), "sem_registro")

        self.assertEqual(justificativa_token({"item_tipo": "tcc"}), "tcc")
        self.assertEqual(justificativa_token({"item_tipo": "ext"}), "extensao")
        self.assertEqual(justificativa_token({"item_tipo": "red"}), "reducao")
        self.assertEqual(justificativa_token({}), "sem_registro")


# ══════════════════════════════════════════════════════════════════════════════
# CORR-006 — Cobertura dos pareceres DESUP (combinações e sequências)
# ══════════════════════════════════════════════════════════════════════════════
class ParecerDesupCoberturaTests(TestCase):
    """
    O fluxo de parecer (Autorizar/Indeferir por item, com e sem os campos
    "aprovados" preenchidos) não tinha cobertura suficiente — o HTTP 500 do
    CORR-004 chegou ao cliente. Aqui exercitamos os 3 tipos × os 3 pareceres,
    as sequências entre itens do mesmo professor, o estouro de limite de horas
    e a permissão DESUP-only.
    """

    def setUp(self):
        self.client = Client()
        self.unidade = Unidade.objects.create(nome="Unidade CORR006", sigla="U6")
        self.contrato = ContractType.objects.create(
            nome="ES CORR006", max_class_hours=20, max_classes=10,
        )
        self.professor = Professor.objects.create(
            rh_nome="Docente CORR006",
            rh_email="corr006@teste.com",
            id_funcional="66666",
            rh_matricula="M66666",
            unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre=semestre_atual(),
            sei_numero="SEI-666666/666666/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        self.desup = User.objects.create_user(
            email="desup_corr006@teste.com", perfil="DESUP", forcar_troca_senha=False,
        )
        self.coord = User.objects.create_user(
            email="coord_corr006@teste.com", perfil="COORDENADOR_UNIDADE",
            unidade=self.unidade, forcar_troca_senha=False,
        )

    # ── Fábricas de item ────────────────────────────────────────────
    def _tcc(self, num_orientandos=4):
        return OrientacaoTCC.objects.create(
            pendencia=self.pendencia, num_orientandos=num_orientandos,
        )

    def _ext(self, num_estudantes=10, carga_horaria="2.0"):
        return AtividadeExtensionista.objects.create(
            pendencia=self.pendencia,
            num_estudantes=num_estudantes,
            carga_horaria=Decimal(carga_horaria),
        )

    def _red(self, horas="2.0"):
        return ReducaoCargaHoraria.objects.create(
            pendencia=self.pendencia,
            motivo_reducao="Coordenação de curso",
            horas_reduzidas=Decimal(horas),
        )

    # ── POST de parecer, por tipo ───────────────────────────────────
    def _post_parecer(self, tipo, item, parecer, aprovados=None, motivo="", user=None):
        rotas = {
            "tcc": ("extra_curricular:parecer_tcc", "ptcc", "num_orientandos_aprovados"),
            "ext": ("extra_curricular:parecer_extensao", "pext", "num_estudantes_aprovados"),
            "red": ("extra_curricular:parecer_reducao", "pred", None),
        }
        url_name, prefixo, campo_aprovados = rotas[tipo]
        self.client.force_login(user or self.desup)
        url = reverse(url_name, kwargs={"pk": self.pendencia.pk, "item_pk": item.pk})
        p = f"{prefixo}-{item.pk}"
        data = {
            f"{p}-parecer_desup": parecer,
            f"{p}-horas_aprovadas": "" if aprovados is None or campo_aprovados else str(aprovados),
            f"{p}-motivo_parecer": motivo,
        }
        if campo_aprovados:
            data[f"{p}-{campo_aprovados}"] = "" if aprovados is None else str(aprovados)
        return self.client.post(url, data)

    # ── Matriz tipo × parecer ───────────────────────────────────────
    def test_cada_tipo_com_cada_parecer_sem_aprovados_preenchidos(self):
        """3 tipos × 3 pareceres, deixando os campos "aprovados" vazios."""
        for parecer in (ParecerChoices.APROVADO, ParecerChoices.INDEFERIDO, ParecerChoices.PENDENTE):
            for tipo, fabrica in (("tcc", self._tcc), ("ext", self._ext), ("red", self._red)):
                with self.subTest(tipo=tipo, parecer=parecer):
                    item = fabrica()
                    resp = self._post_parecer(tipo, item, parecer)
                    self.assertEqual(resp.status_code, 302)   # nunca 500
                    item.refresh_from_db()
                    self.assertEqual(item.parecer_desup, parecer)
                    item.delete()

    def test_cada_tipo_com_cada_parecer_com_aprovados_preenchidos(self):
        """Mesma matriz, agora informando os valores aprovados pela DESUP."""
        casos = [
            ("tcc", self._tcc, 2),      # 2 orientandos aprovados
            ("ext", self._ext, 5),      # 5 estudantes aprovados
            ("red", self._red, "1.5"),  # horas_aprovadas direto
        ]
        for parecer in (ParecerChoices.APROVADO, ParecerChoices.INDEFERIDO, ParecerChoices.PENDENTE):
            for tipo, fabrica, aprovados in casos:
                with self.subTest(tipo=tipo, parecer=parecer):
                    item = fabrica()
                    resp = self._post_parecer(tipo, item, parecer, aprovados=aprovados)
                    self.assertEqual(resp.status_code, 302)
                    item.refresh_from_db()
                    self.assertEqual(item.parecer_desup, parecer)
                    self.assertIsInstance(item.ch_aprovada, float)   # CORR-004
                    item.delete()

    # ── Sequências entre itens do mesmo professor ───────────────────
    def test_aprovar_tcc_depois_indeferir_reducao(self):
        """Variante do CORR-004 com Redução no lugar da Extensão."""
        tcc = self._tcc()
        red = self._red()

        self.assertEqual(
            self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=2).status_code, 302,
        )
        self.assertEqual(
            self._post_parecer("red", red, ParecerChoices.INDEFERIDO, motivo="Fora do escopo").status_code, 302,
        )

        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)

    def test_tres_itens_todos_aprovados_consolidam_aprovado(self):
        tcc, ext, red = self._tcc(), self._ext(), self._red()

        self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=1)
        self._post_parecer("ext", ext, ParecerChoices.APROVADO, aprovados=5)
        self._post_parecer("red", red, ParecerChoices.APROVADO, aprovados="1.0")

        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.APROVADO)

    def test_um_indeferido_entre_tres_consolida_em_parcial(self):
        tcc, ext, red = self._tcc(), self._ext(), self._red()

        self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=1)
        self._post_parecer("ext", ext, ParecerChoices.APROVADO, aprovados=5)
        self._post_parecer("red", red, ParecerChoices.INDEFERIDO, motivo="Não comprovado")

        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)

    def test_ordem_dos_pareceres_nao_muda_o_consolidado(self):
        """A ordem não importa: aprovado + indeferido consolida em PARCIAL (CORR-023)."""
        tcc, ext = self._tcc(), self._ext()

        self._post_parecer("ext", ext, ParecerChoices.INDEFERIDO, motivo="Fora do escopo")
        self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=2)

        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)

    def test_item_pendente_mantem_pendencia_em_enviado(self):
        tcc, ext = self._tcc(), self._ext()

        self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=2)
        self._post_parecer("ext", ext, ParecerChoices.PENDENTE)

        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.ENVIADO)

    # ── Limite de horas extras ──────────────────────────────────────
    def test_estouro_de_limite_gera_mensagem_e_nao_500(self):
        """Aprovar acima de `limite_horas_extra_efetivo` deve avisar, não quebrar."""
        self.professor.limite_horas_extra = Decimal("1.0")
        self.professor.save(update_fields=["limite_horas_extra"])

        tcc = self._tcc(num_orientandos=8)          # 8 × 0,5h = 4h > 1h
        resp = self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=8)

        self.assertEqual(resp.status_code, 302)
        tcc.refresh_from_db()
        # O parecer NÃO é gravado quando estoura o limite.
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)
        mensagens = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Limite de horas extras excedido" in m for m in mensagens))

    def test_soma_de_itens_respeita_o_limite(self):
        """O limite considera os OUTROS itens já aprovados do mesmo professor."""
        self.professor.limite_horas_extra = Decimal("2.0")
        self.professor.save(update_fields=["limite_horas_extra"])

        tcc = self._tcc(num_orientandos=4)          # 2h aprovadas
        ext = self._ext(carga_horaria="2.0")        # +2h => 4h > 2h

        self.assertEqual(
            self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=4).status_code, 302,
        )
        resp = self._post_parecer("ext", ext, ParecerChoices.APROVADO, aprovados=10)

        ext.refresh_from_db()
        self.assertEqual(ext.parecer_desup, ParecerChoices.PENDENTE)   # bloqueado
        mensagens = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("Limite de horas extras excedido" in m for m in mensagens))

    # ── Consistência de tipo (regressão CORR-004) ───────────────────
    def test_soma_de_ch_aprovada_nunca_levanta_typeerror(self):
        tcc = self._tcc(num_orientandos=4)
        ext = self._ext()
        red = self._red()

        self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, aprovados=2)   # float
        self._post_parecer("ext", ext, ParecerChoices.APROVADO)                # fallback Decimal
        self._post_parecer("red", red, ParecerChoices.APROVADO)                # fallback Decimal

        for item in (tcc, ext, red):
            item.refresh_from_db()
            self.assertIsInstance(item.ch_aprovada, float)

        self.pendencia.refresh_from_db()
        total = self.pendencia.ch_total_justificada   # não pode estourar TypeError
        self.assertIsInstance(float(total), float)
        self.assertGreater(total, 0)

    # ── Permissão ───────────────────────────────────────────────────
    def test_apenas_desup_emite_parecer(self):
        tcc = self._tcc()

        resp = self._post_parecer("tcc", tcc, ParecerChoices.APROVADO, user=self.coord)

        # PerfilRequiredMixin levanta PermissionDenied -> 403. Aceitar 302 aqui
        # deixaria passar um refactor que removesse a trava de perfil.
        self.assertEqual(resp.status_code, 403)
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)   # nada gravado

    def test_anonimo_nao_emite_parecer(self):
        tcc = self._tcc()
        self.client.logout()
        url = reverse(
            "extra_curricular:parecer_tcc",
            kwargs={"pk": self.pendencia.pk, "item_pk": tcc.pk},
        )

        resp = self.client.post(url, {})

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])
        tcc.refresh_from_db()
        self.assertEqual(tcc.parecer_desup, ParecerChoices.PENDENTE)

    def test_item_de_outra_pendencia_da_404(self):
        outra = PendenciaExtra.objects.create(
            professor=self.professor,
            unidade=self.unidade,
            semestre="2020.1",
            sei_numero="SEI-000000/000000/2020",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        tcc = self._tcc()
        self.client.force_login(self.desup)
        url = reverse(
            "extra_curricular:parecer_tcc",
            kwargs={"pk": outra.pk, "item_pk": tcc.pk},
        )

        self.assertEqual(self.client.post(url, {}).status_code, 404)


class ParecerReducaoNaoAprovaMaisQueSolicitadoTests(TestCase):
    """
    Mesma regra já aplicada a TCC e Extensão: a DESUP defere no máximo o que foi
    pedido. A redução tinha ficado de fora — aprovar mais horas do que as
    solicitadas inventa CH que ninguém pediu e ainda consome o limite do docente.
    """

    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade RED", sigla="URD")
        self.contrato = ContractType.objects.create(
            nome="ES RED", max_class_hours=20, max_classes=10,
        )
        self.professor = Professor.objects.create(
            rh_nome="Docente RED", rh_email="red@teste.com", id_funcional="77777",
            rh_matricula="M77777", unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor, unidade=self.unidade, semestre=semestre_atual(),
            sei_numero="SEI-777777/777777/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )
        self.reducao = ReducaoCargaHoraria.objects.create(
            pendencia=self.pendencia, motivo_reducao="Coordenação",
            horas_reduzidas=Decimal("2.0"),
        )

    def _form(self, horas_aprovadas):
        from apps.extra_curricular.forms import ParecerReducaoForm
        return ParecerReducaoForm(
            data={
                "parecer_desup": ParecerChoices.APROVADO,
                "horas_aprovadas": horas_aprovadas,
                "motivo_parecer": "",
            },
            instance=self.reducao,
        )

    def test_recusa_aprovar_mais_horas_do_que_o_solicitado(self):
        form = self._form("10.0")

        self.assertFalse(form.is_valid())
        self.assertIn("horas_aprovadas", form.errors)
        self.assertIn("solicitadas apenas 2.0h", str(form.errors["horas_aprovadas"]))

    def test_aceita_aprovar_o_solicitado(self):
        self.assertTrue(self._form("2.0").is_valid())

    def test_aceita_aprovar_menos_que_o_solicitado(self):
        self.assertTrue(self._form("1.5").is_valid())


# ══════════════════════════════════════════════════════════════════════════════
# CORR-023 — Aprovação parcial: item indeferido não zera o que foi aprovado
# ══════════════════════════════════════════════════════════════════════════════
class AprovacaoParcialTests(TestCase):
    """
    Antes, `any(INDEFERIDO)` derrubava a pendência inteira para INDEFERIDO e
    `ch_total_justificada` zerava fora de APROVADO — ou seja, um único item
    indeferido apagava TODA a CH que a DESUP já tinha deferido nos outros itens.
    Agora o resultado misto tem estado próprio (`PARCIAL`) e o que foi aprovado
    continua contando.
    """

    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade PARC", sigla="UPC")
        self.contrato = ContractType.objects.create(
            nome="ES PARC", max_class_hours=20, max_classes=10,
        )
        self.professor = Professor.objects.create(
            rh_nome="Docente PARC", rh_email="parc@teste.com", id_funcional="88888",
            rh_matricula="M88888", unidade_principal=self.unidade,
            tipo_contrato=self.contrato,
        )
        self.pendencia = PendenciaExtra.objects.create(
            professor=self.professor, unidade=self.unidade, semestre=semestre_atual(),
            sei_numero="SEI-888888/888888/2026",
            status=PendenciaExtra.StatusChoices.ENVIADO,
        )

    def _tcc(self, parecer, num=4, aprovados=None):
        return OrientacaoTCC.objects.create(
            pendencia=self.pendencia, num_orientandos=num,
            num_orientandos_aprovados=aprovados, parecer_desup=parecer,
        )

    def _reducao(self, parecer, horas="2.0", aprovadas=None):
        return ReducaoCargaHoraria.objects.create(
            pendencia=self.pendencia, motivo_reducao="Coordenação",
            horas_reduzidas=Decimal(horas),
            horas_aprovadas=Decimal(aprovadas) if aprovadas is not None else None,
            parecer_desup=parecer,
        )

    # ── O caso que o cliente pediu ──────────────────────────────────
    def test_item_indeferido_nao_zera_a_ch_do_item_aprovado(self):
        self._tcc(ParecerChoices.APROVADO, num=8, aprovados=8)   # 4.0h deferidas
        self._reducao(ParecerChoices.INDEFERIDO, horas="2.0")     # não conta

        status = sincronizar_status_pendencia(self.pendencia)
        self.pendencia.refresh_from_db()

        self.assertEqual(status, PendenciaExtra.StatusChoices.PARCIAL)
        self.assertEqual(self.pendencia.ch_total_justificada, 4.0)
        self.assertEqual(self.professor.ch_justificada, 4.0)

    # ── Os extremos continuam como antes ────────────────────────────
    def test_todos_aprovados_continua_aprovado(self):
        self._tcc(ParecerChoices.APROVADO, num=4, aprovados=4)    # 2.0h
        self._reducao(ParecerChoices.APROVADO, horas="1.0", aprovadas="1.0")

        self.assertEqual(
            sincronizar_status_pendencia(self.pendencia),
            PendenciaExtra.StatusChoices.APROVADO,
        )
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.ch_total_justificada, 3.0)

    def test_todos_indeferidos_continua_indeferido_e_zera(self):
        self._tcc(ParecerChoices.INDEFERIDO)
        self._reducao(ParecerChoices.INDEFERIDO)

        self.assertEqual(
            sincronizar_status_pendencia(self.pendencia),
            PendenciaExtra.StatusChoices.INDEFERIDO,
        )
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)

    def test_item_ainda_pendente_mantem_em_analise(self):
        """Sem todos os itens julgados, não é PARCIAL — a análise não acabou."""
        self._tcc(ParecerChoices.APROVADO, num=4, aprovados=4)
        self._reducao(ParecerChoices.INDEFERIDO)
        self._reducao(ParecerChoices.PENDENTE, horas="3.0")

        self.assertEqual(
            sincronizar_status_pendencia(self.pendencia),
            PendenciaExtra.StatusChoices.ENVIADO,
        )
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)

    # ── Interações com o resto do fluxo ─────────────────────────────
    def test_rascunho_nao_vira_parcial(self):
        self.pendencia.status = PendenciaExtra.StatusChoices.RASCUNHO
        self.pendencia.save(update_fields=["status"])
        self._tcc(ParecerChoices.APROVADO, num=4, aprovados=4)
        self._reducao(ParecerChoices.INDEFERIDO)

        self.assertEqual(
            sincronizar_status_pendencia(self.pendencia),
            PendenciaExtra.StatusChoices.RASCUNHO,
        )

    def test_reabrir_aceita_pendencia_parcial(self):
        self._tcc(ParecerChoices.APROVADO, num=8, aprovados=8)
        self._reducao(ParecerChoices.INDEFERIDO)
        sincronizar_status_pendencia(self.pendencia)
        self.pendencia.refresh_from_db()
        self.assertEqual(self.pendencia.status, PendenciaExtra.StatusChoices.PARCIAL)

        desup = User.objects.create_user(
            email="desup_parc@teste.com", perfil="DESUP", forcar_troca_senha=False,
        )
        client = Client()
        client.force_login(desup)
        resp = client.post(
            reverse("extra_curricular:reabrir_pendencia", kwargs={"pk": self.pendencia.pk})
        )

        self.assertEqual(resp.status_code, 302)
        self.pendencia.refresh_from_db()
        self.assertNotIn(self.pendencia.status, PendenciaExtra.STATUS_FINALIZADOS)
        # Reaberta, a CH aprovada deixa de contar até nova decisão.
        self.assertEqual(self.pendencia.ch_total_justificada, 0.0)

    def test_token_de_filtro_do_parcial(self):
        from apps.extra_curricular.services import status_token

        self.assertEqual(
            status_token({"pendencia": self.pendencia, "status_item": "PARCIAL"}),
            "parcial",
        )
