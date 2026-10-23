from django.conf import settings
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


class AlocacaoTurmaDocente(models.Model):
    """
    Oferta de um componente da matriz em uma turma, com o docente responsável.

    Substitui o antigo vínculo direto `MatrixComponent.docente`, permitindo
    várias turmas (e vários docentes) por componente. `docente` nulo indica
    oferta ainda sem professor (ver `Carencia`).
    """

    alocacao_curricular = models.ForeignKey(
        AlocacaoCurricular,
        on_delete=models.CASCADE,
        related_name='alocacoes_turma_docente',
        verbose_name="Alocação curricular",
    )
    componente_matriz = models.ForeignKey(
        'courses.MatrixComponent',
        on_delete=models.PROTECT,
        related_name='alocacoes_turma_docente',
        verbose_name="Componente da matriz",
    )
    turma = models.ForeignKey(
        'courses.ClassGroup',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='alocacoes_turma_docente',
        verbose_name="Turma",
    )
    docente = models.ForeignKey(
        'professors.Professor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='alocacoes_turma_docente',
        verbose_name="Docente",
    )
    carga_horaria_contabilizada = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name="Carga horária contabilizada",
    )
    compartilhado = models.BooleanField(default=False, verbose_name="Compartilhado")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "harpiadb_alocacoes_alocacao_turma_docente"
        verbose_name = "Alocação de Turma e Docente"
        verbose_name_plural = "Alocações de Turma e Docente"
        constraints = [
            models.UniqueConstraint(
                fields=['alocacao_curricular', 'componente_matriz', 'turma', 'docente'],
                name='harpia_alocturmadocente_unica',
            ),
            # Em SQL, NULL não colide em UNIQUE: sem este índice parcial seria
            # possível duplicar a oferta "sem turma" do mesmo docente.
            models.UniqueConstraint(
                fields=['alocacao_curricular', 'componente_matriz', 'docente'],
                condition=models.Q(turma__isnull=True),
                name='harpia_alocturmadocente_unica_sem_turma',
            ),
        ]

    def __str__(self):
        docente = self.docente.nome if self.docente_id else 'Sem professor'
        return f"{self.componente_matriz} - {docente}"


class Carencia(models.Model):
    """Necessidade institucional de docente ("Sem professor") para uma oferta."""

    class StatusChoices(models.TextChoices):
        DECLARADA = 'DECLARADA', 'Declarada'
        EM_ANALISE = 'EM_ANALISE', 'Em análise'
        HOMOLOGADA = 'HOMOLOGADA', 'Homologada'
        RESOLVIDA = 'RESOLVIDA', 'Resolvida'

    alocacao_turma_docente = models.OneToOneField(
        AlocacaoTurmaDocente,
        on_delete=models.CASCADE,
        related_name='carencia',
        verbose_name="Alocação de turma e docente",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DECLARADA,
    )
    justificativa_unidade = models.TextField(blank=True, verbose_name="Justificativa da unidade")
    parecer_desup = models.TextField(blank=True, verbose_name="Parecer da DESUP")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "harpiadb_alocacoes_carencia"
        verbose_name = "Carência"
        verbose_name_plural = "Carências"

    def __str__(self):
        return f"Carência ({self.get_status_display()}) - {self.alocacao_turma_docente}"


class SolicitacaoRAT(models.Model):
    """Solicitação de Regime Adicional de Trabalho para suprir uma carência."""

    class StatusChoices(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        AGUARDANDO_DESUP = 'AGUARDANDO_DESUP', 'Aguardando DESUP'
        APROVADO = 'APROVADO', 'Aprovado'
        REJEITADO = 'REJEITADO', 'Rejeitado'

    carencia = models.ForeignKey(
        Carencia,
        on_delete=models.CASCADE,
        related_name='solicitacoes_rat',
    )
    professor = models.ForeignKey(
        'professors.Professor',
        on_delete=models.PROTECT,
        related_name='solicitacoes_rat',
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='solicitacoes_rat_feitas',
    )
    avaliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='solicitacoes_rat_avaliadas',
    )
    carga_horaria_solicitada = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.RASCUNHO,
    )
    data_solicitacao = models.DateTimeField(default=timezone.now)
    data_avaliacao = models.DateTimeField(null=True, blank=True)
    motivo_parecer = models.TextField(blank=True)

    class Meta:
        db_table = "harpiadb_alocacoes_solicitacao_rat"
        verbose_name = "Solicitação de RAT"
        verbose_name_plural = "Solicitações de RAT"
        ordering = ['-data_solicitacao']

    def __str__(self):
        return f"RAT {self.professor_id} - {self.get_status_display()}"
