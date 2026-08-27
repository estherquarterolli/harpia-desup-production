from django.contrib import admin
from unfold.admin import ModelAdmin
from apps.accounts.admin import admin_site
from .models import Unidade, JanelaEntrega, Notificacao, AuditoriaGlobal
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

admin_site.register(Unidade, UnidadeAdmin)
admin_site.register(JanelaEntrega, JanelaEntregaAdmin)
admin_site.register(Notificacao, NotificacaoAdmin)
admin_site.register(AuditoriaGlobal, AuditoriaGlobalAdmin)
