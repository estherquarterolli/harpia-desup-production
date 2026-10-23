from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

class Unidade(models.Model):
    """
    Modelo que representa uma Unidade no sistema.
    """
    nome = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='Nome'
    )
    sigla = models.CharField(
        max_length=20,
        verbose_name='Sigla'
    )
    status = models.BooleanField(
        default=True,
        verbose_name='Ativo',
        help_text='Define se a unidade está ativa ou inativa.'
    )

    class Meta:
        db_table = 'harpiadb_nucleo_unidade'
        verbose_name = 'Unidade'
        verbose_name_plural = 'Unidades'
        ordering = ['nome']

    def __str__(self):
        return f"{self.sigla} - {self.nome}"


class UnitBoundQuerySet(models.QuerySet):
    def for_user(self, user):
        if user.is_superuser or user.perfil == 'DESUP':
            return self.all()

        # Professores são uma base institucional compartilhada: todas as
        # unidades podem consultá-los e utilizá-los na alocação.
        if (
            self.model._meta.label_lower == 'professors.professor'
            and user.perfil == 'COORDENADOR_UNIDADE'
        ):
            return self.all()

        if user.perfil == 'COORDENADOR_UNIDADE':
            if not user.unidade:
                return self.none()

            # Verifica qual campo de unidade o model possui
            field_names = [f.name for f in self.model._meta.get_fields()]
            if 'unidade_principal' in field_names:
                return self.filter(unidade_principal=user.unidade)
            elif 'unidade' in field_names:
                return self.filter(unidade=user.unidade)

        return self.none()


class UnitBoundManager(models.Manager):
    def get_queryset(self):
        return UnitBoundQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)


