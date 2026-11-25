import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notificacao

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notificacao)
def enviar_email_notificacao_desup(sender, instance, created, raw=False, **kwargs):
    """Enfileira avisos à DESUP após commit, respeitando a unidade de origem."""
    if raw or not created or instance.destinatario_id or instance.unidade_destino_id:
        return

    from .communication import unidade_silenciada
    from .tasks import send_notification_email_task

    def _enviar():
        try:
            if unidade_silenciada(instance.unidade_origem_id):
                logger.info('E-mail de notificação silenciado', extra={
                    'notification_id': instance.pk, 'unit_id': instance.unidade_origem_id,
                    'email_status': 'silenciado',
                })
                instance._email_status = 'silenciado'
                return
            send_notification_email_task.delay(instance.pk)
            instance._email_status = 'enfileirado'
            logger.info('E-mail de notificação enfileirado', extra={
                'notification_id': instance.pk, 'email_status': 'enfileirado',
            })
        except Exception:
            instance._email_status = 'falhou'
            logger.exception("Falha ao enfileirar e-mail da notificação %s", instance.pk)

    instance._email_status = 'aguardando_commit'
    transaction.on_commit(_enviar)
