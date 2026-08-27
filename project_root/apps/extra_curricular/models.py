"""
Models para Alocação Extra-Curricular.

Estrutura:
    PendenciaExtra  ← agrupa as justificativas de 1 professor num semestre
        OrientacaoTCC           (0.5h/orientando, máx 8 alunos / 4h)
        AtividadeExtensionista  (0.5h/estudante, sem limite)
        ReducaoCargaHoraria     (horas reduzidas por lei/aprovação)
"""
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models
from django.core.exceptions import ValidationError


# ────────────────────────────────────────────────────────────────────────────────
# Choices reutilizáveis
# ────────────────────────────────────────────────────────────────────────────────
class ParecerChoices(models.TextChoices):
    PENDENTE  = "PENDENTE",  "Pendente"
    APROVADO  = "APROVADO",  "Aprovado"


# ────────────────────────────────────────────────────────────────────────────────
# PendenciaExtra — cabeçalho / agrupador por professor + semestre
# ────────────────────────────────────────────────────────────────────────────────
class PendenciaExtra(models.Model):
    """
    Agrupa as justificativas extracurriculares de um professor num semestre.
    Criada pelo Coordenador de Unidade; avaliada pela DESUP.
    """

    class StatusChoices(models.TextChoices):
        RASCUNHO  = "RASCUNHO",  "Rascunho"
        ENVIADO   = "ENVIADO",   "Enviado para DESUP"
        APROVADO  = "APROVADO",  "Finalizado"

    professor = models.ForeignKey(
        "professors.Professor",
        on_delete=models.CASCADE,
        related_name="pendencias_extra",
        verbose_name="Docente",
    )
    unidade = models.ForeignKey(
        "core.Unidade",
        on_delete=models.CASCADE,
        related_name="pendencias_extra",
        verbose_name="Unidade",
    )
    semestre = models.CharField(
        max_length=10,
        verbose_name="Semestre",
        help_text="Ex: 2026.1",
    )
    sei_numero = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Número SEI",
        help_text="Formato: SEI-999999/999999/9999",
        validators=[
            RegexValidator(
                regex=r"^SEI-\d{6}/\d{6}/\d{4}$",
                message="O formato do SEI deve ser SEI-999999/999999/9999",
            )
        ],
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.RASCUNHO,
        verbose_name="Status",
    )
    motivo_status_desup = models.TextField(
        blank=True,
        verbose_name="Motivo da decisao DESUP",
    )
    criado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pendencias_criadas",
        verbose_name="Criado por",
    )
    data_criacao    = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    data_atualizacao = models.DateTimeField(auto_now=True,    verbose_name="Atualizado em")

    class Meta:
        verbose_name          = "Pendência Extracurricular"
        verbose_name_plural   = "Pendências Extracurriculares"
        unique_together       = ("professor", "semestre")
        ordering              = ["-semestre", "professor__rh_nome"]

    def __str__(self):
        return f"{self.professor.nome} — {self.semestre} [{self.get_status_display()}]"

    @property
    def ch_total_justificada(self):
        """Soma de toda CH justificada nesta pendência (usa horas aprovadas pela DESUP)."""
        if self.status != self.StatusChoices.APROVADO:
            return 0.0
        tcc     = sum(t.ch_aprovada for t in self.orientacoes_tcc.all())
        ext     = sum(e.ch_aprovada for e in self.atividades_extensao.all())
        red     = sum(r.ch_aprovada for r in self.reducoes_ch.all())
        return float(tcc) + float(ext) + float(red)

    @property
    def ch_faltante(self):
        """CH que ainda falta cobrir após as justificativas."""
        limite = self.professor.limite_horas_extra_efetivo
        return max(limite - self.ch_total_justificada, 0)


