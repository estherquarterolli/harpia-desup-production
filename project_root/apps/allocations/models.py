from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.core.models import JanelaEntrega, UnitBoundManager


class AlocacaoCurricular(models.Model):
    """
    Representa a alocacao consolidada de um curso/turno em um semestre (Regra #8).
    """

    class StatusChoices(models.TextChoices):
        RASCUNHO = 'Rascunho', 'Rascunho'
        ENVIADO = 'Enviado', 'Enviado para DESUP'
        APROVADO = 'Aprovado', 'Aprovado pela DESUP'

    unidade = models.ForeignKey('core.Unidade', on_delete=models.CASCADE, related_name='alocacoes_consolidadas')
    curso = models.ForeignKey('courses.CourseUnit', on_delete=models.CASCADE)
    semestre = models.CharField(max_length=10)  # Ex: 2026.1
    turno = models.CharField(max_length=1, choices=[('M', 'Manhã'), ('T', 'Tarde'), ('N', 'Noite')])

    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.RASCUNHO)

    # Regra #8: SEI e obrigatorio e deve seguir o formato SEI-999999/999999/9999
    sei_numero = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Número SEI",
        validators=[            
            RegexValidator(
                regex=r'^SEI-\d{6}/\d{6}/\d{4}$',
                message="O formato do SEI deve ser SEI-999999/999999/9999"
            )
        ],
    )

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_ultimo_ajuste = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "harpiadb_alocacoes_alocacao_curricular"
        verbose_name = "Alocação Curricular"
        verbose_name_plural = "Alocações Curriculares"
        unique_together = ('curso', 'semestre', 'turno')
        ordering = ['-semestre', 'curso']

    objects = UnitBoundManager()

    def __str__(self):
        return f"{self.curso.sigla} - {self.get_turno_display()} ({self.semestre})"

    @property
    def is_rascunho_expirado(self):
        """Mantido por compatibilidade: rascunho nao expira por prazo fixo de SEI."""
        return False

    @property
    def janela_matriz_ativa(self):
        """Retorna True quando a matriz do semestre/unidade ainda aceita envio."""
        hoje = timezone.now().date()
        return JanelaEntrega.objects.filter(
            semestre=self.semestre,
            status__in=[
                JanelaEntrega.StatusChoices.ABERTO,
                JanelaEntrega.StatusChoices.REABERTO,
            ],
            data_inicio__lte=hoje,
            data_fim__gte=hoje,
        ).filter(
            models.Q(unidade=self.unidade) | models.Q(unidade__isnull=True)
        ).exists()

    def can_add_carga_horaria_justificada(self):
        """Carga horaria justificada segue o mesmo fechamento/reabertura da matriz."""
        if not self.janela_matriz_ativa:
            return False, "O prazo para adicionar carga horaria justificada esta fechado."

        return True, ""

    def can_be_sent(self):
        """Valida se pode ser enviado para a DESUP (Regra #8)."""
        if not self.sei_numero:
            return False, "O numero SEI e obrigatorio para envio definitivo."

        can_add_justificada, msg = self.can_add_carga_horaria_justificada()
        if not can_add_justificada:
            return False, msg


        return True, ""
