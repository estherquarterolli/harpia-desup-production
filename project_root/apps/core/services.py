import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.urls import reverse

from .models import JanelaEntrega, Notificacao
from .tasks import send_email_task

logger = logging.getLogger(__name__)


ACTIVE_WINDOW_STATUSES = (
    JanelaEntrega.StatusChoices.ABERTO,
    JanelaEntrega.StatusChoices.REABERTO,
)


def user_can_bypass_window(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.perfil == "DESUP"))


def fechar_janelas_expiradas():
    """
    Fecha automaticamente as janelas cujo período (data_fim) já passou, mas que
    ainda estão com status Aberto/Reaberto (o status deve refletir o fim do prazo,
    em vez de permanecer em aberto/reaberto indefinidamente).
    """
    from django.utils import timezone

    # timezone.localdate() (e não timezone.now().date()): com USE_TZ=True o `now()`
    # é UTC, então das 21h à meia-noite de Brasília o "hoje" já era o dia seguinte
    # em UTC — a janela era gravada como Fechado 3h antes do fim do prazo.
    hoje = timezone.localdate()
    JanelaEntrega.objects.filter(
        status__in=ACTIVE_WINDOW_STATUSES,
        data_fim__lt=hoje,
    ).update(status=JanelaEntrega.StatusChoices.FECHADO)


def get_delivery_window(unidade=None):
    """
    Devolve a janela vigente (ativa hoje) para a unidade, ou a global, ou None.

    Fonte de verdade única do bloqueio: views, `enforce_window_or_redirect` e o
    context processor do banner devem todos passar por aqui, senão a tela e o POST
    divergem (banner verde + ação bloqueada).
    """
    from django.utils import timezone

    fechar_janelas_expiradas()
    hoje = timezone.localdate()
    # O recorte de data entra já no queryset: filtrar antes do order_by é o que
    # garante que uma janela FUTURA da unidade (data_inicio > hoje) não "roube" a
    # vez da vigente. Antes pegava-se a de data_inicio mais recente e só depois se
    # testava `is_ativa` — se a escolhida não estivesse valendo, as demais janelas
    # da unidade nem eram consideradas e a unidade caía na global (ou em nada).
    qs = JanelaEntrega.objects.filter(
        status__in=ACTIVE_WINDOW_STATUSES,
        data_inicio__lte=hoje,
        data_fim__gte=hoje,
    )

    if unidade:
        # Override explícito de fechamento para esta unidade tem prioridade absoluta,
        # mas SOMENTE se a janela Fechado cobrir hoje. Sem esse recorte, qualquer
        # janela antiga da unidade — que `fechar_janelas_expiradas` marca como
        # Fechado ao vencer — virava um bloqueio permanente: nem uma nova janela da
        # unidade nem a global conseguiam reabrir a unidade.
        fechado_override = JanelaEntrega.objects.filter(
            unidade=unidade,
            status=JanelaEntrega.StatusChoices.FECHADO,
            data_inicio__lte=hoje,
            data_fim__gte=hoje,
        ).exists()
        if fechado_override:
            return None

        # A janela da unidade vence a global por ser consultada primeiro — não por
        # ordenação num queryset misto, que depende do backend do banco.
        janela_unidade = qs.filter(unidade=unidade).order_by("-data_inicio", "-pk").first()
        if janela_unidade:
            return janela_unidade

    janela_global = qs.filter(unidade__isnull=True).order_by("-data_inicio", "-pk").first()
    if janela_global:
        return janela_global

    return None


def can_user_edit_within_window(user, unidade=None):
    if user_can_bypass_window(user):
        return True
    return get_delivery_window(unidade) is not None


def build_window_lock_context(user, unidade=None, area_label="", action_label="", target_label="registro"):
    unidade = unidade or getattr(user, "unidade", None)
    janela = get_delivery_window(unidade)
    fechada = not user_can_bypass_window(user) and janela is None

    return {
        "window_fechada": fechada,
        "window_aberta": not fechada,
        "window_area_label": area_label,
        "window_action_label": action_label or "alterar dados",
        "window_target_label": target_label or "registro",
        "window_unit_id": unidade.pk if unidade else "",
        "window_unit_sigla": unidade.sigla if unidade else "",
        "window_ticket_url": reverse("core:solicitar_chamado_alteracao"),
        "window_message": (
            "Janela de entrega fechada. A alteração foi bloqueada e registrada para a DESUP."
            if fechada
            else ""
        ),
        "window_title": "Janela de entrega fechada" if fechada else "",
    }


