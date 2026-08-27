from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.allocations.models import AlocacaoCurricular
from apps.core.models import JanelaEntrega, Unidade
from apps.courses.models import Course, CourseUnit


class SEIRuleTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Unidade S", sigla="US")
        self.curso_global = Course.objects.create(nome="Curso T", sigla="CT")
        self.curso = CourseUnit.objects.create(curso=self.curso_global, unidade=self.unidade)

    def test_sei_format_validation(self):
        """Regra #8: o campo SEI deve seguir o formato SEI-999999/999999/9999."""
        # Teste falha com formato inválido
        alocacao_invalida = AlocacaoCurricular(
            unidade=self.unidade,
            curso=self.curso,
            semestre="2026.1",
            turno="M",
            sei_numero="FORMATO-ERRADO",
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            alocacao_invalida.full_clean()

        # Teste sucesso com formato válido
        alocacao_valida = AlocacaoCurricular(
            unidade=self.unidade,
            curso=self.curso,
            semestre="2026.1",
            turno="M",
            sei_numero="SEI-123456/123456/2026",
        )
        alocacao_valida.full_clean()

    def test_can_send_with_sei_inside_matrix_window(self):
        """Carga horaria justificada pode ser enviada ate o fechamento da matriz."""
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje,
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade,
            curso=self.curso,
            semestre="2026.1",
            turno="M",
            sei_numero="SEI-123456/123456/2026",
        )

        can_send, msg = alocacao.can_be_sent()

        self.assertTrue(can_send)
        self.assertEqual(msg, "")

    def test_cannot_send_without_sei_even_inside_matrix_window(self):
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje + timedelta(days=1),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade,
            curso=self.curso,
            semestre="2026.1",
            turno="M",
        )

        can_send, msg = alocacao.can_be_sent()

        self.assertFalse(can_send)
        self.assertIn("SEI", msg)
        self.assertFalse(alocacao.is_rascunho_expirado)

    def test_cannot_send_after_matrix_window_closes(self):
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje - timedelta(days=10),
            data_fim=hoje - timedelta(days=1),
            status=JanelaEntrega.StatusChoices.ABERTO,
        )
        alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade,
            curso=self.curso,
            semestre="2026.1",
            turno="M",
            sei_numero="SEI-123456/123456/2026",
        )

        can_send, msg = alocacao.can_be_sent()

        self.assertFalse(can_send)
        self.assertIn("fechado", msg)

    def test_can_send_after_matrix_reopens_for_unit(self):
        hoje = timezone.now().date()
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje - timedelta(days=10),
            data_fim=hoje - timedelta(days=1),
            status=JanelaEntrega.StatusChoices.FECHADO,
        )
        JanelaEntrega.objects.create(
            semestre="2026.1",
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=2),
            status=JanelaEntrega.StatusChoices.REABERTO,
            unidade=self.unidade,
        )
        alocacao = AlocacaoCurricular.objects.create(
            unidade=self.unidade,
            curso=self.curso,
            semestre="2026.1",
            turno="M",
            sei_numero="SEI-123456/123456/2026",
        )

        can_send, msg = alocacao.can_be_sent()

        self.assertTrue(can_send)
        self.assertEqual(msg, "")
