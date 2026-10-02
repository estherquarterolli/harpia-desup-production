import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notificacao

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notificacao)
def enviar_email_notificacao_desup(sender, instance, created, **kwargs):
    """Espelha por e-mail, para os administradores DESUP, toda notificação à DESUP.

    Notificação "da DESUP" = sem destinatário e sem unidade de destino (chamados,
    justificativas extracurriculares enviadas, solicitações de cadastro, tentativas
    bloqueadas...). Avisos endereçados a uma unidade ou usuário não passam por aqui.
    """
    if not created or instance.destinatario_id or instance.unidade_destino_id:
        return

    from .services import get_desup_recipients
    from .tasks import send_email_task

    recipients = get_desup_recipients()
    if not recipients:
        return

    corpo = instance.mensagem
    if instance.url_acao:
        corpo = f"{corpo}\n\nAcesse: {instance.url_acao}"
    corpo = f"{corpo}\n\n— Notificação automática do sistema Harpia."
    assunto = f"[Harpia] {instance.titulo}"

    def _enviar():
        try:
            send_email_task.delay(
                subject=assunto,
                message=corpo,
                recipient_list=recipients,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                fail_silently=False,
            )
        except Exception:
            logger.exception("Falha ao enfileirar e-mail da notificação %s", instance.pk)

    transaction.on_commit(_enviar)
