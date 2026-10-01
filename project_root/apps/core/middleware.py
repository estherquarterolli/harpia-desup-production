import hashlib
import ipaddress
import logging
import re
import secrets
import traceback as traceback_module

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404
from django.utils.deprecation import MiddlewareMixin

from .models import ErroSistema


logger = logging.getLogger(__name__)

_SENSITIVE_PATH_PATTERNS = (
    re.compile(r'(/accounts/redefinir-senha/)[^/]+', re.IGNORECASE),
    re.compile(r'(/accounts/password_change/confirm/)[^/]+', re.IGNORECASE),
    re.compile(r'(/accounts/reset/aprovar/)[^/]+', re.IGNORECASE),
)


def _redact_sensitive_path(value):
    value = str(value or '')
    for pattern in _SENSITIVE_PATH_PATTERNS:
        value = pattern.sub(r'\1[REDACTED]', value)
    return value


def _client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidates = [forwarded_for.split(',', 1)[0].strip(), request.META.get('REMOTE_ADDR')]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def _status_for_exception(exception):
    if isinstance(exception, Http404):
        return 404
    if isinstance(exception, PermissionDenied):
        return 403
    if isinstance(exception, SuspiciousOperation):
        return 400
    return 500


class SystemErrorLoggingMiddleware(MiddlewareMixin):
    """
    Persiste exceções e respostas HTTP 4xx/5xx para diagnóstico do superadmin.

    Não armazena corpo, POST, cookies, cabeçalhos de autorização, query string ou
    tokens de URL. Uma falha no próprio banco de logs nunca pode derrubar a
    requisição original.
    """

    ignored_prefixes = ('/static/', '/media/', '/favicon.ico')

    def process_request(self, request):
        # O mesmo identificador aparece no painel e no cabeçalho da resposta,
        # facilitando localizar o erro relatado por um usuário.
        request._harpia_request_id = secrets.token_hex(8)

    def process_exception(self, request, exception):
        status = _status_for_exception(exception)
        formatted = ''.join(
            traceback_module.format_exception(type(exception), exception, exception.__traceback__)
        )
        self._save(
            request=request,
            status=status,
            error_type=type(exception).__name__,
            message=_redact_sensitive_path(str(exception)),
            traceback_text=_redact_sensitive_path(formatted),
        )
        request._harpia_error_logged = True
        return None

    def process_response(self, request, response):
        request_id = getattr(request, '_harpia_request_id', None) or secrets.token_hex(8)
        request._harpia_request_id = request_id
        if (
            response.status_code >= 400
            and not getattr(request, '_harpia_error_logged', False)
            and not request.path.startswith(self.ignored_prefixes)
        ):
            self._save(
                request=request,
                status=response.status_code,
                error_type=f'HTTP{response.status_code}',
                message=getattr(response, 'reason_phrase', '') or 'Resposta HTTP com erro',
                traceback_text='',
            )
        response['X-Request-ID'] = request_id
        return response

    def _save(self, *, request, status, error_type, message, traceback_text):
        if request.path.startswith(self.ignored_prefixes):
            return

        path = _redact_sensitive_path(request.path)[:500]
        request_id = getattr(request, '_harpia_request_id', None) or secrets.token_hex(8)
        request._harpia_request_id = request_id
        fingerprint_source = f'{status}|{error_type}|{path}'
        fingerprint = hashlib.sha256(fingerprint_source.encode('utf-8')).hexdigest()
        user = getattr(request, 'user', None)
        authenticated = bool(getattr(user, 'is_authenticated', False))

        try:
            ErroSistema.objects.create(
                usuario=user if authenticated else None,
                email_usuario=getattr(user, 'email', '') if authenticated else '',
                perfil_usuario=getattr(user, 'perfil', '') if authenticated else '',
                unidade_usuario=(
                    str(getattr(user, 'unidade', '') or '') if authenticated else ''
                )[:255],
                metodo=(request.method or '')[:10],
                caminho=path,
                status_http=status,
                tipo_erro=(error_type or '')[:255],
                mensagem=(message or '')[:4000],
                traceback=(traceback_text or '')[:30000],
                ip=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:2000],
                request_id=request_id,
                fingerprint=fingerprint,
            )
        except Exception:
            logger.exception(
                'Não foi possível persistir um erro no painel de diagnóstico.',
                extra={'request_id': request_id, 'path': path, 'status': status},
            )
