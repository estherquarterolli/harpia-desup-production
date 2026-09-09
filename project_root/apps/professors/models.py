from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import UnitBoundManager

class ContractType(models.Model):
    """
    Tipo de Contrato do Professor.
    """
    class CategoriaChoices(models.TextChoices):
        TERCEIRIZADO = 'TERCEIRIZADO', 'Terceirizado'
        EFETIVO = 'EFETIVO', 'Efetivo'
        CONCURSADO = 'CONCURSADO', 'Concursado'

    nome = models.CharField(max_length=100, verbose_name="Nome do Contrato", help_text="Ex: Ensino Superior, BTT")
    categoria = models.CharField(
        max_length=20,
        choices=CategoriaChoices.choices,
        default=CategoriaChoices.EFETIVO,
        verbose_name="Categoria do Contrato",
    )
    regime_trabalho = models.CharField(max_length=20, default="", verbose_name="Regime de Trabalho", help_text="Ex: 40h DE, 20h")
    dias_presenca_obrigatorios = models.PositiveSmallIntegerField(
        default=3,
        verbose_name="Dias de presença obrigatórios",
        help_text="Quantidade mínima de dias na unidade (ex.: 40h semanais → 3 dias). Definido pela DESUP.",
    )
    max_class_hours = models.PositiveIntegerField(verbose_name="Limite de horas em sala")
    max_total_hours = models.PositiveIntegerField(verbose_name="Limite total de horas", default=40, help_text="Teto global (ex: 40h)")
    max_classes = models.PositiveIntegerField(verbose_name="Limite de turmas")

    class Meta:
        verbose_name = "Tipo de Contrato"
        verbose_name_plural = "Tipos de Contrato"
        ordering = ['nome']

    def __str__(self):
        return self.nome

class Professor(models.Model):
    """
    Modelo que representa o Professor (Regra #3: Separação RH vs DESUP).
    """
    class StatusChoices(models.TextChoices):
        ATIVO = 'Ativo', 'Ativo'
        AFASTADO = 'Afastado', 'Ausente/Afastado'

    # --- Campos Originais RH (Read-only por Regra de Negócio) ---
    id_funcional = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        db_column="ID_FUNCIONAL",
        verbose_name="ID Funcional",
    )
    rh_matricula = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="Matrícula RH")
    rh_nome = models.CharField(max_length=255, verbose_name="Nome (RH)")
    rh_email = models.EmailField(blank=True, null=True, verbose_name="E-mail (RH)")

    unidade_principal = models.ForeignKey(
        'core.Unidade',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='professores',
        verbose_name="Unidade Principal"
    )

    #  Campos DESUP (Sobrescritas e Ajustes - Regra #3)
    desup_nome = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome (Ajuste DESUP)")
    desup_email = models.EmailField(blank=True, null=True, verbose_name="E-mail (Ajuste DESUP)")

    tipo_contrato = models.ForeignKey(
        ContractType,
        on_delete=models.PROTECT,
        related_name='professores',
        verbose_name="Tipo de Contrato"
    )

    #  Atributos de Domínio 
    is_cedido = models.BooleanField(default=False, verbose_name="Professor Cedido (Regra #4)", help_text="Tratado como carência se True.")
    
    ha = models.PositiveIntegerField(
        default=0,
        verbose_name="HA (Horas-Aula)",
        help_text="Horas-aula semanais do professor"
    )

    cursos = models.ManyToManyField(
        'courses.Course',
        blank=True,
        related_name='professores_cursos',
        verbose_name="Cursos"
    )

    class MateriaChoices(models.TextChoices):
        INFORMATICA = 'INFO', 'Informática (Computação)'
        ELETROTECNICA = 'ELETRO', 'Eletrotécnica (Eletrônica)'
        MECANICA = 'MECANICA', 'Mecânica (Automação)'
        EDIFICACOES = 'EDIFICACOES', 'Edificações (Civil)'
        ADMINISTRACAO = 'ADMIN', 'Administração (Gestão)'
        SAUDE = 'SAUDE', 'Saúde (Enfermagem)'
        DESIGN = 'DESIGN', 'Design (Moda)'
        TELECOMUNICACOES = 'TELECOM', 'Telecomunicações'
        QUIMICA = 'QUIMICA', 'Química (Meio Ambiente)'
        TURISMO = 'TURISMO', 'Turismo (Hospitalidade)'
        FORMACAO = 'FORMACAO', 'Formação Geral'
        OUTROS = 'OUTROS', 'Outros'

    materia = models.CharField(
        max_length=20,
        choices=MateriaChoices.choices,
        blank=True,
        default='',
        verbose_name="Eixo",
        help_text="Área de atuação do professor (ex: Informática, Saúde, etc.)"
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ATIVO,
        verbose_name="Status"
    )

    class Meta:
        verbose_name = "Professor"
        verbose_name_plural = "Professores"
        ordering = ['rh_nome']

    objects = UnitBoundManager()

    def __str__(self):
        return f"{self.nome} ({self.id_funcional} / {self.rh_matricula})"

    def clean(self):
        super().clean()
        if self.id_funcional and self.rh_matricula and self.id_funcional == self.rh_matricula:
            raise ValidationError({
                "rh_matricula": "A matrícula deve ser diferente do ID Funcional.",
            })

    # --- Getters com Lógica de Sobrescrita (Regra #3) ---

    @property
    def nome(self):
        return self.desup_nome if self.desup_nome else self.rh_nome

    @property
    def email(self):
        return self.desup_email if self.desup_email else self.rh_email

    # --- Propriedades para Dashboard (UC08) e Limites (UC05) ---

    @property
    def ch_total(self) -> int:
        """Retorna o limite de horas total do contrato vinculado."""
        return self.tipo_contrato.max_total_hours if self.tipo_contrato else 0

    @property
    def ch_justificada(self) -> float:
        """
        Soma de horas justificadas/extracurriculares aprovadas pela DESUP
        **no semestre atual**.

        Usa as horas efetivamente APROVADAS pela DESUP (``ch_aprovada`` de cada
        item), não as solicitadas — reaproveitando
        ``PendenciaExtra.ch_total_justificada``, que já retorna 0 quando a
        pendência não está APROVADA e já soma o ``ch_aprovada`` de TCC +
        extensão + redução. Antes esta property somava ``carga_horaria`` /
        ``horas_reduzidas`` (valores solicitados), o que superestimava o total
        quando a DESUP aprovava menos horas do que o pedido.

        As justificativas são escopadas por semestre (uma PendenciaExtra por
        professor + semestre) e não ficam acumuladas no professor: ao virar o
        semestre, as justificativas de semestres anteriores deixam de contar.
        """
        try:
            from apps.extra_curricular.utils import semestre_atual
            pendencias = self.pendencias_extra.filter(semestre=semestre_atual())
            return sum(float(p.ch_total_justificada) for p in pendencias)
        except Exception:
            return 0.0

    @property
    def ch_alocada(self) -> int:
        """Soma CH alocada; componentes compartilhados contam uma única vez."""
        try:
            vistos = set()
            total = 0
            for comp in self.componentes_matriz.filter(matriz__is_vigente=True).select_related('componente_curricular'):
                chave = (
                    comp.componente_curricular_id
                    if comp.compartilhado
                    else comp.pk
                )
                if chave in vistos:
                    continue
                vistos.add(chave)
                total += comp.ha_semanal
            return total
        except Exception:
            return 0

    @property
    def limite_horas_extra_efetivo(self) -> float:
        """
        Limite de horas extracurriculares aprováveis pela DESUP.
        Usa o total já calculado pelo sistema (horas de sala ainda não preenchidas).
        """
        meta = self.tipo_contrato.max_class_hours if self.tipo_contrato else 0
        return max(meta - self.ch_alocada, 0)

    @property
    def ch_nao_alocada(self) -> int:
        """Retorna as horas restantes do professor."""
        try:
            saldo = self.ch_total - (self.ch_alocada + self.ch_justificada)
            return max(saldo, 0)
        except Exception:
            return 0

    @property
    def percentual_alocado(self) -> float:
        """Retorna a porcentagem alocada (incluindo horas justificadas), limitada a 100%."""
        try:
            if self.ch_total == 0:
                return 0.0
            total_alocado = self.ch_alocada + self.ch_justificada
            percentual = min((total_alocado / self.ch_total) * 100, 100.0)
            return round(percentual, 2)
        except Exception:
            return 0.0

    @property
    def categoria_contrato(self) -> str:
        if self.tipo_contrato:
            return self.tipo_contrato.get_categoria_display()
        return "—"

    @property
    def dias_presenca_obrigatorios(self) -> int:
        if self.tipo_contrato:
            return self.tipo_contrato.dias_presenca_obrigatorios
        return 0

    def get_disciplinas_alocadas(self):
        """Disciplinas distintas em que o professor está alocado na matriz vigente."""
        from apps.courses.models import MatrixComponent
        nomes = (
            MatrixComponent.objects.filter(
                docente=self,
                matriz__is_vigente=True,
            )
            .select_related('componente_curricular')
            .values_list('componente_curricular__nome', flat=True)
            .distinct()
        )
        return [n for n in nomes if n]

