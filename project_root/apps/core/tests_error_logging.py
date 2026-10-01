from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, HttpResponseNotFound
from django.test import RequestFactory, TestCase

from apps.accounts.admin import admin_site
from apps.accounts.models import User

from .middleware import SystemErrorLoggingMiddleware
from .models import ErroSistema


class SystemErrorLoggingMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SystemErrorLoggingMiddleware(lambda request: HttpResponse())

    def test_registra_resposta_http_de_erro(self):
        request = self.factory.get('/rota-inexistente/')
        request.user = AnonymousUser()
        self.middleware.process_request(request)

        response = self.middleware.process_response(
            request,
            HttpResponseNotFound('não encontrado'),
        )

        self.assertEqual(response.status_code, 404)
        error = ErroSistema.objects.get()
        self.assertEqual(error.status_http, 404)
        self.assertEqual(error.tipo_erro, 'HTTP404')
        self.assertEqual(error.caminho, '/rota-inexistente/')
        self.assertFalse(error.traceback)
        self.assertEqual(response['X-Request-ID'], error.request_id)

    def test_registra_excecao_com_usuario_e_traceback(self):
        user = User.objects.create_user(
            email='usuario-erro@teste.com',
            password='Senha@2026',
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )
        request = self.factory.post('/acao-com-erro/')
        request.user = user

        try:
            raise ValueError('falha controlada para teste')
        except ValueError as exception:
            self.middleware.process_exception(request, exception)

        error = ErroSistema.objects.get()
        self.assertEqual(error.status_http, 500)
        self.assertEqual(error.usuario, user)
        self.assertEqual(error.email_usuario, user.email)
        self.assertEqual(error.tipo_erro, 'ValueError')
        self.assertIn('falha controlada para teste', error.traceback)

    def test_remove_token_da_url_e_do_detalhe(self):
        secret = 'SEGREDO-QUE-NAO-PODE-SER-GRAVADO'
        request = self.factory.get(f'/accounts/redefinir-senha/{secret}/')
        request.user = AnonymousUser()

        self.middleware.process_response(request, HttpResponse(status=400))

        error = ErroSistema.objects.get()
        self.assertNotIn(secret, error.caminho)
        self.assertNotIn(secret, error.mensagem)
        self.assertIn('[REDACTED]', error.caminho)


class SystemErrorAdminPermissionTests(TestCase):
    def setUp(self):
        self.password = 'Senha@2026'
        self.superadmin = User.objects.create_superuser(
            email='super-debug@teste.com',
            password=self.password,
        )
        self.desup = User.objects.create_user(
            email='desup-sem-debug@teste.com',
            password=self.password,
            perfil=User.Perfil.DESUP,
            forcar_troca_senha=False,
        )

    def test_somente_superadmin_ve_modelo_de_erros(self):
        model_admin = admin_site._registry[ErroSistema]
        super_request = RequestFactory().get('/admin/core/errosistema/')
        super_request.user = self.superadmin
        desup_request = RequestFactory().get('/admin/core/errosistema/')
        desup_request.user = self.desup

        self.assertTrue(model_admin.has_module_permission(super_request))
        self.assertTrue(model_admin.has_view_permission(super_request))
        self.assertFalse(model_admin.has_module_permission(desup_request))
        self.assertFalse(model_admin.has_view_permission(desup_request))
        self.assertFalse(model_admin.has_add_permission(super_request))
        self.assertFalse(model_admin.has_delete_permission(super_request))
