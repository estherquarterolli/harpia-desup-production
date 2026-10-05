from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.http import HttpResponse


MODO_VISUALIZACAO_SESSAO = 'superadmin_modo_visualizacao'
UNIDADE_VISUALIZACAO_SESSAO = 'superadmin_unidade_visualizacao'


class SuperadminVisualizationMiddleware:
    """Aplica, apenas na requisição, o perfil operacional escolhido pelo superadmin.

    O usuário continua superadministrador no banco. Ao navegar no sistema como
    DESUP ou unidade, porém, as views recebem os mesmos atributos de um usuário
    daquele perfil. Isso reaproveita as regras de permissão e de isolamento já
    existentes, sem espalhar exceções de superusuário por cada módulo.
    """

    EXCLUDED_PREFIXES = (
        '/admin/',
        '/accounts/visualizacao/',
        '/accounts/logout/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and user.is_superuser
            and not request.path.startswith(self.EXCLUDED_PREFIXES)
        ):
            modo = request.session.get(MODO_VISUALIZACAO_SESSAO)
            if modo in ('DESUP', 'COORDENADOR_UNIDADE'):
                self._aplicar_modo(request, user, modo)

        return self.get_response(request)

    @staticmethod
    def _aplicar_modo(request, user, modo):
        unidade = None
        if modo == 'COORDENADOR_UNIDADE':
            from apps.core.models import Unidade

            unidade_id = request.session.get(UNIDADE_VISUALIZACAO_SESSAO)
            unidade = Unidade.objects.filter(pk=unidade_id, status=True).first()
            if unidade is None:
                request.session.pop(MODO_VISUALIZACAO_SESSAO, None)
                request.session.pop(UNIDADE_VISUALIZACAO_SESSAO, None)
                return

        user._harpia_superadmin_original = True
        user._harpia_perfil_original = user.perfil
        user._harpia_visualization_mode = modo

        # Fundamental para o modo unidade: os managers e as views existentes
        # não podem executar o bypass global de superusuário nesta requisição.
        user.is_superuser = False
        user.perfil = modo

        if modo == 'COORDENADOR_UNIDADE':
            user.unidade = unidade
            user.unidade_id = unidade.pk
            user._harpia_visualization_unit = unidade
        else:
            user.unidade = None
            user.unidade_id = None


class PasswordChangeForceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return self.get_response(request)

            if getattr(request.user, 'forcar_troca_senha', False):
                try:
                    change_path = reverse('password_change')
                except NoReverseMatch:
                    change_path = '/accounts/password_change/'
                
                try:
                    logout_path = reverse('logout')
                except NoReverseMatch:
                    logout_path = '/accounts/logout/'

                # Links de confirmação precisam funcionar mesmo se o usuário ainda
                # tiver uma sessão antiga com troca obrigatória pendente.
                is_confirm_link = (
                    '/accounts/password_change/confirm/' in request.path
                    or '/accounts/redefinir-senha/' in request.path
                )

                # Allow password_change, logout, static files, and media
                if request.path != change_path and request.path != logout_path and not is_confirm_link:
                    if not request.path.startswith('/static/') and not request.path.startswith('/media/'):
                        if request.headers.get('HX-Request'):
                            response = HttpResponse()
                            response['HX-Redirect'] = change_path
                            return response
                        return redirect(change_path)

        response = self.get_response(request)
        return response