class TipoCargoDiretivo(models.Model):
    """Cargo configurável que pode compor a equipe diretiva de uma unidade."""

    nome = models.CharField(max_length=120, unique=True, verbose_name="Nome do cargo")
    codigo = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name="Código interno",
    )
    exige_curso = models.BooleanField(
        default=False,
        verbose_name="Cargo por curso",
        help_text="Ao preencher o cargo, será necessário escolher um curso da unidade.",
    )
    permite_multiplos = models.BooleanField(
        default=False,
        verbose_name="Permite mais de um ocupante",
        help_text="Marque para permitir mais de um ocupante vigente ao mesmo tempo.",
    )
    ativo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Ativo",
        help_text="Cargos inativos permanecem no histórico, mas não recebem novos ocupantes.",
    )
    carga_reducao_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("168.00"))],
        verbose_name="Carga horária de redução semanal",
        help_text="Horas semanais de redução de carga que o cargo garante a quem o ocupa. Definida pela DESUP.",
    )
    ordem = models.PositiveSmallIntegerField(default=100, verbose_name="Ordem de exibição")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = "harpiadb_nucleo_tipo_cargo_diretivo"
        verbose_name = "Tipo de cargo diretivo"
        verbose_name_plural = "Tipos de cargo diretivo"
        ordering = ["ordem", "nome"]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("nome"),
                name="harpia_cargo_nome_ci_uniq",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo:
            base = slugify(self.nome).replace("-", "_").upper() or "CARGO"
            base = base[:50]
            codigo = base
            contador = 2
            while type(self).objects.exclude(pk=self.pk).filter(codigo=codigo).exists():
                sufixo = f"_{contador}"
                codigo = f"{base[:50 - len(sufixo)]}{sufixo}"
                contador += 1
            self.codigo = codigo
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class OcupacaoEquipeDiretiva(models.Model):
    """Ocupação histórica de um cargo diretivo por um professor/servidor."""

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="ocupacoes_equipe_diretiva",
        verbose_name="Unidade",
    )
    cargo = models.ForeignKey(
        TipoCargoDiretivo,
        on_delete=models.PROTECT,
        related_name="ocupacoes",
        verbose_name="Cargo",
    )
    professor = models.ForeignKey(
        "professors.Professor",
        on_delete=models.PROTECT,
        related_name="ocupacoes_diretivas",
        verbose_name="Servidor",
        help_text="Selecione o servidor no cadastro institucional de professores.",
    )
    curso = models.ForeignKey(
        "courses.CourseUnit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ocupacoes_diretivas",
        verbose_name="Curso",
    )
    data_inicio = models.DateField(verbose_name="Início da vigência")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Fim da vigência")
    carga_reducao_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("168.00"))],
        verbose_name="Carga horária de redução semanal",
        help_text="Informe o total de horas semanais de redução associado à ocupação.",
    )
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    criado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocupacoes_diretivas_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    objects = UnitBoundManager()

    class Meta:
        db_table = "harpiadb_nucleo_ocupacao_diretiva"
        verbose_name = "Ocupação da equipe diretiva"
        verbose_name_plural = "Ocupações da equipe diretiva"
        ordering = ["unidade__nome", "cargo__ordem", "cargo__nome", "-data_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
                name="harpia_ocup_data_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(carga_reducao_horas__gte=0),
                name="harpia_ocup_carga_nao_neg",
            ),
        ]
        indexes = [
            models.Index(fields=["unidade", "data_inicio", "data_fim"], name="harpia_ocup_unid_vig_idx"),
            models.Index(fields=["cargo", "data_inicio", "data_fim"], name="harpia_ocup_cargo_vig_idx"),
        ]

    @property
    def vigente(self):
        hoje = timezone.localdate()
        return self.data_inicio <= hoje and (self.data_fim is None or self.data_fim > hoje)

    @staticmethod
    def filtro_vigente(data=None):
        """Periodo [inicio, fim): o dia do encerramento libera o cargo."""
        data = data or timezone.localdate()
        return models.Q(data_inicio__lte=data) & (
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gt=data)
        )

    def conflitos_de_vigencia(self):
        if not self.unidade_id or not self.cargo_id or not self.data_inicio:
            return type(self).objects.none()

        # Um encerramento no dia do inicio tem duracao zero.
        if self.data_fim == self.data_inicio:
            return type(self).objects.none()

        conflitos = type(self).objects.filter(
            unidade_id=self.unidade_id,
            cargo_id=self.cargo_id,
        ).exclude(pk=self.pk).exclude(data_fim=models.F("data_inicio"))

        if self.cargo.permite_multiplos:
            if self.cargo.exige_curso:
                conflitos = conflitos.filter(curso_id=self.curso_id)
            else:
                conflitos = conflitos.filter(curso__isnull=True)
            conflitos = conflitos.filter(professor_id=self.professor_id)

        if self.data_fim:
            conflitos = conflitos.filter(data_inicio__lt=self.data_fim)
        return conflitos.filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gt=self.data_inicio)
        )

    def clean(self):
        super().clean()
        erros = {}

        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O fim da vigência não pode ser anterior ao início."

        if self.cargo_id:
            if self.cargo.exige_curso and not self.curso_id:
                erros["curso"] = "Este cargo exige a seleção de um curso da unidade."
            if not self.cargo.exige_curso and self.curso_id:
                erros["curso"] = "Este cargo não deve ser vinculado a um curso."

        if self.curso_id and self.unidade_id and self.curso.unidade_id != self.unidade_id:
            erros["curso"] = "O curso selecionado não pertence à unidade informada."

        if self.professor_id and self.unidade_id:
            vinculado = (
                self.professor.unidade_principal_id == self.unidade_id
                or self.professor.unidades.filter(pk=self.unidade_id).exists()
            )
            if not vinculado:
                erros["professor"] = "O servidor não está vinculado à unidade informada."

        if not erros and self.conflitos_de_vigencia().exists():
            erros["data_inicio"] = (
                "Já existe uma ocupação conflitante para este cargo, unidade e período."
            )

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        complemento = f" - {self.curso.sigla}" if self.curso_id else ""
        return f"{self.unidade.sigla} - {self.cargo.nome}{complemento}: {self.professor.nome}"


