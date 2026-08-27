from django.db import models

class Course(models.Model):
    """
    Modelo que representa um Curso no sistema.
    """
    nome = models.CharField(max_length=255, unique=True, verbose_name="Nome do Curso")
    sigla = models.CharField(max_length=20, unique=True, verbose_name="Sigla")

    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        ordering = ['nome']

    @property
    def ha_semanal(self):
        return 0

    @property
    def hr_semanal(self):
        return 0

    def __str__(self):
        return f"{self.sigla} - {self.nome}"

class CourseUnit(models.Model):
    """
    Representa um Curso oferecido em uma Unidade específica.
    """
    curso = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_units', verbose_name="Curso")
    unidade = models.ForeignKey('core.Unidade', on_delete=models.CASCADE, related_name='course_units', verbose_name="Unidade")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")

    class Meta:
        verbose_name = "Curso na Unidade"
        verbose_name_plural = "Cursos na Unidade"
        unique_together = ('curso', 'unidade')
        ordering = ['curso__nome', 'unidade__nome']

    @property
    def nome(self):
        return self.curso.nome

    @property
    def sigla(self):
        return self.curso.sigla

    def __str__(self):
        return f"{self.curso.sigla} - {self.curso.nome} ({self.unidade.sigla})"

class CurricularComponent(models.Model):
    """
    Modelo que representa um Componente Curricular base.
    """
    nome = models.CharField(max_length=255, verbose_name="Nome do Componente Curricular")
    sigla = models.CharField(max_length=20, verbose_name="Sigla")
    codigo = models.CharField(max_length=50, blank=True, db_index=True, verbose_name="Codigo")
    carga_horaria_padrao = models.PositiveIntegerField(verbose_name="Carga Horária Padrão")
    creditos = models.PositiveSmallIntegerField(default=0, verbose_name="Creditos")
    obrigatoria = models.BooleanField(default=True, verbose_name="Obrigatória")
    pre_requisitos = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='componentes_dependentes',
        verbose_name="Pre-requisitos padrao"
    )
    ementa = models.TextField(blank=True, verbose_name="Ementa")

    class Meta:
        verbose_name = "Componente Curricular"
        verbose_name_plural = "Componentes Curriculares"
        ordering = ['nome']

    def __str__(self):
        codigo = f"{self.codigo} - " if self.codigo else ""
        return f"{codigo}{self.sigla} - {self.nome} ({self.carga_horaria_padrao}h)"

class CurriculumMatrix(models.Model):
    """
    Matriz Curricular (Ref. UC04).
    Agrupa os componentes curriculares de um Curso, Período Letivo e Turno.
    Referência base para alocações em sala de aula.
    """
    curso = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='matrizes',
        verbose_name="Curso",
        null=True,
        blank=True,
    )
    unidades = models.ManyToManyField(
        'core.Unidade',
        blank=True,
        related_name='curriculum_matrices',
        verbose_name="Unidades",
    )
    nome = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Código da Matriz",
        help_text="Ex: MC-ADS-2026"
    )
    is_vigente = models.BooleanField(
        default=True,
        verbose_name="Vigente",
        help_text="Se True, esta é a matriz atual do curso."
    )
    is_rascunho = models.BooleanField(
        default=False,
        verbose_name="Rascunho",
        help_text="Se True, esta matriz ainda está em rascunho."
    )
    criada_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criada em",
        null=True,
    )
    periodo_letivo = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Período Letivo",
        help_text="Ex: 2026.1"
    )
    turno = models.CharField(
        max_length=1,
        choices=[('M', 'Manhã'), ('T', 'Tarde'), ('N', 'Noite')],
        blank=True,
        null=True,
        verbose_name="Turno"
    )
    componentes = models.ManyToManyField(
        CurricularComponent,
        through='MatrixComponent',
        related_name='matrizes',
        blank=True,
        verbose_name="Componentes Curriculares"
    )
    class Meta:
        verbose_name = "Matriz Curricular"
        verbose_name_plural = "Matrizes Curriculares"
        ordering = ['curso__nome', 'nome']

    def __str__(self):
        label = self.nome if self.nome else f"Matriz - {self.curso.sigla if self.curso_id else '?'}"
        vigente = " (Vigente)" if self.is_vigente else " (Anterior)"
        return f"{label}{vigente}"

    @property
    def total_componentes(self):
        return self.componentes_da_matriz.count()


