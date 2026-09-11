from django.contrib import admin
from unfold.sites import UnfoldAdminSite
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

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
    
    list_display = ('email', 'perfil', 'unidade', 'is_staff', 'forcar_troca_senha')
    list_filter = ('perfil', 'unidade', 'is_staff', 'is_active', 'forcar_troca_senha')
    search_fields = ('email',)
    ordering = ('email',)

    actions = ['resetar_senha_usuarios', 'ativar_senha_padrao']

    @admin.action(description="Resetar senha dos usuários selecionados para a senha padrão e forçar troca")
    def resetar_senha_usuarios(self, request, queryset):
        self._aplicar_senha_padrao(request, queryset, "resetada")

    @admin.action(description="Ativar senha padrão para os usuários selecionados")
    def ativar_senha_padrao(self, request, queryset):
        self._aplicar_senha_padrao(request, queryset, "ativada")

    def _aplicar_senha_padrao(self, request, queryset, operacao):
        from .models import DEFAULT_USER_PASSWORD
        for user in queryset:
            user.set_password(DEFAULT_USER_PASSWORD)
            user.forcar_troca_senha = True
            user.save()
        self.message_user(
            request,
            f"Senha padrão {operacao} e troca de senha forçada para {queryset.count()} usuários.",
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