class AtividadeEstagioSupervisao(models.Model):
    """Registro de atividades de estágio e supervisão de uma unidade."""

    class TipoChoices(models.TextChoices):
        COORDENACAO_ESTAGIO = "COORDENACAO_ESTAGIO", "Coordenação de Estágio"
        SUPERVISAO_ESTAGIO = "SUPERVISAO_ESTAGIO", "Supervisão de Estágio"
        ORIENTACAO_ESTAGIO = "ORIENTACAO_ESTAGIO", "Orientação de Estágio"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="atividades_estagio_supervisao",
        verbose_name="Unidade",
    )
    professor = models.ForeignKey(
        "professors.Professor",
        on_delete=models.PROTECT,
        related_name="atividades_estagio_supervisao",
        verbose_name="Servidor",
        help_text="Selecione o servidor vinculado à unidade.",
    )
    curso = models.ForeignKey(
        "courses.CourseUnit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="atividades_estagio_supervisao",
        verbose_name="Curso",
    )
    tipo = models.CharField(
        max_length=30,
        choices=TipoChoices.choices,
        default=TipoChoices.SUPERVISAO_ESTAGIO,
        db_index=True,
        verbose_name="Tipo de atividade",
    )
    semestre = models.CharField(
        max_length=10,
        verbose_name="Semestre letivo",
        validators=[
            RegexValidator(
                regex=r"^\d{4}\.[12]$",
                message="Informe o semestre no formato AAAA.1 ou AAAA.2.",
            )
        ],
    )
    num_estudantes = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(200)],
        verbose_name="Nº de estagiários/supervisionados",
    )
    carga_horaria_semanal = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("40.00"))],
        verbose_name="Carga horária semanal dedicada (h)",
        help_text="Horas semanais dedicadas à atividade de estágio/supervisão.",
    )
    carga_reducao_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("40.00"))],
        verbose_name="Carga horária de redução semanal (DESUP)",
        help_text="Definida exclusivamente pela DESUP.",
    )
    data_inicio = models.DateField(verbose_name="Início da vigência")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Fim da vigência")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    criado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atividades_estagio_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    objects = UnitBoundManager()

    class Meta:
        db_table = "harpiadb_nucleo_atividade_estagio_supervisao"
        verbose_name = "Atividade de estágio e supervisão"
        verbose_name_plural = "Atividades de estágio e supervisão"
        ordering = ["-semestre", "-data_inicio", "professor__rh_nome"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
                name="harpia_estagio_data_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(carga_horaria_semanal__gte=0),
                name="harpia_estagio_ch_nao_neg",
            ),
            models.CheckConstraint(
                condition=models.Q(carga_reducao_horas__gte=0),
                name="harpia_estagio_red_nao_neg",
            ),
        ]
        indexes = [
            models.Index(fields=["unidade", "semestre"], name="harpia_estagio_unid_sem_idx"),
        ]

    @property
    def vigente(self):
        hoje = timezone.localdate()
        return self.data_inicio <= hoje and (self.data_fim is None or self.data_fim >= hoje)

    def clean(self):
        super().clean()
        erros = {}

        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O fim da vigência não pode ser anterior ao início."

        if self.curso_id and self.unidade_id and self.curso.unidade_id != self.unidade_id:
            erros["curso"] = "O curso selecionado não pertence à unidade informada."

        if self.professor_id and self.unidade_id:
            vinculado = (
                self.professor.unidade_principal_id == self.unidade_id
                or self.professor.unidades.filter(pk=self.unidade_id).exists()
            )
            if not vinculado:
                erros["professor"] = "O servidor não está vinculado à unidade informada."

        if erros:
            raise ValidationError(erros)

    def __str__(self):
        complemento = f" ({self.curso.sigla})" if self.curso_id else ""
        return f"{self.unidade.sigla} - {self.get_tipo_display()}{complemento}: {self.professor.nome} [{self.semestre}]"


