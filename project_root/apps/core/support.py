"""Envio síncrono com reserva persistida, limites por usuário e contexto assinado."""
import logging
import uuid
from datetime import timedelta
from email.utils import parseaddr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import DatabaseError, transaction
from django.utils import timezone

from .ajuda import AJUDA_PAGINAS, AJUDA_PAGINAS_COORDENADOR, ajuda_generica
from .models import SolicitacaoSuporte
from .support_forms import TIPOS_SUPORTE

logger = logging.getLogger(__name__)
SALT = 'harpia.suporte.v1'
COOLDOWN_SECONDS = 60
HOURLY_LIMIT = 5


def pagina_suporte(route):
    # Somente nomes de funcionalidades conhecidos; nunca URL, query string,
    # identificador de registro, token ou Referer fornecido pelo navegador.
    paginas = {**AJUDA_PAGINAS, **AJUDA_PAGINAS_COORDENADOR}
    if route in paginas:
        return paginas[route]['titulo']
    titulo = ajuda_generica(route)['titulo']
    return titulo if titulo != 'Ajuda da página' else 'Central de Ajuda'


def novo_contexto(user, pagina):
    return signing.dumps({'usuario': user.pk, 'id': str(uuid.uuid4()), 'pagina': pagina}, salt=SALT)


def ler_contexto(token, user):
    try:
        dados = signing.loads(token, salt=SALT, max_age=7200)
        if dados['usuario'] != user.pk:
            raise ValueError
        dados['id'] = uuid.UUID(dados['id'])
        if not isinstance(dados['pagina'], str) or len(dados['pagina']) > 150:
            raise ValueError
        return dados
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise ValidationError('O formulário expirou ou é inválido. Reabra a Central de Ajuda antes de enviar.') from None


def email_suporte():
    """A caixa institucional de envio também recebe o suporte por padrão."""
    return settings.HARPIA_SUPPORT_EMAIL or parseaddr(settings.DEFAULT_FROM_EMAIL)[1]


def motivo_email_indisponivel():
    try:
        validate_email(email_suporte())
        validate_email(parseaddr(settings.DEFAULT_FROM_EMAIL)[1])
        if '\r' in settings.DEFAULT_FROM_EMAIL or '\n' in settings.DEFAULT_FROM_EMAIL:
            return 'O endereço do remetente não está configurado corretamente.'
    except ValidationError:
        return 'O endereço de suporte ou do remetente não está configurado corretamente.'
    # Estes backends não encaminham mensagens à equipe de suporte.
    if settings.EMAIL_BACKEND in {
        'django.core.mail.backends.console.EmailBackend',
        'django.core.mail.backends.dummy.EmailBackend',
        'django.core.mail.backends.filebased.EmailBackend',
    }:
        return 'Este ambiente está em modo de simulação de e-mail. Nenhuma mensagem será encaminhada à equipe de suporte.'
    return ''


def email_disponivel():
    return not motivo_email_indisponivel()


class SuporteErro(Exception):
    def __init__(self, mensagem, *, renovar_contexto=False):
        super().__init__(mensagem)
        self.renovar_contexto = renovar_contexto


def _reservar_envio(user, contexto):
    now = timezone.now()
    # O bloqueio no usuário serializa reservas de abas/sessões diferentes no
    # PostgreSQL/MySQL. Nenhum bloqueio fica aberto durante a chamada SMTP.
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        existente = SolicitacaoSuporte.objects.filter(pk=contexto['id'], usuario=user).first()
        if existente:
            if existente.status == SolicitacaoSuporte.Status.ENVIADO:
                return existente, True
            if existente.status == SolicitacaoSuporte.Status.FALHOU:
                raise SuporteErro('Este envio falhou. Reabra a Central de Ajuda para tentar novamente.')
            raise SuporteErro(f'Este envio está em andamento ou sem confirmação. Evite reenviá-lo; consulte a equipe responsável. Referência: {existente.pk}.')

        recentes = SolicitacaoSuporte.objects.filter(usuario=user, criado_em__gte=now - timedelta(hours=1))
        if recentes.filter(criado_em__gte=now - timedelta(seconds=COOLDOWN_SECONDS)).exists():
            raise SuporteErro('Aguarde um minuto entre tentativas de envio de suporte.')
        if recentes.count() >= HOURLY_LIMIT:
            raise SuporteErro('O limite de cinco tentativas por hora foi atingido. Tente novamente mais tarde.')
        recibo = SolicitacaoSuporte.objects.create(
            id=contexto['id'], usuario=user, unidade_id=user.unidade_id, criado_em=now,
        )
    return recibo, False


