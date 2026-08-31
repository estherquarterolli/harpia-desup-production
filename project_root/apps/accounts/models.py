import uuid
from datetime import timedelta

from decouple import config
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

DEFAULT_USER_PASSWORD = config("DEFAULT_USER_PASSWORD", default="Faetec@123")


class UserManager(BaseUserManager):
    """
    Custom manager for User where email is the login identifier.
    """
    def generate_unique_username(self, base_username):
        if not base_username:
            raise ValueError("A username base is required.")
        max_length = self.model._meta.get_field("username").max_length
        base_username = str(base_username)[:max_length]
        candidate = base_username
        counter = 1
        while self.filter(username=candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base_username[:max_length - len(suffix)]}{suffix}"
            counter += 1
        return candidate

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.pop("cpf", None)
        extra_fields.pop("telefone", None)
        extra_fields["username"] = self.generate_unique_username(
            extra_fields.get("username") or email
        )
        user = self.model(email=email, **extra_fields)
        user.set_password(password or DEFAULT_USER_PASSWORD)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # CORR-021: quem cria superusuário é o time de TI/DEV — o perfil padrão passou
        # a ser ADMIN (antes era DESUP, o que misturava TI com a operação da DESUP).
        # Ainda dá para passar `perfil=` explicitamente quando a conta também operar.
        extra_fields.setdefault("perfil", "ADMIN")
        extra_fields.setdefault("forcar_troca_senha", False)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password or DEFAULT_USER_PASSWORD, **extra_fields)


class User(AbstractUser):
    """
    Custom user model for Harpia.
    Uses email as the login key and profile system.
    """

    class Perfil(models.TextChoices):
        """
        CORR-021 — os três perfis oficiais do sistema.

        `ADMIN` é o time de TI/DEV: cuida do desenvolvimento e usa o **admin do
        Django** para testes e ajustes. Não é um perfil operacional e não precisa
        dos dashboards — a operação do dia a dia é dividida apenas entre
        `DESUP` (Coordenação DESUP) e `COORDENADOR_UNIDADE`.
        """
        ADMIN = "ADMIN", _("Administrador (TI DESUP)")
        DESUP = "DESUP", _("Coordenador DESUP")
        COORDENADOR_UNIDADE = "COORDENADOR_UNIDADE", _("Coordenador de Unidade")

    email = models.EmailField(unique=True, verbose_name=_("E-mail"))

    perfil = models.CharField(
        max_length=30,
        choices=Perfil.choices,
        default=Perfil.COORDENADOR_UNIDADE,
        verbose_name="Perfil de Acesso",
    )

    unidade = models.ForeignKey(
        "core.Unidade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
        verbose_name="Unidade de Ensino",
    )

    dados_submetidos = models.BooleanField(
        default=False,
        verbose_name="Dados ja submetidos?",
    )

    forcar_troca_senha = models.BooleanField(
        default=True,
        verbose_name="Forcar troca de senha",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["email"]

    def save(self, *args, **kwargs):
        """
        Ensure a unique username when creating new users.
        """
        if self._state.adding and self.email:
            self.username = self.__class__.objects.generate_unique_username(
                self.username or self.email
            )
        # CORR-021: o perfil ADMIN opera exclusivamente pelo admin do Django, que
        # exige `is_staff`. Sem isso seria possível criar um ADMIN sem acesso à
        # única tela que o perfil usa.
        if self.perfil == self.Perfil.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.get_perfil_display()})"


class PasswordResetRequest(models.Model):
    """
    Stores a password reset request for later approval.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_requests")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizado = models.BooleanField(default=False)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    aprovado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aprovacoes_reset",
    )

    # SEC-004: rate-limit do "esqueci minha senha". O endpoint é PÚBLICO (não
    # exige sessão), e sem limite cada POST criava uma solicitação, uma
    # notificação por destinatário e um e-mail para toda a DESUP — em laço, vira
    # e-mail bombing e a aprovação legítima se perde no ruído. Igual ao cooldown
    # que a CORR-020 aplicou no fluxo autenticado.
    COOLDOWN = timedelta(hours=24)

    class Meta:
        verbose_name = "Solicitacao de Reset"
        verbose_name_plural = "Solicitacoes de Reset"
        ordering = ["-criado_em"]

    @classmethod
    def pedido_pendente(cls, user):
        """
        Solicitação ainda válida e não aprovada para este usuário, ou `None`.

        Como a janela do cooldown é igual à validade do token (24h), isso é o
        mesmo que "existe pedido em aberto": aprovado (`finalizado`) ou expirado
        libera um pedido novo.
        """
        return (
            cls.objects
            .filter(user=user, finalizado=False, criado_em__gte=timezone.now() - cls.COOLDOWN)
            .order_by("-criado_em")
            .first()
        )

    @property
    def is_expirado(self):
        return timezone.now() > self.criado_em + timedelta(hours=24)

    def __str__(self):
        return f"Reset: {self.user.email} - {'Finalizado' if self.finalizado else 'Pendente'}"


class SelfPasswordChangeRequest(models.Model):
    """
    Token para troca de senha solicitada pelo proprio usuario apos o primeiro acesso.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="self_password_change_requests")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)
    usado_em = models.DateTimeField(null=True, blank=True)
    solicitado_ip = models.GenericIPAddressField(null=True, blank=True)

    # CORR-020: rate-limit — no máximo um pedido de link por usuário a cada 24h.
    # A view ignora o limite quando `settings.DEBUG` (ambiente de desenvolvimento).
    COOLDOWN = timedelta(days=1)

    class Meta:
        verbose_name = "Solicitacao de Troca de Senha"
        verbose_name_plural = "Solicitacoes de Troca de Senha"
        ordering = ["-criado_em"]

    @classmethod
    def pedido_recente(cls, user):
        """Último pedido do usuário ainda dentro da janela de cooldown, ou `None`."""
        return (
            cls.objects
            .filter(user=user, criado_em__gte=timezone.now() - cls.COOLDOWN)
            .order_by("-criado_em")
            .first()
        )

    @property
    def liberado_em(self):
        """Momento em que o usuário poderá pedir um novo link."""
        return self.criado_em + self.COOLDOWN

    @property
    def is_expirado(self):
        return timezone.now() > self.criado_em + timedelta(hours=1)

    def __str__(self):
        return f"Troca de senha: {self.user.email} - {'Usado' if self.usado else 'Pendente'}"
