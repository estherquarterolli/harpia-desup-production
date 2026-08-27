from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.http import HttpResponse

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

                # Is it a password confirm link? (contains /accounts/password_change/confirm/)
                is_confirm_link = '/accounts/password_change/confirm/' in request.path

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