class MatrixComponent(models.Model):
    """
    Componente vinculado a uma matriz curricular.
    Guarda os atributos que podem variar por matriz/curso/turno.
    """

    class StatusChoices(models.TextChoices):
        COMPLETO = 'COMPLETO', 'Completo'
        INCOMPLETO = 'INCOMPLETO', 'Incompleto'
        SEM_PROFESSOR = 'SEM_PROFESSOR', 'Sem professor'
        NAO_OFERECIDA = 'NAO_OFERECIDA', 'Nao oferecida'

    matriz = models.ForeignKey(
        CurriculumMatrix,
        on_delete=models.CASCADE,
        related_name='componentes_da_matriz',
        verbose_name="Matriz Curricular"
    )
    componente_curricular = models.ForeignKey(
        CurricularComponent,
        on_delete=models.PROTECT,
        related_name='vinculos_matriz',
        verbose_name="Componente Curricular"
    )
    codigo = models.CharField(max_length=50, blank=True, verbose_name="Codigo na matriz")
    periodo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Periodo do componente",
        help_text="Ex: 1o periodo, 2o periodo"
    )
    carga_horaria = models.PositiveIntegerField(verbose_name="Carga Horaria")
    creditos = models.PositiveSmallIntegerField(default=0, verbose_name="Creditos")
    pre_requisitos = models.ManyToManyField(
        CurricularComponent,
        blank=True,
        related_name='requisito_em_matrizes',
        verbose_name="Pre-requisitos"
    )
    docente = models.ForeignKey(
        'professors.Professor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='componentes_matriz',
        verbose_name="Docente"
    )
    compartilhado = models.BooleanField(default=False, verbose_name="Compartilhado com outro curso")
    curso_compartilhado = models.ForeignKey(
        CourseUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='componentes_compartilhados',
        verbose_name="Curso compartilhado"
    )
    carga_horaria_semanal = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Carga horaria por semana"
    )
    distribuicao_semanal = models.TextField(blank=True, verbose_name="Distribuicao semanal")
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.SEM_PROFESSOR,
        verbose_name="Status"
    )
    observacoes = models.TextField(blank=True, verbose_name="Observacoes")

    @property
    def ha_semanal(self):
        """Hora-Aula semanal: carga horária semestral / 20 semanas."""
        return (self.carga_horaria or 0) / 20.0

    @property
    def hr_semanal(self):
        """Hora-Relógio semanal: HA semanal * 50min / 60min."""
        return self.ha_semanal * (50.0 / 60.0)

    class Meta:
        verbose_name = "Componente da Matriz"
        verbose_name_plural = "Componentes da Matriz"
        unique_together = ('matriz', 'componente_curricular')
        ordering = ['matriz', 'periodo', 'componente_curricular__nome']

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.compartilhado and not self.curso_compartilhado:
            raise ValidationError({
                'curso_compartilhado': 'Informe o curso quando o componente for compartilhado.'
            })

        if self.curso_compartilhado_id and self.matriz_id and self.curso_compartilhado.curso_id == self.matriz.curso_id:
            raise ValidationError({
                'curso_compartilhado': 'O curso compartilhado deve ser diferente do curso da matriz.'
            })

    def save(self, *args, **kwargs):
        if not self.codigo:
            cc = self.componente_curricular
            self.codigo = cc.codigo or cc.sigla or ''
        if self.carga_horaria is None:
            self.carga_horaria = self.componente_curricular.carga_horaria_padrao
        
        # Calcular creditos e carga horaria semanal
        if self.carga_horaria is not None:
            self.creditos = self.carga_horaria // 20
            self.carga_horaria_semanal = self.creditos
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.matriz} - {self.componente_curricular.sigla}"

class ClassGroup(models.Model):
    """
    Turma baseada na Matriz Curricular.
    """
    matriz_curricular = models.ForeignKey(
        CurriculumMatrix, 
        on_delete=models.CASCADE, 
        related_name='turmas',
        verbose_name="Matriz Curricular"
    )
    matriz_componente = models.ForeignKey(
        MatrixComponent,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='turmas',
        verbose_name="Componente da Matriz"
    )
    ano_semestre = models.CharField(
        max_length=20, 
        verbose_name="Ano/Semestre",
        help_text="Ex: 2024.1, 2024.2"
    )
    identificador = models.CharField(
        max_length=50, 
        verbose_name="Identificador da Turma",
        help_text="Ex: T01, A"
    )

    class Meta:
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        unique_together = ('matriz_curricular', 'ano_semestre', 'identificador')

    def __str__(self):
        componente = self.matriz_componente.componente_curricular.sigla if self.matriz_componente_id else self.matriz_curricular.curso.sigla
        return f"{componente} - Turma {self.identificador} ({self.ano_semestre})"
