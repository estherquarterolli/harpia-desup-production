from django.contrib import admin
from django.db.models import Q
from django.utils import timezone
from unfold.contrib.filters.admin import ChoicesDropdownFilter, RangeDateTimeFilter, TextFilter

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

class _ContemFilter(TextFilter):
    """Caixa de texto "contém": cada palavra digitada precisa aparecer em algum dos campos.

    Ex.: "maria faeterj" acha todo registro que tenha "maria" E "faeterj" (em qualquer
    ordem, em qualquer maiúscula/minúscula), mesmo no meio de uma frase.
    """

    campos = ()

    def queryset(self, request, queryset):
        valor = (self.value() or '').strip()
        if not valor:
            return queryset
        for termo in valor.split():
            condicao = Q()
            for campo in self.campos:
                condicao |= Q(**{f'{campo}__icontains': termo})
            queryset = queryset.filter(condicao)
        return queryset


class DetalhesContemFilter(_ContemFilter):
    title = 'Detalhes contém'
    parameter_name = 'detalhes_contem'
    campos = ('detalhes',)


class QuemFezContemFilter(_ContemFilter):
    title = 'Quem fez contém (e-mail ou perfil)'
    parameter_name = 'quem_contem'
    campos = ('email', 'perfil_usuario')


class RegistroContemFilter(_ContemFilter):
    title = 'Nome do registro contém (ex.: nome do professor)'
    parameter_name = 'registro_contem'
    campos = ('objeto', 'entidade', 'objeto_id')


class UnidadeContemFilter(_ContemFilter):
    title = 'Unidade contém'
    parameter_name = 'unidade_contem'
    campos = ('unidade_objeto', 'unidade_usuario')


class AcaoContemFilter(_ContemFilter):
    title = 'Código da ação contém'
    parameter_name = 'acao_contem'
    campos = ('acao',)


class AuditoriaGlobalAdmin(HarpiaModelAdmin):
    """Log do sistema: só leitura, com busca "contém" por qualquer parte do texto."""

    list_display = (
        'quando', 'tipo_acao', 'acao', 'quem', 'perfil_usuario', 'entidade',
        'objeto', 'unidade_objeto', 'resumo',
    )
    list_display_links = ('quando', 'acao')
    list_per_page = 50
    list_filter_submit = True
    list_filter = (
        DetalhesContemFilter,
        RegistroContemFilter,
        QuemFezContemFilter,
        UnidadeContemFilter,
        AcaoContemFilter,
        ('categoria', ChoicesDropdownFilter),
        ('criado_em', RangeDateTimeFilter),
    )
    search_fields = (
        'detalhes', 'acao', 'email', 'perfil_usuario', 'unidade_usuario',
        'entidade', 'objeto', 'objeto_id', 'unidade_objeto', 'ip',
    )
    search_help_text = (
        'Busca por qualquer parte do texto (contém), em detalhes, ação, e-mail, '
        'nome do registro, unidade e IP. Várias palavras = todas precisam aparecer.'
    )
    ordering = ('-criado_em',)
    readonly_fields = (
        'criado_em', 'usuario', 'email', 'perfil_usuario', 'unidade_usuario',
        'categoria', 'acao', 'entidade', 'objeto', 'objeto_id', 'unidade_objeto',
        'detalhes', 'ip', 'user_agent',
    )
    fieldsets = (
        ('Quando e quem', {'fields': (
            'criado_em', 'usuario', 'email', 'perfil_usuario', 'unidade_usuario',
        )}),
        ('O que foi feito', {'fields': (
            'categoria', 'acao', 'entidade', 'objeto', 'objeto_id', 'unidade_objeto', 'detalhes',
        )}),
        ('Origem técnica', {'fields': ('ip', 'user_agent'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Data e hora', ordering='criado_em')
    def quando(self, obj):
        return timezone.localtime(obj.criado_em).strftime('%d/%m/%Y %H:%M:%S')

    @admin.display(description='Tipo', ordering='categoria')
    def tipo_acao(self, obj):
        return obj.get_categoria_display()

    @admin.display(description='Quem fez', ordering='email')
    def quem(self, obj):
        return obj.email or (obj.usuario.email if obj.usuario_id else '—')

    @admin.display(description='Resumo')
    def resumo(self, obj):
        texto = ' '.join((obj.detalhes or '').split())
        return texto if len(texto) <= 140 else texto[:139].rstrip() + '…'

    # O log é prova de auditoria: ninguém cria, edita ou apaga linhas pelo painel.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
    readonly_fields = ('codigo', 'permite_multiplos', 'criado_em', 'atualizado_em')


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
