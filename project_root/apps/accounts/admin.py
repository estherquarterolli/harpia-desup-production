from django.contrib import admin
from unfold.sites import UnfoldAdminSite
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.models import Group
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from unfold.contrib.filters.admin import DropdownFilter
from .models import DEFAULT_USER_PASSWORD, User
from .forms import CustomUserCreationForm, CustomUserChangeForm


def usuarios_por_situacao(queryset, situacao):
    """Regra única das "situações de acesso", usada no filtro da lista e no alerta da home."""
    if situacao == 'nunca_acessou':
        return queryset.filter(is_active=True, last_login__isnull=True)
    if situacao == 'senha_temporaria':
        return queryset.filter(is_active=True, forcar_troca_senha=True)
    if situacao == 'inativo':
        return queryset.filter(is_active=False)
    if situacao == 'sem_unidade':
        return queryset.filter(
            is_active=True, perfil=User.Perfil.COORDENADOR_UNIDADE, unidade__isnull=True,
        )
    return queryset


class SituacaoUsuarioFilter(DropdownFilter):
    title = 'Situação de acesso'
    parameter_name = 'situacao'

    def lookups(self, request, model_admin):
        return [
            ['nunca_acessou', 'Nunca acessou o sistema'],
            ['senha_temporaria', 'Ainda com a senha temporária'],
            ['sem_unidade', 'Coordenador sem unidade'],
            ['inativo', 'Desativados'],
        ]

    def queryset(self, request, queryset):
        return usuarios_por_situacao(queryset, self.value())


class HarpiaAdminSite(UnfoldAdminSite):
    site_header = _("Harpia – Administração")
    site_title = _("Harpia")
    index_title = _("Painel de Controle")

    def index(self, request, extra_context=None):
        if not request.user.is_superuser:
            return super().index(request, extra_context)

        from django.urls import reverse
        from django.utils import timezone

        from apps.core.audit import titulo_da_acao
        from apps.core.models import AuditoriaGlobal, ErroSistema, Unidade
        from apps.professors.models import Professor

        recentes = AuditoriaGlobal.objects.select_related('usuario').order_by('-criado_em', '-pk')[:6]
        atividade_recente = [
            {
                'quando': timezone.localtime(linha.criado_em),
                'titulo': titulo_da_acao(linha.acao),
                'quem': linha.email or (linha.usuario.email if linha.usuario_id else '—'),
                'registro': linha.objeto,
                'url': reverse(f'{self.name}:core_auditoriaglobal_change', args=[linha.pk]),
            }
            for linha in recentes
        ]

        resumo = {
            'precisa_atencao': self._precisa_atencao(),
            'total_usuarios': User.objects.count(),
            'total_unidades': Unidade.objects.filter(status=True).count(),
            'total_professores': Professor.objects.filter(status='Ativo').count(),
            'total_erros': ErroSistema.objects.count(),
            'unidades_visualizacao': Unidade.objects.filter(status=True).order_by('nome'),
            'atividade_recente': atividade_recente,
        }
        return super().index(request, {**resumo, **(extra_context or {})})

    def _precisa_atencao(self, agora=None):
        """Pendências que o superusuário deveria olhar, cada uma com link para a lista já filtrada."""
        from datetime import timedelta

        from apps.core.models import ErroSistema, JanelaEntrega, Unidade

        agora = agora or timezone.now()
        usuarios = User.objects.all()
        itens = [
            (
                'atencao', ErroSistema.objects.filter(criado_em__gte=agora - timedelta(hours=24)).count(),
                'Erros nas últimas 24 horas',
                'Falhas registradas pelo sistema que podem ter atrapalhado alguém.',
                'core_errosistema_changelist', 'periodo=24h',
            ),
            (
                'atencao', Unidade.objects.filter(status=True, usuarios__isnull=True).count(),
                'Unidades ativas sem nenhum usuário',
                'Ninguém consegue entrar para preencher os dados dessas unidades.',
                'core_unidade_changelist', 'acesso=sem_usuario',
            ),
            (
                'atencao', usuarios_por_situacao(usuarios, 'sem_unidade').count(),
                'Coordenadores sem unidade',
                'Usuários de unidade sem unidade vinculada não enxergam dados.',
                'accounts_user_changelist', 'situacao=sem_unidade',
            ),
            (
                'info', usuarios_por_situacao(usuarios, 'nunca_acessou').count(),
                'Usuários que nunca acessaram',
                'Contas ativas que ainda não fizeram o primeiro acesso.',
                'accounts_user_changelist', 'situacao=nunca_acessou',
            ),
            (
                'info', usuarios_por_situacao(usuarios, 'senha_temporaria').count(),
                'Usuários com senha temporária',
                'Ainda não trocaram a senha padrão.',
                'accounts_user_changelist', 'situacao=senha_temporaria',
            ),
            (
                'info', JanelaEntrega.objects.filter(
                    status__in=[JanelaEntrega.StatusChoices.ABERTO, JanelaEntrega.StatusChoices.REABERTO],
                ).count(),
                'Prazos de entrega abertos',
                'Janelas em que as unidades ainda podem enviar a matriz.',
                'core_janelaentrega_changelist', 'prazo=abertas',
            ),
        ]
        return [
            {
                'gravidade': gravidade, 'quantidade': quantidade, 'titulo': titulo, 'texto': texto,
                'url': f"{reverse(f'{self.name}:{rota}')}?{consulta}",
            }
            for gravidade, quantidade, titulo, texto, rota, consulta in itens
            if quantidade
        ]

    def each_context(self, request):
        context = super().each_context(request)
        from apps.core.context_processors import notificacoes
        context.update(notificacoes(request))
        return context

