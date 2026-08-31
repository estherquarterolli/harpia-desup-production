import logging
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

ADMIN_URL = '/admin/'


class PerfilRequiredMixin:
    """
    Mixin que valida se o usuário possui um dos perfis permitidos.
    Caso a validação falhe, retorna 403. Se for requisição HTMX, retorna um HTML amigável.
    """
    allowed_profiles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Se não estiver autenticado, deixa o LoginRequiredMixin ou outro mixin lidar
            return super().dispatch(request, *args, **kwargs)

        # CORR-021: ADMIN (TI DESUP) não é perfil operacional — o foco dele é o admin
        # do Django. Vai antes do bypass de superusuário abaixo, porque o ADMIN
        # normalmente TAMBÉM é superusuário. Redireciona em vez de 403 para não
        # parecer erro: a tela certa para esse perfil é outra, não é falta de permissão.
        if request.user.perfil == 'ADMIN' and 'ADMIN' not in self.allowed_profiles:
            logger.info(
                "Perfil ADMIN redirecionado ao admin do Django (rota operacional: %s).",
                request.path,
            )
            if self._is_htmx(request):
                resposta = HttpResponse(status=204)
                resposta['HX-Redirect'] = ADMIN_URL
                return resposta
            return redirect(ADMIN_URL)

        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # Verifica se o perfil do usuário está na lista de perfis permitidos
        if request.user.perfil in self.allowed_profiles:
            return super().dispatch(request, *args, **kwargs)

        # Mapeamento para grupos caso o projeto esteja transicionando para Groups
        group_mapping = {
            'DESUP': 'Admin DESUP',
            'COORDENADOR_UNIDADE': 'Gestor Unidade'
        }
        allowed_groups = [group_mapping.get(p) for p in self.allowed_profiles if p in group_mapping]
        if request.user.groups.filter(name__in=allowed_groups).exists():
            return super().dispatch(request, *args, **kwargs)

        logger.warning(
            f"Acesso negado (403) para usuário ID: {request.user.id}, "
            f"perfil: {request.user.perfil}."
        )
        
        if self._is_htmx(request):
            html_erro = (
                "<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>"
                "Acesso negado: Você não possui o perfil necessário para acessar este recurso."
                "</div>"
            )
            return HttpResponseForbidden(html_erro)
        
        raise PermissionDenied("Você não possui o perfil necessário para acessar este recurso.")

    @staticmethod
    def _is_htmx(request):
        """Via request.htmx (se django-htmx estiver instalado) ou pelo header."""
        return bool(getattr(request, 'htmx', False)) or request.headers.get('HX-Request') == 'true'