class SolicitacaoProfessorExterno(models.Model):
    """Solicitação à DESUP: cessão de professor de outra unidade ou cadastro de professor novo."""

    class StatusChoices(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        RECUSADA = "RECUSADA", "Recusada"
        CANCELADA = "CANCELADA", "Cancelada"

    class TipoChoices(models.TextChoices):
        CESSAO = "CESSAO", "Cessão de professor"
        CADASTRO = "CADASTRO", "Cadastro de professor"

    tipo = models.CharField(
        max_length=10,
        choices=TipoChoices.choices,
        default=TipoChoices.CESSAO,
        db_index=True,
        verbose_name="Tipo",
    )
    unidade_solicitante = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="solicitacoes_professor_enviadas",
        verbose_name="Unidade solicitante",
    )
    # Nulos nas solicitações de cadastro: o professor ainda não existe no sistema.
    unidade_origem = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_professor_recebidas",
        verbose_name="Unidade de origem",
    )
    professor = models.ForeignKey(
        "professors.Professor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_externas",
        verbose_name="Professor",
    )
    professor_nome = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nome do professor informado",
        help_text="Usado nas solicitações de cadastro.",
    )
    professor_id_funcional = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="ID funcional informado",
        help_text="Usado nas solicitações de cadastro.",
    )
    professor_rh_matricula = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Matrícula RH informada",
        help_text="Usado nas solicitações de cadastro.",
    )
    tipo_contrato_solicitado = models.ForeignKey(
        "professors.ContractType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Tipo de contrato informado",
    )
    observacao_cadastro = models.TextField(
        blank=True,
        verbose_name="Observações do cadastro",
    )
    semestre = models.CharField(
        max_length=6,
        validators=[
            RegexValidator(
                regex=r"^\d{4}\.[12]$",
                message="Informe o semestre no formato AAAA.1 ou AAAA.2.",
            )
        ],
        verbose_name="Semestre",
    )
    justificativa = models.TextField(verbose_name="Justificativa")
    status = models.CharField(
        max_length=12,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDENTE,
        db_index=True,
        verbose_name="Situação",
    )
    solicitado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="solicitacoes_professor_criadas",
        verbose_name="Solicitado por",
    )
    decidido_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_professor_decididas",
        verbose_name="Decidido por",
    )
    motivo_decisao = models.TextField(blank=True, verbose_name="Motivo da decisão")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    decidido_em = models.DateTimeField(null=True, blank=True, verbose_name="Decidido em")

    class Meta:
        db_table = "harpiadb_nucleo_solicitacao_professor_externo"
        verbose_name = "Solicitação"
        verbose_name_plural = "Solicitações"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(unidade_solicitante=models.F("unidade_origem")),
                name="harpia_sol_prof_unidades_distintas",
            ),
            models.UniqueConstraint(
                fields=["unidade_solicitante", "professor", "semestre"],
                condition=models.Q(status="PENDENTE"),
                name="harpia_sol_prof_pendente_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "semestre"], name="harpia_sol_prof_status_idx"),
            models.Index(fields=["unidade_solicitante", "status"], name="harpia_sol_prof_unid_idx"),
        ]

    def clean(self):
        super().clean()
        erros = {}
        if (
            self.unidade_solicitante_id
            and self.unidade_origem_id
            and self.unidade_solicitante_id == self.unidade_origem_id
        ):
            erros["unidade_solicitante"] = "A unidade solicitante deve ser diferente da unidade de origem."

        if self.tipo == self.TipoChoices.CESSAO and not (self.professor_id and self.unidade_origem_id):
            erros["professor"] = "Informe o professor e a unidade de origem da cessão."
        if self.tipo == self.TipoChoices.CADASTRO and not self.professor_nome.strip():
            erros["professor_nome"] = "Informe o nome do professor a cadastrar."

        if self.professor_id and self.unidade_origem_id:
            vinculado = (
                self.professor.unidade_principal_id == self.unidade_origem_id
                or self.professor.unidades.filter(pk=self.unidade_origem_id).exists()
            )
            if not vinculado:
                erros["unidade_origem"] = "O professor não está vinculado à unidade de origem informada."

        if erros:
            raise ValidationError(erros)

    @property
    def nome_professor(self):
        return self.professor.nome if self.professor_id else " ".join((self.professor_nome or "").split()).title()

    def __str__(self):
        if self.unidade_origem_id:
            return f"{self.nome_professor}: {self.unidade_origem.sigla} -> {self.unidade_solicitante.sigla}"
        return f"{self.nome_professor}: cadastro para {self.unidade_solicitante.sigla}"


