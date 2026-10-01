import hashlib
import ipaddress
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.tasks import send_email_task

from .models import EmailPasswordResetToken, User


logger = logging.getLogger(__name__)


def password_reset_token_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PasswordResetIssueResult:
    sent: bool
    reason: str
    available_at: object = None


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidates = [forwarded_for.split(",", 1)[0].strip(), request.META.get("REMOTE_ADDR")]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def issue_email_password_reset(*, user, request, requested_by=None):
    """
    Emite e envia um token de recuperação sem persistir o segredo em claro.

    A trava na linha do usuário impede que dois cliques simultâneos emitam dois
    links. O cooldown evita spam; a validade e o uso único são conferidos de
    novo na confirmação, dentro de transação.
    """

    if not user.is_active or not user.has_usable_password() or not user.email:
        return PasswordResetIssueResult(False, "unavailable")

    ttl_seconds = getattr(settings, "PASSWORD_RESET_TOKEN_TTL_SECONDS", 3600)
    cooldown_seconds = getattr(settings, "PASSWORD_RESET_COOLDOWN_SECONDS", 900)
    now = timezone.now()

    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        recent = (
            EmailPasswordResetToken.objects
            .filter(
                user=locked_user,
                criado_em__gte=now - timedelta(seconds=cooldown_seconds),
            )
            .order_by("-criado_em")
            .first()
        )
        if recent is not None:
            return PasswordResetIssueResult(
                False,
                "rate_limited",
                recent.criado_em + timedelta(seconds=cooldown_seconds),
            )

        # Um novo pedido invalida links anteriores ainda pendentes.
        EmailPasswordResetToken.objects.filter(
            user=locked_user,
            usado=False,
        ).update(usado=True, usado_em=now)

        raw_token = secrets.token_urlsafe(32)
        token = EmailPasswordResetToken.objects.create(
            user=locked_user,
            token_hash=password_reset_token_hash(raw_token),
            expira_em=now + timedelta(seconds=ttl_seconds),
            solicitado_ip=_client_ip(request),
            solicitado_por=requested_by,
        )
        reset_url = request.build_absolute_uri(
            reverse("email_password_reset_confirm", kwargs={"token": raw_token})
        )

        def queue_email():
            try:
                send_email_task.delay(
                    subject="HARPIA - Redefinição de senha",
                    message=(
                        "Recebemos uma solicitação para redefinir a senha da sua conta no HARPIA.\n\n"
                        f"Acesse o link abaixo para cadastrar uma nova senha:\n{reset_url}\n\n"
                        "O link é individual, pode ser usado uma única vez e expira em 1 hora. "
                        "Se você não solicitou esta alteração, ignore este e-mail."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[locked_user.email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    "Falha ao enfileirar e-mail de redefinição de senha.",
                    extra={"user_id": locked_user.pk},
                )

        transaction.on_commit(queue_email)

    logger.info(
        "Token de redefinição de senha emitido.",
        extra={"user_id": user.pk, "token_id": token.pk},
    )
    return PasswordResetIssueResult(True, "sent")