admin_site = HarpiaAdminSite(name='alloc_admin')

from django.utils.html import mark_safe


class HarpiaModelAdmin(ModelAdmin):
    """Configuração leve compartilhada pelas listagens do superadmin."""

    list_per_page = 25
    show_full_result_count = False


def _selos_situacao(usuario):
    """Selos coloridos com a situação de acesso (sem depender só da cor: sempre há texto)."""
    if not usuario.is_active:
        selos = [('exclusao', 'Desativado')]
    else:
        selos = []
        if usuario.last_login is None:
            selos.append(('outro', 'Nunca acessou'))
        if usuario.forcar_troca_senha:
            selos.append(('seguranca', 'Senha temporária'))
        if not selos:
            selos.append(('criacao', 'Ativo'))
    return format_html_join(
        ' ', '<span class="sa-badge sa-badge--{}">{}</span>', selos,
    )


class CustomUserAdmin(DjangoUserAdmin, ModelAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    
    list_display = ('email', 'perfil', 'unidade', 'situacao', 'ultimo_acesso')
    list_select_related = ('unidade',)
    list_filter = (
        SituacaoUsuarioFilter, 'perfil', 'unidade', 'is_staff', 'is_active', 'forcar_troca_senha',
    )
    search_fields = ('email',)
    ordering = ('email',)
    readonly_fields = ('painel_atividade',)

    actions = ['forcar_reset_senha', 'ativar_usuarios', 'desativar_usuarios']
    list_per_page = 25
    show_full_result_count = False

    # ---- colunas da lista -------------------------------------------------

    @admin.display(description='Situação')
    def situacao(self, obj):
        return _selos_situacao(obj)

    @admin.display(description='Último acesso', ordering='last_login')
    def ultimo_acesso(self, obj):
        if not obj.last_login:
            return mark_safe('<span class="sa-muted">Nunca acessou</span>')
        return format_html(
            '<span class="sa-nowrap">{}</span>',
            timezone.localtime(obj.last_login).strftime('%d/%m/%Y %H:%M'),
        )

    # ---- painel de atividade (página do usuário) ---------------------------

    @admin.display(description='Atividade deste usuário')
    def painel_atividade(self, obj):
        if obj is None or not obj.pk:
            return '—'
        from apps.core.audit import titulo_da_acao
        from apps.core.models import AuditoriaGlobal

        linhas = list(
            AuditoriaGlobal.objects.filter(email__iexact=obj.email).order_by('-criado_em', '-pk')[:8]
        )
        resumo = format_html(
            '<dl class="sa-kv">{}</dl>',
            format_html_join(
                '', '<div class="sa-kv__item"><dt>{}</dt><dd>{}</dd></div>',
                (
                    ('Situação', _selos_situacao(obj)),
                    ('Último acesso', self.ultimo_acesso(obj)),
                    ('Cadastrado em', timezone.localtime(obj.date_joined).strftime('%d/%m/%Y %H:%M')),
                ),
            ),
        )
        if not linhas:
            return format_html('{}<p class="sa-muted">Nenhuma ação registrada na auditoria por este e-mail.</p>', resumo)

        tabela = format_html(
            '<div class="sa-table-wrap"><table class="sa-table"><thead><tr>'
            '<th>Quando</th><th>O que fez</th><th>Registro</th></tr></thead><tbody>{}</tbody></table></div>',
            format_html_join(
                '', '<tr><td class="sa-nowrap">{}</td><td><a href="{}">{}</a></td><td>{}</td></tr>',
                (
                    (
                        timezone.localtime(linha.criado_em).strftime('%d/%m/%Y %H:%M'),
                        reverse(f'{self.admin_site.name}:core_auditoriaglobal_change', args=[linha.pk]),
                        titulo_da_acao(linha.acao),
                        linha.objeto or '—',
                    )
                    for linha in linhas
                ),
            ),
        )
        link = reverse(f'{self.admin_site.name}:core_auditoriaglobal_changelist')
        return format_html(
            '{}{}<p><a href="{}?quem_contem={}">Ver tudo o que este usuário fez na auditoria →</a></p>',
            resumo, tabela, link, obj.email,
        )

    # ---- ações ------------------------------------------------------------

    @admin.action(description='Ativar usuários selecionados')
    def ativar_usuarios(self, request, queryset):
        return self._alterar_ativo(request, queryset, True)

    @admin.action(description='Desativar usuários selecionados (não conseguem mais entrar)')
    def desativar_usuarios(self, request, queryset):
        return self._alterar_ativo(request, queryset, False)

    def _alterar_ativo(self, request, queryset, ativo):
        if not request.user.is_superuser:
            self.message_user(request, 'Apenas superusuários podem ativar ou desativar contas.', level=messages.ERROR)
            return None
        alvo = queryset.exclude(pk=request.user.pk).filter(is_active=not ativo)
        total = 0
        emails = []
        # `save()` (e não `update()`) para que a auditoria registre quem mudou e o antes → depois.
        for usuario in alvo:
            usuario.is_active = ativo
            usuario.save(update_fields=['is_active'])
            emails.append(usuario.email)
            total += 1
        ignorados = queryset.count() - total
        if total:
            from apps.core.audit import registrar
            from apps.core.models import AuditoriaGlobal

            # Um único evento diz o que foi feito; o antes → depois de cada conta vai junto.
            registrar(
                request, 'USUARIO_ATIVADO' if ativo else 'USUARIO_DESATIVADO',
                f'{total} conta(s) {"ativada(s)" if ativo else "desativada(s)"} pela lista de usuários: '
                + ', '.join(emails) + '.',
                categoria=AuditoriaGlobal.Categoria.ALTERACAO, entidade='Usuário',
                objeto=emails[0] if total == 1 else f'{total} usuários',
            )
        verbo = 'ativado(s)' if ativo else 'desativado(s)'
        self.message_user(request, f'{total} usuário(s) {verbo}.')
        if ignorados:
            self.message_user(
                request,
                f'{ignorados} ignorado(s): já estavam nessa situação ou é a sua própria conta.',
                level=messages.WARNING,
            )
        return None

    @admin.action(description="Redefinir senha (senha padrão + troca obrigatória)")
    def forcar_reset_senha(self, request, queryset):
        """Define a senha padrão e exige troca no próximo login. Só superusuário."""
        from .views import registrar_auditoria

        if not request.user.is_superuser:
            self.message_user(
                request, 'Apenas superusuários podem forçar o reset de senha.', level=messages.ERROR,
            )
            return None
        queryset = queryset.exclude(pk=request.user.pk)

        if request.POST.get('confirmar_envio') == 'sim':
            total = 0
            for target in queryset:
                target.set_password(DEFAULT_USER_PASSWORD)
                target.forcar_troca_senha = True
                target.save(update_fields=['password', 'forcar_troca_senha'])
                registrar_auditoria(
                    request,
                    'ADMIN_FORCE_PASSWORD_RESET',
                    usuario=request.user,
                    email=request.user.email,
                    detalhes=f'Senha de {target.email} redefinida para o padrão com troca obrigatória.',
                    entidade='Senha de usuário', objeto=target.email, objeto_id=str(target.pk),
                )
                total += 1
            self.message_user(
                request,
                f'{total} senha(s) redefinida(s). Senha temporária: {DEFAULT_USER_PASSWORD} '
                '(diferencia maiúsculas e minúsculas). Troca obrigatória no próximo acesso.',
            )
            return None

        return TemplateResponse(
            request,
            'admin/accounts/user/password_force_reset_confirmation.html',
            {
                **self.admin_site.each_context(request),
                'title': 'Confirmar reset forçado de senha',
                'usuarios': queryset,
                'queryset': queryset,
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
                'opts': self.model._meta,
                'action_name': 'forcar_reset_senha',
            },
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            for nome in ('forcar_reset_senha', 'ativar_usuarios', 'desativar_usuarios'):
                actions.pop(nome, None)
        return actions

    # Campos exibidos na edição do usuário
    fieldsets = (
        (None, {'fields': ('email',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'perfil', 'unidade', 'forcar_troca_senha')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
        ('Atividade recente', {'fields': ('painel_atividade',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'perfil', 'unidade', 'forcar_troca_senha'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            # O painel de atividade lê a auditoria, que é exclusiva do superusuário.
            fieldsets = tuple(par for par in fieldsets if par[0] != 'Atividade recente')
        return fieldsets

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
    list_per_page = 25
    show_full_result_count = False

admin_site.register(User, CustomUserAdmin)
admin_site.register(Group, CustomGroupAdmin)