def record_window_attempt(request, *, area_label, action_label, target_label="", unidade=None, details=""):
    unidade = unidade or getattr(request.user, "unidade", None)
    unidade_label = f"{unidade.sigla} - {unidade.nome}" if unidade else "Geral"
    username = request.user.get_full_name() or request.user.email
    mensagem = (
        f"O usuário {username} tentou {action_label} fora da janela de entrega. "
        f"Área: {area_label}. Alvo: {target_label or 'registro'}. "
        f"Unidade: {unidade_label}."
    )
    if details:
        mensagem = f"{mensagem} Detalhes: {details}."

    Notificacao.objects.create(
        destinatario=None,
        unidade_destino=None,
        titulo=f"Tentativa bloqueada - {area_label}",
        mensagem=mensagem,
        url_acao=reverse("core:janela_list"),
    )

    logger.warning(
        "Tentativa bloqueada fora da janela",
        extra={
            "user_id": request.user.id,
            "user_email": request.user.email,
            "perfil": request.user.perfil,
            "area": area_label,
            "action": action_label,
            "target": target_label,
            "unit_id": unidade.pk if unidade else None,
            "path": request.path,
        },
    )


def enforce_window_or_redirect(request, *, area_label, action_label, target_label="", unidade=None, details="", fallback_url=None):
    if can_user_edit_within_window(request.user, unidade):
        return None

    record_window_attempt(
        request,
        area_label=area_label,
        action_label=action_label,
        target_label=target_label,
        unidade=unidade,
        details=details,
    )
    from django.contrib import messages
    from django.shortcuts import redirect

    messages.error(
        request,
        "Janela de entrega fechada. A alteração foi bloqueada e a DESUP foi avisada.",
    )
    return redirect(fallback_url or request.META.get("HTTP_REFERER") or "/")


def get_desup_recipients():
    from apps.accounts.models import User

    return list(
        User.objects.filter(perfil="DESUP", is_active=True)
        .exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )


def create_window_ticket(*, request, area_label, action_label, target_label="", details="", unidade=None, next_url=""):
    unidade = unidade or getattr(request.user, "unidade", None)
    unidade_label = f"{unidade.sigla} - {unidade.nome}" if unidade else "Geral"
    username = request.user.get_full_name() or request.user.email
    titulo = f"Chamado - {area_label}"
    mensagem = (
        f"O gestor {username} solicitou abertura de chamado para {action_label} "
        f"fora da janela de entrega.\n\n"
        f"Área: {area_label}\n"
        f"Unidade: {unidade_label}\n"
        f"Alvo: {target_label or 'registro'}\n"
        f"Detalhes: {details or 'Sem detalhes adicionais.'}\n"
        f"Solicitante: {request.user.email}"
    )

    Notificacao.objects.create(
        destinatario=None,
        unidade_destino=None,
        titulo=titulo,
        mensagem=mensagem,
        url_acao=reverse("core:janela_list"),
    )

    recipients = get_desup_recipients()
    email_sent = False
    if recipients:
        def _queue_email():
            try:
                send_email_task.delay(
                    subject=titulo,
                    message=mensagem,
                    recipient_list=recipients,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    "Falha ao enfileirar email do chamado",
                    extra={
                        "area": area_label,
                        "action": action_label,
                        "target": target_label,
                        "unit_id": unidade.pk if unidade else None,
                    },
                )

        transaction.on_commit(_queue_email)
        email_sent = True

    logger.info(
        "Chamado de alteração criado",
        extra={
            "user_id": request.user.id,
            "perfil": request.user.perfil,
            "area": area_label,
            "action": action_label,
            "target": target_label,
            "unit_id": unidade.pk if unidade else None,
            "email_sent": email_sent,
        },
    )
    return email_sent