def enviar_suporte(user, cleaned_data, contexto):
    motivo = motivo_email_indisponivel()
    if motivo:
        raise SuporteErro(f'O envio de suporte está indisponível. {motivo}')
    try:
        recibo, ja_enviado = _reservar_envio(user, contexto)
    except DatabaseError as exc:
        logger.error('Falha ao reservar envio de suporte erro=%s', type(exc).__name__)
        raise SuporteErro('O envio está temporariamente indisponível. Nenhum e-mail foi enviado. Tente novamente mais tarde.') from None
    if ja_enviado:
        return recibo
    now = recibo.criado_em

    unidade = user.unidade
    perfil = user.get_perfil_display()
    if getattr(user, '_harpia_superadmin_original', False):
        perfil = f'{perfil} (visualização por administrador)'
    texto = '\n'.join([
        'HARPIA — SOLICITAÇÃO DE SUPORTE TÉCNICO',
        f'Referência: {recibo.pk}',
        f'Tipo: {dict(TIPOS_SUPORTE)[cleaned_data["tipo"]]}',
        f'Assunto: {cleaned_data["assunto"]}',
        '', 'CONTEXTO',
        f'Usuário: {user.get_full_name() or user.email}',
        f'E-mail para resposta: {user.email}',
        f'Unidade: {unidade if unidade else "Sem unidade vinculada"}',
        f'Perfil: {perfil}',
        f'Data e hora: {timezone.localtime(now):%d/%m/%Y %H:%M:%S %z}',
        f'Funcionalidade de origem: {contexto["pagina"]}',
        '', 'DESCRIÇÃO', cleaned_data['descricao'], '',
        'Este contato não altera dados nem substitui solicitações administrativas ou aprovações do sistema.',
    ])
    try:
        message = EmailMessage(
            subject=f'[HARPIA][SUPORTE][{cleaned_data["tipo"]}] {cleaned_data["assunto"]}',
            body=texto, from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email_suporte()], reply_to=[user.email],
        )
        if message.send(fail_silently=False) != 1:
            raise SuporteErro('O serviço não confirmou o envio.')
    except Exception as exc:
        try:
            SolicitacaoSuporte.objects.filter(pk=recibo.pk).update(status=SolicitacaoSuporte.Status.FALHOU)
        except DatabaseError:
            logger.error('Resultado do envio de suporte não persistido referencia=%s', recibo.pk)
            raise SuporteErro(f'Não foi possível confirmar o resultado deste envio. Confira com a equipe responsável antes de tentar novamente. Referência: {recibo.pk}.') from None
        # Não registrar corpo, assunto, endereços, credenciais nem a mensagem
        # da exceção SMTP, que pode conter dados da mensagem rejeitada.
        logger.error('Falha no envio de suporte referencia=%s erro=%s', recibo.pk, type(exc).__name__)
        raise SuporteErro(f'Não foi possível confirmar o envio do e-mail. O formulário foi preservado. Aguarde um minuto e tente novamente; em caso de timeout, confira antes com a equipe para evitar duplicação. Referência: {recibo.pk}.', renovar_contexto=True) from None

    # Se o processo cair entre SMTP e esta atualização, permanece ENVIANDO:
    # resultado incerto, sem retentativa automática e sem falso sucesso.
    try:
        SolicitacaoSuporte.objects.filter(pk=recibo.pk).update(
            status=SolicitacaoSuporte.Status.ENVIADO, enviado_em=timezone.now(),
        )
    except DatabaseError:
        logger.error('Aceitação SMTP de suporte não persistida referencia=%s', recibo.pk)
        raise SuporteErro(f'O serviço de e-mail aceitou a mensagem, mas não foi possível registrar a confirmação. Não reenvie; confira com a equipe responsável. Referência: {recibo.pk}.') from None
    recibo.status = SolicitacaoSuporte.Status.ENVIADO
    return recibo