class LimiteCargaUnidade(models.Model):
    """Limite agregado de carga semanal definido pela DESUP para uma unidade."""

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="limites_carga",
        verbose_name="Unidade",
    )
    limite_horas_semanais = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Limite semanal da unidade",
    )
    data_inicio = models.DateField(verbose_name="Início da vigência")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Fim da vigência")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    criado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="limites_carga_criados",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = "harpiadb_nucleo_limite_carga_unidade"
        verbose_name = "Limite de carga da unidade"
        verbose_name_plural = "Limites de carga das unidades"
        ordering = ["unidade__nome", "-data_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
                name="harpia_limite_data_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(limite_horas_semanais__gt=0),
                name="harpia_limite_carga_positiva",
            ),
        ]
        indexes = [
            models.Index(fields=["unidade", "data_inicio", "data_fim"], name="harpia_limite_vig_idx"),
        ]

    @property
    def vigente(self):
        hoje = timezone.localdate()
        return self.data_inicio <= hoje and (self.data_fim is None or self.data_fim >= hoje)

    def conflitos_de_vigencia(self):
        if not self.unidade_id or not self.data_inicio:
            return type(self).objects.none()
        conflitos = type(self).objects.filter(unidade_id=self.unidade_id).exclude(pk=self.pk)
        if self.data_fim:
            conflitos = conflitos.filter(data_inicio__lte=self.data_fim)
        return conflitos.filter(
            models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=self.data_inicio)
        )

    def clean(self):
        super().clean()
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O fim da vigência não pode ser anterior ao início."
        if not erros and self.conflitos_de_vigencia().exists():
            erros["data_inicio"] = "Já existe um limite para esta unidade no período informado."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"{self.unidade.sigla}: {self.limite_horas_semanais} h semanais"


class ExcecaoCargaUnidade(models.Model):
    """Exceção temporária de carga submetida à decisão da DESUP."""

    class StatusChoices(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        RECUSADA = "RECUSADA", "Recusada"
        CANCELADA = "CANCELADA", "Cancelada"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="excecoes_carga",
        verbose_name="Unidade",
    )
    professor = models.ForeignKey(
        "professors.Professor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="excecoes_carga",
        verbose_name="Professor",
        help_text="Deixe vazio quando a exceção se aplicar somente ao limite agregado da unidade.",
    )
    horas_adicionais = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Horas adicionais autorizadas",
    )
    data_inicio = models.DateField(verbose_name="Início da vigência")
    data_fim = models.DateField(verbose_name="Fim da vigência")
    justificativa = models.TextField(verbose_name="Justificativa")
    status = models.CharField(
        max_length=12,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDENTE,
        db_index=True,
        verbose_name="Situação",
    )
    solicitado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="excecoes_carga_solicitadas",
        verbose_name="Solicitado por",
    )
    decidido_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="excecoes_carga_decididas",
        verbose_name="Decidido por",
    )
    motivo_decisao = models.TextField(blank=True, verbose_name="Motivo da decisão")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    decidido_em = models.DateTimeField(null=True, blank=True, verbose_name="Decidido em")

    class Meta:
        db_table = "harpiadb_nucleo_excecao_carga_unidade"
        verbose_name = "Exceção de carga"
        verbose_name_plural = "Exceções de carga"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_fim__gte=models.F("data_inicio")),
                name="harpia_excecao_data_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(horas_adicionais__gt=0),
                name="harpia_excecao_horas_positivas",
            ),
        ]

    def clean(self):
        super().clean()
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O fim da vigência não pode ser anterior ao início."
        if self.professor_id and self.unidade_id:
            vinculado = (
                self.professor.unidade_principal_id == self.unidade_id
                or self.professor.unidades.filter(pk=self.unidade_id).exists()
            )
            if not vinculado:
                erros["professor"] = "O professor não está vinculado à unidade informada."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        alvo = self.professor.nome if self.professor_id else self.unidade.sigla
        return f"{alvo}: +{self.horas_adicionais} h ({self.get_status_display()})"


