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

    # O indicador de janela de entrega só é relevante nas áreas de Alocação
    # Curricular e Extracurricular — nas demais telas (professores, matrizes, etc.)
    # a janela não se aplica mais. As rotas de alocação curricular não usam
    # namespace, então o escopo é decidido pelo prefixo da URL.
    areas_com_janela = ('/alocacao-curricular/', '/extracurriculares/')
    if not request.path.startswith(areas_com_janela):
        return {}

    try:
        from apps.core.models import JanelaEntrega
        from apps.core.services import fechar_janelas_expiradas
        from django.utils import timezone

        fechar_janelas_expiradas()

        hoje = timezone.now().date()
        user = request.user
        unidade = getattr(user, 'unidade', None)

        if user.perfil == 'COORDENADOR_UNIDADE' and unidade:
            # Se existe override FECHADO para esta unidade, janela está fechada
            if JanelaEntrega.objects.filter(unidade=unidade, status='Fechado').exists():
                return {'janela_fechada': True}
            janela = JanelaEntrega.objects.filter(
                Q(status='Aberto') | Q(status='Reaberto'),
                data_inicio__lte=hoje,
                data_fim__gte=hoje,
            ).filter(Q(unidade=unidade) | Q(unidade__isnull=True)).order_by('-unidade').first()
            if janela and janela.is_ativa:
                return {
                    'janela_ativa': janela,
                    'janela_data_fim': janela.data_fim.strftime('%d/%m/%Y'),
                }
            return {'janela_fechada': True}
        else:
            janela = JanelaEntrega.objects.filter(
                Q(status='Aberto') | Q(status='Reaberto'),
                data_inicio__lte=hoje,
                data_fim__gte=hoje,
                unidade__isnull=True,
            ).first()

        if janela:
            return {
                'janela_ativa': janela,
                'janela_data_fim': janela.data_fim.strftime('%d/%m/%Y'),
            }
    except Exception:
        logger.exception("Erro ao carregar contexto da janela de entrega")

    return {}
