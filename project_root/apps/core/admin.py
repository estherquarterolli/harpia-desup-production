from django.contrib import admin
from apps.accounts.admin import HarpiaModelAdmin, admin_site
from .models import (
    AtividadeEstagioSupervisao,
    AuditoriaGlobal,
    ErroSistema,
    ExcecaoCargaUnidade,
    JanelaEntrega,
    LimiteCargaUnidade,
    Notificacao,
    OcupacaoEquipeDiretiva,
    ReadaptacaoProfessor,
    SolicitacaoProfessorExterno,
    TipoCargoDiretivo,
    Unidade,
)
from .forms import JanelaEntregaForm

class UnidadeAdmin(HarpiaModelAdmin):
    list_display = ('nome', 'sigla', 'status')
    search_fields = ('nome', 'sigla')
    list_filter = ('status',)

class JanelaEntregaAdmin(HarpiaModelAdmin):
    form = JanelaEntregaForm
    list_display = ('semestre', 'data_inicio', 'data_fim', 'status', 'unidade')
    list_filter = ('status', 'semestre', 'unidade')
    search_fields = ('semestre',)

class NotificacaoAdmin(HarpiaModelAdmin):
    list_display = ('titulo', 'destinatario', 'unidade_destino', 'lida', 'data_criacao')
    list_filter = ('lida', 'unidade_destino', 'data_criacao')
    search_fields = ('titulo', 'mensagem')
    ordering = ('-data_criacao',)

class AuditoriaGlobalAdmin(HarpiaModelAdmin):
    list_display = ('criado_em', 'acao', 'email', 'usuario', 'ip')
    list_filter = ('acao', 'criado_em')
    search_fields = ('email', 'acao', 'detalhes', 'ip')
    readonly_fields = ('usuario', 'email', 'acao', 'detalhes', 'ip', 'user_agent', 'criado_em')
    ordering = ('-criado_em',)


class ErroSistemaAdmin(HarpiaModelAdmin):
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


class TipoCargoDiretivoAdmin(HarpiaModelAdmin):
    list_display = ('nome', 'codigo', 'exige_curso', 'permite_multiplos', 'ativo', 'ordem')
    list_filter = ('ativo', 'exige_curso', 'permite_multiplos')
    search_fields = ('nome', 'codigo')
    readonly_fields = ('codigo', 'criado_em', 'atualizado_em')


class OcupacaoEquipeDiretivaAdmin(HarpiaModelAdmin):
    list_display = ('unidade', 'cargo', 'professor', 'curso', 'data_inicio', 'data_fim', 'carga_reducao_horas')
    list_filter = ('unidade', 'cargo', 'data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'unidade__nome', 'cargo__nome')
    readonly_fields = ('criado_em', 'atualizado_em')

    def save_model(self, request, obj, form, change):
        if 'carga_reducao_horas' in form.changed_data:
            obj.reducao_personalizada = True
        super().save_model(request, obj, form, change)


class AtividadeEstagioSupervisaoAdmin(HarpiaModelAdmin):
    list_display = (
        'unidade', 'tipo', 'professor', 'curso', 'semestre',
        'num_estudantes', 'carga_horaria_semanal', 'carga_reducao_horas', 'data_inicio', 'data_fim',
    )
    list_filter = ('unidade', 'tipo', 'semestre', 'data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'unidade__nome', 'observacoes')
    readonly_fields = ('criado_em', 'atualizado_em')


class SolicitacaoProfessorExternoAdmin(HarpiaModelAdmin):
    list_display = ('professor', 'unidade_origem', 'unidade_solicitante', 'semestre', 'status', 'criado_em')
    list_filter = ('status', 'semestre', 'unidade_origem', 'unidade_solicitante')
    search_fields = ('professor__rh_nome', 'justificativa', 'motivo_decisao')
    readonly_fields = ('criado_em', 'decidido_em')


class LimiteCargaUnidadeAdmin(HarpiaModelAdmin):
    list_display = ('unidade', 'limite_horas_semanais', 'data_inicio', 'data_fim')
    list_filter = ('unidade', 'data_inicio', 'data_fim')
    readonly_fields = ('criado_em', 'atualizado_em')


class ExcecaoCargaUnidadeAdmin(HarpiaModelAdmin):
    list_display = ('unidade', 'professor', 'horas_adicionais', 'data_inicio', 'data_fim', 'status')
    list_filter = ('status', 'unidade', 'data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'justificativa', 'motivo_decisao')
    readonly_fields = ('criado_em', 'decidido_em')


class ReadaptacaoProfessorAdmin(HarpiaModelAdmin):
    list_display = ('professor', 'data_inicio', 'data_fim', 'criado_por')
    list_filter = ('data_inicio', 'data_fim')
    search_fields = ('professor__rh_nome', 'professor__id_funcional')
    readonly_fields = ('criado_em', 'atualizado_em')

admin_site.register(Unidade, UnidadeAdmin)
admin_site.register(JanelaEntrega, JanelaEntregaAdmin)
admin_site.register(Notificacao, NotificacaoAdmin)
admin_site.register(AuditoriaGlobal, AuditoriaGlobalAdmin)
admin_site.register(ErroSistema, ErroSistemaAdmin)
admin_site.register(TipoCargoDiretivo, TipoCargoDiretivoAdmin)
admin_site.register(OcupacaoEquipeDiretiva, OcupacaoEquipeDiretivaAdmin)
admin_site.register(AtividadeEstagioSupervisao, AtividadeEstagioSupervisaoAdmin)
admin_site.register(SolicitacaoProfessorExterno, SolicitacaoProfessorExternoAdmin)
admin_site.register(LimiteCargaUnidade, LimiteCargaUnidadeAdmin)
admin_site.register(ExcecaoCargaUnidade, ExcecaoCargaUnidadeAdmin)
admin_site.register(ReadaptacaoProfessor, ReadaptacaoProfessorAdmin)
