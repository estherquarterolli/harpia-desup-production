import logging
from apps.core.models import Notificacao
from django.db.models import Q

logger = logging.getLogger(__name__)


def notificacoes(request):
    """
    Context processor para disponibilizar notificações não lidas para o usuário logado.
    """
    if not request.user.is_authenticated:
        return {'notificacoes_nao_lidas': [], 'total_notificacoes_nao_lidas': 0}

    try:
        user = request.user

        base_qs = Notificacao.objects.filter(lida=False).order_by('-data_criacao')

        if user.is_superuser or user.perfil == 'DESUP':
            qs = base_qs.filter(
                Q(destinatario=user) | Q(destinatario__isnull=True, unidade_destino__isnull=True)
            )
        elif user.perfil == 'COORDENADOR_UNIDADE':
            if user.unidade:
                qs = base_qs.filter(
                    Q(destinatario=user) | Q(unidade_destino=user.unidade)
                )
            else:
                qs = base_qs.filter(destinatario=user)
        else:
            qs = base_qs.filter(destinatario=user)

        qs = qs.distinct()
        notifs = list(qs[:10])
        return {
            'notificacoes_nao_lidas': notifs,
            'total_notificacoes_nao_lidas': len(notifs),
        }
    except Exception:
        logger.exception("Erro ao carregar notificações no context processor")
        return {'notificacoes_nao_lidas': [], 'total_notificacoes_nao_lidas': 0}


def delivery_window_context(request):
    if not request.user.is_authenticated:
        return {}

    # ESCOPO DA JANELA DE ENTREGA (decisão do cliente, 2026-08-01 — CORR-024):
    # a janela controla o que o COORDENADOR DE UNIDADE pode alterar em duas áreas,
    # e só nelas — **alocação curricular** e **justificativas extracurriculares**.
    #
    # O **cadastro de professor passa fora da janela**, de propósito: editar,
    # excluir e duplicar docente continuam liberados com a janela fechada. Isso
    # NÃO é um furo — é a regra vigente até o cliente final mudar de ideia. Se uma
    # auditoria futura apontar "rotas de professor sem enforce", confirme a decisão
    # antes de "corrigir".
    #
    # O CRUD de matriz em si é DESUP-only, e DESUP faz bypass da janela
    # (`user_can_bypass_window`), então na prática a janela nunca o alcança; o que
    # a unidade faz sobre a matriz é a alocação, coberta acima.
    #
    # As rotas de alocação curricular não usam namespace, então o escopo é decidido
    # pelo prefixo da URL.
    areas_com_janela = ('/alocacao-curricular/', '/extracurriculares/')
    if not request.path.startswith(areas_com_janela):
        return {}

    try:
        from apps.core.services import get_delivery_window, user_can_bypass_window

        user = request.user
        unidade = getattr(user, 'unidade', None)

        # O banner precisa dizer exatamente o que o POST vai fazer. Antes este
        # processor reimplementava a regra da janela (override Fechado sem recorte
        # de data, ordenação `-unidade` que na verdade ordenava por nome e invertia
        # no PostgreSQL, etc.) e divergia de `get_delivery_window` — dava o cenário
        # "banner verde na tela, ação bloqueada no POST". Agora existe uma única
        # fonte de verdade; `get_delivery_window` já roda `fechar_janelas_expiradas`.
        escopo = unidade if (user.perfil == 'COORDENADOR_UNIDADE' and unidade) else None
        janela = get_delivery_window(escopo)

        if janela:
            return {
                'janela_ativa': janela,
                'janela_data_fim': janela.data_fim.strftime('%d/%m/%Y'),
            }

        # DESUP/superusuário fazem bypass da janela, então nunca veem o aviso de
        # "fechada". Quem não tem unidade também não tem escopo a bloquear.
        if escopo and not user_can_bypass_window(user):
            return {'janela_fechada': True}
    except Exception:
        logger.exception("Erro ao carregar contexto da janela de entrega")

    return {}
