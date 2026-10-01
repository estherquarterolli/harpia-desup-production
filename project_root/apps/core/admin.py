from django.contrib import admin
from unfold.admin import ModelAdmin
from apps.accounts.admin import admin_site
from .models import Unidade, JanelaEntrega, Notificacao, AuditoriaGlobal, ErroSistema
from .forms import JanelaEntregaForm

class UnidadeAdmin(ModelAdmin):
    list_display = ('nome', 'sigla', 'status')
    search_fields = ('nome', 'sigla')
    list_filter = ('status',)

class JanelaEntregaAdmin(ModelAdmin):
    form = JanelaEntregaForm
    list_display = ('semestre', 'data_inicio', 'data_fim', 'status', 'unidade')
    list_filter = ('status', 'semestre', 'unidade')
    search_fields = ('semestre',)

class NotificacaoAdmin(ModelAdmin):
    list_display = ('titulo', 'destinatario', 'unidade_destino', 'lida', 'data_criacao')
    list_filter = ('lida', 'unidade_destino', 'data_criacao')
    search_fields = ('titulo', 'mensagem')
    ordering = ('-data_criacao',)

class AuditoriaGlobalAdmin(ModelAdmin):
    list_display = ('criado_em', 'acao', 'email', 'usuario', 'ip')
    list_filter = ('acao', 'criado_em')
    search_fields = ('email', 'acao', 'detalhes', 'ip')
    readonly_fields = ('usuario', 'email', 'acao', 'detalhes', 'ip', 'user_agent', 'criado_em')
    ordering = ('-criado_em',)


class ErroSistemaAdmin(ModelAdmin):
    list_display = (
        'criado_em', 'status_http', 'tipo_erro', 'metodo', 'caminho',
        'email_usuario', 'request_id',
    )
    list_filter = ('status_http', 'tipo_erro', 'perfil_usuario', 'criado_em')
    search_fields = (
        'request_id', 'email_usuario', 'caminho', 'tipo_erro',
        'mensagem', 'fingerprint',
    )
    readonly_fields = (
        'criado_em', 'status_http', 'tipo_erro', 'mensagem', 'traceback',
        'metodo', 'caminho', 'usuario', 'email_usuario', 'perfil_usuario',
        'unidade_usuario', 'ip', 'user_agent', 'request_id', 'fingerprint',
    )
    ordering = ('-criado_em',)
    list_per_page = 50

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin_site.register(Unidade, UnidadeAdmin)
admin_site.register(JanelaEntrega, JanelaEntregaAdmin)
admin_site.register(Notificacao, NotificacaoAdmin)
admin_site.register(AuditoriaGlobal, AuditoriaGlobalAdmin)
admin_site.register(ErroSistema, ErroSistemaAdmin)