# ────────────────────────────────────────────────────────────────────────────────
# OrientacaoTCC
# ────────────────────────────────────────────────────────────────────────────────
class OrientacaoTCC(models.Model):
    """
    Justificativa por orientação de TCC.
    Regra: 0,5h por orientando | máx 8 orientandos (≤ 4h).
    Somente para TCCs previstos no PPC fora da matriz curricular.
    """
    pendencia = models.ForeignKey(
        PendenciaExtra,
        on_delete=models.CASCADE,
        related_name="orientacoes_tcc",
        verbose_name="Pendência",
    )
    num_orientandos = models.PositiveSmallIntegerField(
        verbose_name="Nº de Orientandos",
        validators=[MaxValueValidator(8)],
        help_text="Máximo de 8 orientandos por professor.",
    )
    num_orientandos_aprovados = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Orientandos Aprovados",
        validators=[MaxValueValidator(8)],
        help_text="Nº de orientandos aprovados pela DESUP. Se vazio, usa o total solicitado.",
    )
    carga_horaria = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        editable=False,
        verbose_name="Carga Horária (h)",
        help_text="Calculado automaticamente: orientandos × 0,5 (máx 4h).",
    )
    horas_aprovadas = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Horas Aprovadas (DESUP)",
        help_text="Valor definido pela DESUP. Se vazio, usa o valor calculado.",
    )
    # Parecer — exclusivo DESUP
    parecer_desup  = models.CharField(
        max_length=20,
        choices=ParecerChoices.choices,
        default=ParecerChoices.PENDENTE,
        verbose_name="Parecer DESUP",
    )
    motivo_parecer = models.TextField(
        blank=True,
        verbose_name="Motivo do Parecer",
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Orientação de TCC"
        verbose_name_plural = "Orientações de TCC"

    @property
    def ch_aprovada(self):
        """Retorna horas aprovadas pela DESUP, ou o valor calculado se não definido."""
        if self.num_orientandos_aprovados is not None:
            return min(round(self.num_orientandos_aprovados * 0.5, 1), 4.0)
        if self.horas_aprovadas is not None:
            return self.horas_aprovadas
        return self.carga_horaria

    def clean(self):
        if self.num_orientandos and self.num_orientandos > 8:
            raise ValidationError(
                {"num_orientandos": "O máximo permitido é 8 orientandos por professor."}
            )

    def save(self, *args, **kwargs):
        # Calcular CH automaticamente (0.5h por orientando, máx 4h)
        if self.num_orientandos:
            self.carga_horaria = min(round(self.num_orientandos * 0.5, 1), 4.0)
        else:
            self.carga_horaria = 0.0
        
        # Atualizar horas_aprovadas com base no num_orientandos_aprovados ou carga_horaria
        if self.num_orientandos_aprovados is not None:
            self.horas_aprovadas = min(round(self.num_orientandos_aprovados * 0.5, 1), 4.0)
        elif self.horas_aprovadas is None:
            self.horas_aprovadas = self.carga_horaria
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"TCC — {self.pendencia.professor.nome} ({self.num_orientandos} orientandos)"


# ────────────────────────────────────────────────────────────────────────────────
# AtividadeExtensionista
# ────────────────────────────────────────────────────────────────────────────────
class AtividadeExtensionista(models.Model):
    """
    Justificativa por atividade extensionista.
    Regra: 0,5h por estudante | sem limite de alunos.
    Somente para atividades fora da matriz (Resolução CNE/CES nº 7).
    """
    pendencia = models.ForeignKey(
        PendenciaExtra,
        on_delete=models.CASCADE,
        related_name="atividades_extensao",
        verbose_name="Pendência",
    )
    num_estudantes = models.PositiveIntegerField(
        verbose_name="Nº de Estudantes",
    )
    num_estudantes_aprovados = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Estudantes Aprovados",
        help_text="Nº de estudantes aprovados pela DESUP. Se vazio, usa o total solicitado.",
    )
    carga_horaria = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        editable=False,
        verbose_name="Carga Horária (h)",
        help_text="Calculado automaticamente: estudantes × 0,5.",
    )
    horas_aprovadas = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Horas Aprovadas (DESUP)",
        help_text="Valor definido pela DESUP. Se vazio, usa o valor calculado.",
    )
    # Parecer — exclusivo DESUP
    parecer_desup  = models.CharField(
        max_length=20,
        choices=ParecerChoices.choices,
        default=ParecerChoices.PENDENTE,
        verbose_name="Parecer DESUP",
    )
    motivo_parecer = models.TextField(
        blank=True,
        verbose_name="Motivo do Parecer",
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Atividade Extensionista"
        verbose_name_plural = "Atividades Extensionistas"

    @property
    def ch_aprovada(self):
        """Retorna horas aprovadas pela DESUP, ou o valor calculado se não definido."""
        if self.num_estudantes_aprovados is not None:
            return round(self.num_estudantes_aprovados * 0.5, 1)
        if self.horas_aprovadas is not None:
            return self.horas_aprovadas
        return self.carga_horaria

    def save(self, *args, **kwargs):
        if self.num_estudantes:
            self.carga_horaria = round(self.num_estudantes * 0.5, 1)
        else:
            self.carga_horaria = 0.0
        
        # Atualizar horas_aprovadas com base no num_estudantes_aprovados ou carga_horaria
        if self.num_estudantes_aprovados is not None:
            self.horas_aprovadas = round(self.num_estudantes_aprovados * 0.5, 1)
        elif self.horas_aprovadas is None:
            self.horas_aprovadas = self.carga_horaria
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Extensão — {self.pendencia.professor.nome} ({self.num_estudantes} estudantes)"


# ────────────────────────────────────────────────────────────────────────────────
# ReducaoCargaHoraria
# ────────────────────────────────────────────────────────────────────────────────
class ReducaoCargaHoraria(models.Model):
    """
    Justificativa por redução de carga horária prevista em lei ou aprovada.
    """
    pendencia = models.ForeignKey(
        PendenciaExtra,
        on_delete=models.CASCADE,
        related_name="reducoes_ch",
        verbose_name="Pendência",
    )
    motivo_reducao = models.TextField(
        verbose_name="Motivo da Redução",
        help_text="Descreva a legislação ou aprovação que fundamenta a redução.",
    )
    horas_reduzidas = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        verbose_name="Horas de Aula Reduzidas",
    )
    horas_aprovadas = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Horas Aprovadas (DESUP)",
        help_text="Valor definido pela DESUP. Se vazio, usa o valor solicitado.",
    )
    # Parecer — exclusivo DESUP
    parecer_desup  = models.CharField(
        max_length=20,
        choices=ParecerChoices.choices,
        default=ParecerChoices.PENDENTE,
        verbose_name="Parecer DESUP",
    )
    motivo_parecer = models.TextField(
        blank=True,
        verbose_name="Motivo do Parecer",
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Redução de Carga Horária"
        verbose_name_plural = "Reduções de Carga Horária"

    @property
    def ch_aprovada(self):
        """Retorna horas aprovadas pela DESUP, ou o valor solicitado se não definido."""
        if self.horas_aprovadas is not None:
            return self.horas_aprovadas
        return self.horas_reduzidas

    def save(self, *args, **kwargs):
        if self.horas_aprovadas is None and self.horas_reduzidas:
            self.horas_aprovadas = self.horas_reduzidas
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Redução — {self.pendencia.professor.nome} ({self.horas_reduzidas}h)"