class Availability(models.Model):
    """
    Disponibilidade de horário do professor.
    """
    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 2, 'Segunda-feira'
        TERCA = 3, 'Terça-feira'
        QUARTA = 4, 'Quarta-feira'
        QUINTA = 5, 'Quinta-feira'
        SEXTA = 6, 'Sexta-feira'
        SABADO = 7, 'Sábado'
        DOMINGO = 1, 'Domingo'

    class Turno(models.TextChoices):
        MANHA = 'M', 'Manhã'
        TARDE = 'T', 'Tarde'
        NOITE = 'N', 'Noite'

    professor = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name='disponibilidades',
        verbose_name="Professor"
    )
    dia_semana = models.IntegerField(
        choices=DiaSemana.choices,
        verbose_name="Dia da Semana"
    )
    turno = models.CharField(
        max_length=1,
        choices=Turno.choices,
        verbose_name="Turno"
    )

    class Meta:
        verbose_name = "Disponibilidade"
        verbose_name_plural = "Disponibilidades"
        unique_together = ('professor', 'dia_semana', 'turno')
        ordering = ['professor', 'dia_semana', 'turno']

    def __str__(self):
        return f"{self.professor.nome} - {self.get_dia_semana_display()} ({self.get_turno_display()})"

class AbsenceRecord(models.Model):
    """
    Registro de Ausência do professor (Ref. UC07).
    """
    professor = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name='ausencias',
        verbose_name="Professor"
    )
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Fim")
    motivo = models.TextField(verbose_name="Motivo")
    comprovante = models.FileField(
        upload_to='ausencias/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Atestado/Comprovante"
    )

    class Meta:
        verbose_name = "Registro de Ausência"
        verbose_name_plural = "Registros de Ausência"
        ordering = ['-data_inicio']

    def __str__(self):
        return f"Ausência: {self.professor.nome} ({self.data_inicio} a {self.data_fim})"