class ReadaptacaoProfessor(models.Model):
    """Período formal de readaptação administrado pela DESUP."""

    professor = models.ForeignKey(
        "professors.Professor",
        on_delete=models.PROTECT,
        related_name="readaptacoes",
        verbose_name="Professor",
    )
    data_inicio = models.DateField(verbose_name="Início da vigência")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Fim da vigência")
    pausado_em = models.DateTimeField(null=True, blank=True, verbose_name="Pausada em")
    justificativa_administrativa = models.TextField(
        verbose_name="Justificativa administrativa",
        help_text="Não informe diagnóstico ou dados médicos desnecessários.",
    )
    criado_por = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="readaptacoes_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        db_table = "harpiadb_nucleo_readaptacao_professor"
        verbose_name = "Readaptação de professor"
        verbose_name_plural = "Readaptações de professores"
        ordering = ["-data_inicio", "professor__rh_nome"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
                name="harpia_readapt_data_valida",
            ),
        ]
        indexes = [
            models.Index(fields=["professor", "data_inicio", "data_fim"], name="harpia_readapt_vig_idx"),
        ]

    @property
    def vigente(self):
        hoje = timezone.localdate()
        return self.pausado_em is None and self.data_inicio <= hoje and (self.data_fim is None or self.data_fim >= hoje)

    def conflitos_de_vigencia(self):
        if not self.professor_id or not self.data_inicio:
            return type(self).objects.none()
        conflitos = type(self).objects.filter(professor_id=self.professor_id).exclude(pk=self.pk)
        from datetime import timedelta

        fim_novo = self.data_fim
        if self.pausado_em:
            ultimo_dia = timezone.localtime(self.pausado_em).date() - timedelta(days=1)
            fim_novo = min(fim_novo, ultimo_dia) if fim_novo else ultimo_dia
        for outro in conflitos:
            fim_outro = outro.data_fim
            if outro.pausado_em:
                ultimo_dia = timezone.localtime(outro.pausado_em).date() - timedelta(days=1)
                fim_outro = min(fim_outro, ultimo_dia) if fim_outro else ultimo_dia
            if (fim_outro is None or fim_outro >= self.data_inicio) and (fim_novo is None or outro.data_inicio <= fim_novo):
                return conflitos.filter(pk=outro.pk)
        return conflitos.none()

    def clean(self):
        super().clean()
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros["data_fim"] = "O fim da vigência não pode ser anterior ao início."
        if not (self.justificativa_administrativa or "").strip():
            erros["justificativa_administrativa"] = "Informe uma justificativa administrativa."
        if not erros and self.conflitos_de_vigencia().exists():
            erros["data_inicio"] = "Já existe uma readaptação para este professor no período informado."
        if erros:
            raise ValidationError(erros)

    def __str__(self):
        return f"Readaptação de {self.professor.nome} desde {self.data_inicio:%d/%m/%Y}"

class JanelaEntrega(models.Model):
    """
    Representa o período permitido para envio da matriz curricular (Regra #2).
    """
    class StatusChoices(models.TextChoices):
        ABERTO = 'Aberto', 'Aberto'
        FECHADO = 'Fechado', 'Fechado'
        REABERTO = 'Reaberto', 'Reaberto'

    semestre = models.CharField(max_length=10, verbose_name="Semestre (Ex: 2026.1)")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Fim")
    status = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.FECHADO
    )
    unidade = models.ForeignKey(
        Unidade, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Se vazio, aplica-se a todas as unidades."
    )

    class Meta:
        db_table = "harpiadb_nucleo_janela_entrega"
        verbose_name = "Janela de Entrega"
        verbose_name_plural = "Janelas de Entrega"
        ordering = ['-semestre', '-data_fim']

    def __str__(self):
        scope = self.unidade.sigla if self.unidade else "Global"
        return f"[{scope}] {self.semestre} - {self.status}"

    @property
    def is_ativa(self):
        from django.utils import timezone
        # localdate() e não now().date(): com USE_TZ=True o now() é UTC, e em
        # America/Sao_Paulo (UTC-3) o dia virava às 21h — a janela "fechava" três
        # horas antes da meia-noite do último dia do prazo.
        hoje = timezone.localdate()
        return self.status != self.StatusChoices.FECHADO and self.data_inicio <= hoje <= self.data_fim


