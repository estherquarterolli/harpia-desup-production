import logging
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)

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
        
        # Validação HTMX: via request.htmx (se django-htmx estiver instalado) ou verificando os headers
        is_htmx = getattr(request, 'htmx', False) or request.headers.get('HX-Request') == 'true'
        
        if is_htmx:
            html_erro = (
                "<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>"
                "Acesso negado: Você não possui o perfil necessário para acessar este recurso."
                "</div>"
            )
            return HttpResponseForbidden(html_erro)
        
        raise PermissionDenied("Você não possui o perfil necessário para acessar este recurso.")

