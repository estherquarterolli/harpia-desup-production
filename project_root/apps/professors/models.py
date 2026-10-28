from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import UnitBoundManager

TIPOS_CONTRATO_PERMITIDOS = [
    'PROF FAETEC ENS SUP 40H',
    'PROFESSOR FAETEC I 20 H',
    'PROFESSOR FAETEC I 40 H',
    'PROFESSOR FAETEC II - 40 H/ QD SUPL',
    "PROFESSOR INSPETOR ESCOLAR L9146'2020",
    "PROFESSOR SUPERVISOR EDUCACIONAL L9146'2020",
    'SUPERVISOR EDUCACIONAL',
    'TÉCNICO SUPERIOR',
    'ORIENTADOR EDUCACIONAL',
    'PROFESSOR CEDIDO',
]


class ContractTypeQuerySet(models.QuerySet):
    def permitidos(self):
        """Somente os tipos de contrato oficiais (lista da DESUP)."""
        return self.filter(nome__in=TIPOS_CONTRATO_PERMITIDOS)


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

    objects = ContractTypeQuerySet.as_manager()

    class Meta:
        db_table = "harpiadb_professores_tipo_contrato"
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

    class NivelEnsinoOrigemChoices(models.TextChoices):
        NAO_INFORMADO = 'NAO_INFORMADO', 'Não informado'
        MEDIO = 'MEDIO', 'Ensino Médio'
        SUPERIOR = 'SUPERIOR', 'Ensino Superior'
        AMBOS = 'AMBOS', 'Ensino Médio e Superior'

    class VinculoEmpregaticioChoices(models.TextChoices):
        EFETIVO = 'EFETIVO', 'Efetivo'
        CONTR_TEMPORARIO = 'CONTR TEMPORARIO', 'Contrato temporário'
        CARGO_COMISSAO = 'CARGO COMISSAO', 'Cargo em comissão'
        REQUISICAO_INTERNA = 'REQUISICAO INTERNA', 'Requisição interna'
        REQUISICAO_EXTERNA = 'REQUISICAO EXTERNA', 'Requisição externa'
        TERCEIRIZADO = 'TERCEIRIZADO', 'Terceirizado'

    # --- Campos Originais RH (Read-only por Regra de Negócio) ---
    id_funcional = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        db_column="ID_FUNCIONAL",
        verbose_name="ID Funcional",
    )
    rh_matricula = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        verbose_name="Matrícula RH",
        help_text="Opcional: nem todo professor possui matrícula.",
    )
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

    unidades = models.ManyToManyField(
        'core.Unidade',
        blank=True,
        related_name='professores_vinculados',
        verbose_name='Unidades',
        db_table='harpiadb_professores_professor_unidades',
        help_text='Unidades às quais o professor está vinculado.',
    )

    locais_lotacao = models.TextField(
        blank=True,
        default='',
        verbose_name="Locais de lotação (não são unidades)",
        help_text="Setores de origem que não correspondem a uma unidade do sistema, separados por ' | '.",
    )

    setor_origem = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Setor de origem (PDF/RH)',
        help_text='Descrição do setor na fonte de pessoal; não altera os vínculos com unidades.',
    )

    cargo_origem = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Cargo de origem (PDF/RH)',
        help_text='Texto original do cargo; o tipo de contrato do sistema define os limites de carga.',
    )

    vinculo_empregaticio = models.CharField(
        max_length=30, choices=VinculoEmpregaticioChoices.choices,
        blank=True, default='', verbose_name='Vínculo empregatício',
        help_text='Vínculo individual do professor, independente do cargo.',
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

    carga_diferenciada = models.BooleanField(
        default=False,
        verbose_name="Professor com carga diferente",
        help_text="Marque quando a carga horária deste professor não é a do tipo de contrato.",
    )
    carga_horaria_personalizada = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Carga horária total (h)",
        help_text="Carga semanal total. A alocação em sala é metade (20h → 10h; 40h → 20h).",
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
        verbose_name="Cursos",
        db_table="harpiadb_professores_professor_cursos",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ATIVO,
        verbose_name="Status"
    )

    nivel_ensino_origem = models.CharField(
        max_length=20,
        choices=NivelEnsinoOrigemChoices.choices,
        default=NivelEnsinoOrigemChoices.NAO_INFORMADO,
        db_index=True,
        verbose_name="Nível de ensino de origem",
        help_text="Informação institucional usada para alertar atuações no Ensino Superior.",
    )

    area_atuacao = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="Área de atuação",
        help_text="Área de conhecimento em que o professor atua (ex.: Matemática, Computação).",
    )

    class Meta:
        db_table = "harpiadb_professores_professor"
        verbose_name = "Professor"
        verbose_name_plural = "Professores"
        ordering = ['rh_nome']

    objects = UnitBoundManager()

    def __str__(self):
        if self.rh_matricula:
            return f"{self.nome} ({self.id_funcional} / {self.rh_matricula})"
        return f"{self.nome} ({self.id_funcional})"

    def clean(self):
        super().clean()
        self.normalizar_nomes()
        if self.carga_diferenciada and not self.carga_horaria_personalizada:
            raise ValidationError({
                "carga_horaria_personalizada": "Informe a carga horária deste professor.",
            })
        if not self.carga_diferenciada:
            self.carga_horaria_personalizada = None
        if self.id_funcional and self.rh_matricula and self.id_funcional == self.rh_matricula:
            raise ValidationError({
                "rh_matricula": "A matrícula deve ser diferente do ID Funcional.",
            })

    def normalizar_nomes(self):
        for campo in ('rh_nome', 'desup_nome'):
            valor = getattr(self, campo)
            if valor is not None:
                setattr(self, campo, valor.upper())

    def save(self, *args, **kwargs):
        self.normalizar_nomes()
        return super().save(*args, **kwargs)

    # --- Getters com Lógica de Sobrescrita (Regra #3) ---

    @property
    def nome(self):
        nome = self.desup_nome if self.desup_nome else self.rh_nome
        return " ".join(nome.split()).upper() if nome else ""

    @property
    def email(self):
        return self.desup_email if self.desup_email else self.rh_email

    @property
    def unidades_exibicao(self):
        """Relação múltipla, com fallback para cadastros legados ainda não migrados."""
        unidades = list(self.unidades.all())
        if not unidades and self.unidade_principal_id:
            return [self.unidade_principal]
        return unidades

    @property
    def locais_lotacao_lista(self):
        return [l.strip() for l in (self.locais_lotacao or '').split('|') if l.strip()]

    # --- Propriedades para Dashboard (UC08) e Limites (UC05) ---

    @property
    def carga_total_efetiva(self) -> int:
        """Carga total: a personalizada (se marcada) ou a do tipo de contrato."""
        if self.carga_diferenciada and self.carga_horaria_personalizada:
            return self.carga_horaria_personalizada
        return self.tipo_contrato.max_total_hours if self.tipo_contrato else 0

    @property
    def reducao_carga_vigente(self) -> float:
        """Horas semanais de redução determinadas pela DESUP (equipe diretiva) hoje vigentes.

        Usa `ocupacoes_diretivas` — se a consulta já fez prefetch, não gera query por professor.
        """
        from django.utils import timezone

        hoje = timezone.localdate()
        total = 0.0
        for ocupacao in self.ocupacoes_diretivas.all():
            if ocupacao.vigente:
                total += float(ocupacao.carga_reducao_horas or 0)
        return total

    @property
    def readaptado_vigente(self) -> bool:
        """Há readaptação formal (DESUP) vigente hoje. Usa prefetch de `readaptacoes` se existir."""
        from django.utils import timezone

        hoje = timezone.localdate()
        return any(
            r.pausado_em is None and r.data_inicio <= hoje and (r.data_fim is None or r.data_fim >= hoje)
            for r in self.readaptacoes.all()
        )

    def vinculado_a_unidade(self, unidade_id) -> bool:
        """Pertence à unidade (principal, vínculo adicional ou cessão aprovada)."""
        if not unidade_id:
            return True
        unidade_id = int(unidade_id)
        if self.unidade_principal_id == unidade_id or any(
            u.pk == unidade_id for u in self.unidades.all()
        ):
            return True
        from apps.core.models import SolicitacaoProfessorExterno
        return SolicitacaoProfessorExterno.objects.filter(
            professor_id=self.pk,
            unidade_solicitante_id=unidade_id,
            tipo=SolicitacaoProfessorExterno.TipoChoices.CESSAO,
            status=SolicitacaoProfessorExterno.StatusChoices.APROVADA,
        ).exists()

    @property
    def meta_horas_base_sala(self) -> int:
        """Limite de horas em sala antes da redução: metade da carga personalizada, ou o do contrato."""
        if self.carga_diferenciada and self.carga_horaria_personalizada:
            return self.carga_horaria_personalizada // 2
        return self.tipo_contrato.max_class_hours if self.tipo_contrato else 0

    @property
    def meta_horas_sala(self):
        """Limite de horas em sala já descontada a redução vigente determinada pela DESUP.

        Professor readaptado não tem cobrança de carga horária: a meta é zero e
        o que estiver alocado conta como alocação completa.
        """
        if self.readaptado_vigente:
            return 0.0
        base = self.meta_horas_base_sala
        reducao = self.reducao_carga_vigente
        if not reducao:
            return base
        return max(base - reducao, 0.0)

    @property
    def ch_total(self) -> int:
        """Retorna o limite de horas total do contrato vinculado."""
        return self.carga_total_efetiva

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
            total = sum(float(p.ch_total_justificada) for p in pendencias)
            # Estágio (orientação/supervisão/coordenação) vigente no semestre.
            from django.db.models import Q
            from django.utils import timezone

            hoje = timezone.localdate()
            estagios = self.atividades_estagio_supervisao.filter(
                semestre=semestre_atual(), data_inicio__lte=hoje,
            ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
            return total + sum(float(e.carga_horaria_semanal) for e in estagios)
        except Exception:
            return 0.0

    @property
    def ch_alocada(self) -> int:
        """Soma CH alocada; componentes compartilhados contam uma única vez."""
        try:
            vistos = set()
            total = 0
            from apps.allocations.services import alocacoes_vigentes

            linhas = alocacoes_vigentes().filter(docente=self).select_related(
                'componente_matriz', 'componente_matriz__componente_curricular'
            )
            for linha in linhas:
                comp = linha.componente_matriz
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
        meta = self.meta_horas_sala
        return max(meta - self.ch_alocada, 0)

    @property
    def ch_nao_alocada(self) -> int:
        """Retorna as horas restantes do professor."""
        try:
            saldo = self.ch_total - (self.ch_alocada + self.ch_justificada + self.reducao_carga_vigente)
            return max(saldo, 0)
        except Exception:
            return 0

    @property
    def percentual_alocado(self) -> float:
        """Retorna a porcentagem alocada (incluindo horas justificadas), limitada a 100%."""
        try:
            if self.readaptado_vigente:
                return 100.0
            if self.ch_total == 0:
                return 0.0
            total_alocado = self.ch_alocada + self.ch_justificada + self.reducao_carga_vigente
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
    def vinculo_empregaticio_codigo(self) -> str:
        if self.vinculo_empregaticio:
            return self.vinculo_empregaticio
        if self.tipo_contrato_id:
            categoria = self.tipo_contrato.categoria
            return (self.VinculoEmpregaticioChoices.EFETIVO
                    if categoria == ContractType.CategoriaChoices.CONCURSADO else categoria)
        return ''

    @property
    def vinculo_empregaticio_exibicao(self) -> str:
        return dict(self.VinculoEmpregaticioChoices.choices).get(
            self.vinculo_empregaticio_codigo, '—'
        )

    @property
    def dias_presenca_obrigatorios(self) -> int:
        if self.tipo_contrato:
            return self.tipo_contrato.dias_presenca_obrigatorios
        return 0

    def get_disciplinas_alocadas(self):
        """Disciplinas distintas em que o professor está alocado na matriz vigente.

        Inclui tanto disciplinas do catálogo quanto temporárias (`nome_temporario`,
        sem registro em CurricularComponent) — por isso usa `nome_disciplina`
        (property) em vez de filtrar direto no banco por `componente_curricular__nome`.
        """
        from apps.allocations.services import alocacoes_vigentes
        linhas = alocacoes_vigentes().filter(docente=self).select_related(
            'componente_matriz', 'componente_matriz__componente_curricular'
        )
        nomes = {l.componente_matriz.nome_disciplina for l in linhas if l.componente_matriz.nome_disciplina}
        return sorted(nomes)

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
        db_table = "harpiadb_professores_disponibilidade"
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
        db_table = "harpiadb_professores_ausencia"
        verbose_name = "Registro de Ausência"
        verbose_name_plural = "Registros de Ausência"
        ordering = ['-data_inicio']

    def __str__(self):
        return f"Ausência: {self.professor.nome} ({self.data_inicio} a {self.data_fim})"


def filtro_vinculo_empregaticio(valor, prefixo=''):
    """Filtra o vínculo individual, usando a categoria antiga enquanto ele não foi importado."""
    if valor not in dict(Professor.VinculoEmpregaticioChoices.choices):
        return models.Q()
    campo = f'{prefixo}vinculo_empregaticio'
    categoria = f'{prefixo}tipo_contrato__categoria__in'
    categorias_legadas = (
        [ContractType.CategoriaChoices.EFETIVO, ContractType.CategoriaChoices.CONCURSADO]
        if valor == Professor.VinculoEmpregaticioChoices.EFETIVO else [valor]
    )
    return models.Q(**{campo: valor}) | (
        models.Q(**{campo: ''}) & models.Q(**{categoria: categorias_legadas})
    )