class Notificacao(models.Model):
    """
    Representa uma notificação/aviso no sistema.
    Pode ser destinada a um usuário específico ou a uma unidade.
    """
    destinatario = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notificacoes',
        null=True,
        blank=True,
        verbose_name='Usuário Destinatário'
    )
    unidade_destino = models.ForeignKey(
        Unidade,
        on_delete=models.CASCADE,
        related_name='notificacoes_unidade',
        null=True,
        blank=True,
        verbose_name='Unidade Destino'
    )
    titulo = models.CharField(max_length=255, verbose_name="Título", default="Nova Notificação")
    mensagem = models.TextField(verbose_name="Mensagem")
    lida = models.BooleanField(default=False, verbose_name="Lida")
    url_acao = models.CharField(max_length=255, null=True, blank=True, verbose_name="URL de Ação")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    class Meta:
        db_table = "harpiadb_nucleo_notificacao"
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"[{'LIDA' if self.lida else 'NOVA'}] {self.titulo}"


class AuditoriaGlobal(models.Model):
    """
    Registro central de eventos sensiveis do sistema.
    """

    usuario = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_auditoria',
        verbose_name='Usuario',
    )
    email = models.EmailField(blank=True, verbose_name='E-mail')
    acao = models.CharField(max_length=120, db_index=True, verbose_name='Acao')
    detalhes = models.TextField(blank=True, verbose_name='Detalhes')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.TextField(blank=True, verbose_name='User-Agent')
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Data de Criacao')

    class Meta:
        db_table = 'harpiadb_nucleo_auditoria'
        verbose_name = 'Auditoria Global'
        verbose_name_plural = 'Auditoria Global'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.criado_em:%Y-%m-%d %H:%M:%S} - {self.acao} - {self.email}"


class ErroSistema(models.Model):
    """Ocorrência técnica capturada para diagnóstico exclusivo do superadmin."""

    usuario = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='erros_sistema',
        verbose_name='Usuário',
    )
    email_usuario = models.EmailField(blank=True, verbose_name='E-mail do usuário')
    perfil_usuario = models.CharField(max_length=30, blank=True, verbose_name='Perfil')
    unidade_usuario = models.CharField(max_length=255, blank=True, verbose_name='Unidade')
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Data')
    metodo = models.CharField(max_length=10, verbose_name='Método HTTP')
    caminho = models.CharField(max_length=500, db_index=True, verbose_name='Caminho')
    status_http = models.PositiveSmallIntegerField(db_index=True, verbose_name='Status HTTP')
    tipo_erro = models.CharField(max_length=255, db_index=True, verbose_name='Tipo do erro')
    mensagem = models.TextField(blank=True, verbose_name='Mensagem')
    traceback = models.TextField(blank=True, verbose_name='Traceback')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.TextField(blank=True, verbose_name='Navegador/User-Agent')
    request_id = models.CharField(max_length=32, db_index=True, verbose_name='ID da requisição')
    fingerprint = models.CharField(max_length=64, db_index=True, verbose_name='Fingerprint')

    class Meta:
        db_table = 'harpiadb_nucleo_erro_sistema'
        verbose_name = 'Erro do Sistema'
        verbose_name_plural = 'Erros do Sistema'
        ordering = ['-criado_em']
        indexes = [
            models.Index(
                fields=['status_http', 'criado_em'],
                name='harpia_erro_status_data_idx',
            ),
        ]

    def __str__(self):
        return f"{self.status_http} {self.tipo_erro} em {self.caminho}"


class AtalhoDashboard(models.Model):
    """Atalho configurável do dashboard (por usuário). Guarda a *chave* do
    catálogo (apps/core/atalhos.py) — whitelist, não URL crua."""

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='atalhos',
        verbose_name='Usuário',
    )
    chave = models.CharField(max_length=80, verbose_name='Chave do atalho')
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        db_table = 'harpiadb_nucleo_atalho_dashboard'
        verbose_name = 'Atalho do Dashboard'
        verbose_name_plural = 'Atalhos do Dashboard'
        ordering = ['ordem', 'id']
        unique_together = ('user', 'chave')

    def __str__(self):
        return f"{self.user_id}:{self.chave}"
