import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.tasks import send_email_task

from .models import DEFAULT_USER_PASSWORD, User

logger = logging.getLogger(__name__)


def enviar_email_novo_usuario(user):
    """Enfileira o e-mail de boas-vindas com o login e a senha padrão (primeiro acesso)."""
    try:
        send_email_task.delay(
            subject="HARPIA - Seu acesso foi criado",
            message=(
                "Olá!\n\n"
                "Sua conta no HARPIA foi criada.\n\n"
                f"E-mail de acesso: {user.email}\n"
                f"Senha padrão: {DEFAULT_USER_PASSWORD}\n\n"
                "No primeiro acesso o sistema pedirá que você cadastre uma nova senha. "
                "A senha padrão diferencia maiúsculas e minúsculas."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Falha ao enfileirar e-mail de novo usuário.",
            extra={"user_id": user.pk},
        )


@receiver(post_save, sender=User, dispatch_uid="accounts_email_novo_usuario")
def avisar_novo_usuario(sender, instance, created, raw=False, **kwargs):
    """Todo usuário novo com a senha padrão recebe, primeiro, um e-mail com o login e a senha."""
    if not created or raw or not instance.email or not instance.is_active:
        return
    # Só avisa quando a conta nasce com a senha padrão: quem define a própria senha
    # (ex.: testes, fluxos que já informam a senha) não precisa recebê-la por e-mail.
    if not instance.check_password(DEFAULT_USER_PASSWORD):
        return
    transaction.on_commit(lambda: enviar_email_novo_usuario(instance))
