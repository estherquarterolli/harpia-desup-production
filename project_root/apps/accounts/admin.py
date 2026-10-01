from django.contrib import admin
from unfold.sites import UnfoldAdminSite
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .services import issue_email_password_reset

class HarpiaAdminSite(UnfoldAdminSite):
    site_header = _("Harpia – Administração")
    site_title = _("Harpia")
    index_title = _("Painel de Controle")

    def each_context(self, request):
        context = super().each_context(request)
        from apps.core.context_processors import notificacoes
        context.update(notificacoes(request))
        return context

admin_site = HarpiaAdminSite(name='alloc_admin')

from django.utils.html import mark_safe

class CustomUserAdmin(DjangoUserAdmin, ModelAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    
    list_display = (
        'email', 'perfil', 'unidade', 'last_login', 'is_active',
        'is_staff', 'forcar_troca_senha',
    )
    list_filter = ('perfil', 'unidade', 'is_staff', 'is_active', 'forcar_troca_senha')
    search_fields = ('email',)
    ordering = ('email',)

    actions = ['enviar_redefinicao_email']

    @admin.action(description="Enviar link seguro de redefinição de senha")
    def enviar_redefinicao_email(self, request, queryset):
        """Ação em duas etapas; nenhum reset administrativo ocorre sem confirmação."""
        if not request.user.is_superuser:
            queryset = queryset.exclude(is_superuser=True).exclude(perfil=User.Perfil.ADMIN)

        if request.POST.get('confirmar_envio') == 'sim':
            enviados = 0
            limitados = 0
            for target in queryset:
                result = issue_email_password_reset(
                    user=target,
                    request=request,
                    requested_by=request.user,
                )
                if result.sent:
                    enviados += 1
                elif result.reason == 'rate_limited':
                    limitados += 1
            self.message_user(
                request,
                f'{enviados} link(s) enviado(s). {limitados} usuário(s) já tinham um link recente.',
            )
            return None

        return TemplateResponse(
            request,
            'admin/accounts/user/password_reset_confirmation.html',
            {
                **self.admin_site.each_context(request),
                'title': 'Confirmar envio de redefinição de senha',
                'usuarios': queryset,
                'queryset': queryset,
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
                'opts': self.model._meta,
                'action_name': 'enviar_redefinicao_email',
            },
        )

    # Campos exibidos na edição do usuário
    fieldsets = (
        (None, {'fields': ('email',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'perfil', 'unidade', 'forcar_troca_senha')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'perfil', 'unidade', 'forcar_troca_senha'),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """
        Garante que apenas superusuários possam alterar o status de is_superuser.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            if 'is_superuser' not in readonly_fields:
                readonly_fields.append('is_superuser')
        return readonly_fields

class CustomGroupAdmin(DjangoGroupAdmin, ModelAdmin):
    pass

admin_site.register(User, CustomUserAdmin)
admin_site.register(Group, CustomGroupAdmin)



