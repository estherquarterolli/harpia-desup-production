import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_email_task(self, subject, message, recipient_list, from_email=None, fail_silently=False):
    return send_mail(
        subject=subject,
        message=message,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=fail_silently,
    )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_notification_email_task(self, notification_id):
    """Resolve a política atual em cada execução, inclusive nas retentativas."""
    from .communication import get_desup_recipients, unidade_silenciada
    from .models import Notificacao

    notification = Notificacao.objects.filter(pk=notification_id).first()
    if notification is None or notification.destinatario_id or notification.unidade_destino_id:
        return 'ignorado'
    if unidade_silenciada(notification.unidade_origem_id):
        logger.info('E-mail de notificação silenciado na execução', extra={
            'notification_id': notification_id, 'unit_id': notification.unidade_origem_id,
            'email_status': 'silenciado',
        })
        return 'silenciado'

    recipients = get_desup_recipients(notification.unidade_origem_id)
    if not recipients:
        return 'silenciado'

    corpo = notification.mensagem
    if notification.url_acao:
        # Os avisos antigos guardam caminhos relativos; no e-mail, use a URL pública.
        url = notification.url_acao
        if url.startswith('/'):
            url = f'{settings.SITE_URL}{url}'
        corpo += f'\n\nAcesse: {url}'
    corpo += '\n\n— Notificação automática do sistema Harpia.'
    try:
        enviados = send_mail(
            subject=f'[Harpia] {notification.titulo}', message=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients, fail_silently=False,
        )
        if enviados != 1:
            raise RuntimeError('O serviço de e-mail não confirmou o envio da notificação.')
    except Exception:
        logger.exception('Falha no envio de e-mail da notificação %s', notification_id)
        raise
    logger.info('E-mail de notificação aceito pelo serviço', extra={
        'notification_id': notification_id, 'email_status': 'enviado',
    })
    return 'enviado'
