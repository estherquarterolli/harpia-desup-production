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
    PENDENTE   = "PENDENTE",   "Pendente"
    APROVADO   = "APROVADO",   "Aprovado"
    INDEFERIDO = "INDEFERIDO", "Indeferido"


# ────────────────────────────────────────────────────────────────────────────────
# PendenciaExtra — cabeçalho / agrupador por professor + semestre
# ────────────────────────────────────────────────────────────────────────────────
class PendenciaExtra(models.Model):
    """
    Agrupa as justificativas extracurriculares de um professor num semestre.
    Criada pelo Coordenador de Unidade; avaliada pela DESUP.
    """

    class StatusChoices(models.TextChoices):
        RASCUNHO   = "RASCUNHO",   "Rascunho"
        ENVIADO    = "ENVIADO",    "Enviado para DESUP"
        APROVADO   = "APROVADO",   "Finalizado"
        # CORR-023: análise concluída com resultado misto — ao menos um item
        # aprovado e ao menos um indeferido. Antes o agregado era binário e
        # `any(INDEFERIDO)` derrubava a pendência inteira para INDEFERIDO, o que
        # zerava a CH dos itens que a DESUP tinha aprovado.
        PARCIAL    = "PARCIAL",    "Finalizado parcialmente"
        INDEFERIDO = "INDEFERIDO", "Indeferido"

    #: Estados em que a análise da DESUP terminou e a CH aprovada vale.
    STATUS_FINALIZADOS = ("APROVADO", "PARCIAL")

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
        """Soma de toda CH justificada nesta pendência (usa horas aprovadas pela DESUP).

        `ch_aprovada` é sempre `float` (CORR-004), então a soma nunca mistura
        Decimal/float. O `float(...)` no acumulador é defensivo.

        Só entram na conta os itens com parecer APROVADO. O gate pelo status do
        cabeçalho não basta: `ch_aprovada` cai no valor SOLICITADO enquanto a
        DESUP não opina (o `save()` dos três models já copia o solicitado para
        `horas_aprovadas`), e a unidade pode incluir justificativas depois da
        aprovação — sem o filtro por item, uma redução recém-criada (PENDENTE,
        sem nenhum parecer) passava a contar como CH aprovada no mesmo instante.
        Itens INDEFERIDOS, que também mantêm `horas_aprovadas` preenchido, ficam
        de fora pelo mesmo motivo.

        CORR-023: `PARCIAL` conta igual a `APROVADO` — o que foi deferido vale, o
        indeferido só não entra na soma. O gate pelo status do cabeçalho continua
        existindo porque é ele que faz a CH parar de contar depois de uma
        REABERTURA (o status volta a ENVIADO enquanto os itens seguem marcados
        como aprovados).
        """
        if self.status not in self.STATUS_FINALIZADOS:
            return 0.0

        def _aprovados(queryset):
            return sum(
                float(item.ch_aprovada)
                for item in queryset
                if item.parecer_desup == ParecerChoices.APROVADO
            )

        tcc = _aprovados(self.orientacoes_tcc.all())
        ext = _aprovados(self.atividades_extensao.all())
        red = _aprovados(self.reducoes_ch.all())
        return tcc + ext + red

    @property
    def ch_faltante(self):
        """CH que ainda falta cobrir após as justificativas."""
        limite = self.professor.limite_horas_extra_efetivo
        return max(limite - self.ch_total_justificada, 0)

    def bloquear_itens_enviados(self):
        """
        Marca como bloqueadas todas as justificativas atuais desta pendência.

        Chamado no envio definitivo à DESUP (botão vermelho): a partir daí a
        unidade não pode mais editar ou excluir esses itens. Novas justificativas
        adicionadas depois começam desbloqueadas e só travam num próximo envio.
        """
        self.orientacoes_tcc.update(bloqueado=True)
        self.atividades_extensao.update(bloqueado=True)
        self.reducoes_ch.update(bloqueado=True)


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
    bloqueado = models.BooleanField(
        default=False,
        verbose_name="Bloqueado (enviado à DESUP)",
        help_text="Se True, a unidade não pode mais editar/excluir este item (já enviado em definitivo).",
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Orientação de TCC"
        verbose_name_plural = "Orientações de TCC"

    @property
    def ch_aprovada(self):
        """Retorna horas aprovadas pela DESUP, ou o valor calculado se não definido.

        Sempre `float` (CORR-004): nunca misturar float/Decimal nos consumidores
        (ex.: soma em BasePendenciaFormSet.clean e ch_total_justificada).
        """
        if self.num_orientandos_aprovados is not None:
            return min(round(self.num_orientandos_aprovados * 0.5, 1), 4.0)
        if self.horas_aprovadas is not None:
            return float(self.horas_aprovadas)
        return float(self.carga_horaria or 0)

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
    bloqueado = models.BooleanField(
        default=False,
        verbose_name="Bloqueado (enviado à DESUP)",
        help_text="Se True, a unidade não pode mais editar/excluir este item (já enviado em definitivo).",
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Atividade Extensionista"
        verbose_name_plural = "Atividades Extensionistas"

    @property
    def ch_aprovada(self):
        """Retorna horas aprovadas pela DESUP, ou o valor calculado se não definido.

        Sempre `float` (CORR-004): tipo consistente para as somas de CH.
        """
        if self.num_estudantes_aprovados is not None:
            return round(self.num_estudantes_aprovados * 0.5, 1)
        if self.horas_aprovadas is not None:
            return float(self.horas_aprovadas)
        return float(self.carga_horaria or 0)

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
    bloqueado = models.BooleanField(
        default=False,
        verbose_name="Bloqueado (enviado à DESUP)",
        help_text="Se True, a unidade não pode mais editar/excluir este item (já enviado em definitivo).",
    )
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Redução de Carga Horária"
        verbose_name_plural = "Reduções de Carga Horária"

    @property
    def ch_aprovada(self):
        """Retorna horas aprovadas pela DESUP, ou o valor solicitado se não definido.

        Sempre `float` (CORR-004): tipo consistente para as somas de CH.
        """
        if self.horas_aprovadas is not None:
            return float(self.horas_aprovadas)
        return float(self.horas_reduzidas or 0)

    def save(self, *args, **kwargs):
        if self.horas_aprovadas is None and self.horas_reduzidas:
            self.horas_aprovadas = self.horas_reduzidas
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Redução — {self.pendencia.professor.nome} ({self.horas_reduzidas}h)"
