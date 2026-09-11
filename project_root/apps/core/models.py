from django.db import models

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

class UnitBoundQuerySet(models.QuerySet):
    def for_user(self, user):
        if user.is_superuser or user.perfil == 'DESUP':
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

