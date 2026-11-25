"""Política global, preferências pessoais e interfaces de comunicação."""
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views import View

from apps.accounts.models import User
from .audit import registrar
from .models import ConfiguracaoComunicacao, PreferenciaComunicacao, Unidade


def pode_gerenciar_comunicacao(user):
    return user.is_authenticated and (user.is_superuser or user.perfil == User.Perfil.ADMIN)


def pode_receber_comunicacao(user):
    return user.is_authenticated and (user.is_superuser or user.perfil in (User.Perfil.ADMIN, User.Perfil.DESUP))


def unidade_silenciada(unidade_id):
    return bool(unidade_id and ConfiguracaoComunicacao.objects.filter(
        pk=1, unidades_silenciadas__pk=unidade_id,
    ).exists())


def get_desup_recipients(unidade_origem_id=None):
    if unidade_silenciada(unidade_origem_id):
        return []
    preferencias = PreferenciaComunicacao.objects.filter(
        Q(usuario__perfil__in=(User.Perfil.DESUP, User.Perfil.ADMIN)) | Q(usuario__is_superuser=True),
        receber_emails=True, usuario__is_active=True,
    )
    if unidade_origem_id:
        preferencias = preferencias.exclude(unidades_silenciadas__pk=unidade_origem_id)
    adicionais = preferencias.order_by('usuario__email').values_list('usuario__email', flat=True)
    vistos, resultado = set(), []
    for endereco in [settings.HARPIA_NOTIFICATION_EMAIL, *adicionais]:
        endereco = endereco.strip()
        chave = endereco.casefold()
        if endereco and chave not in vistos:
            vistos.add(chave)
            resultado.append(endereco)
    return resultado


class ConfiguracaoComunicacaoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoComunicacao
        fields = ('unidades_silenciadas',)
        widgets = {'unidades_silenciadas': forms.CheckboxSelectMultiple()}


class PreferenciaComunicacaoForm(forms.ModelForm):
    class Meta:
        model = PreferenciaComunicacao
        fields = ('receber_emails', 'unidades_silenciadas')
        widgets = {'unidades_silenciadas': forms.CheckboxSelectMultiple()}


def _estado(config):
    estado = {'Unidades silenciadas': [str(u) for u in config.unidades_silenciadas.order_by('nome')]}
    if isinstance(config, PreferenciaComunicacao):
        estado['Receber notificações por e-mail'] = config.receber_emails
    return estado


def _auditar(request, antes, config, usuario=None):
    depois = _estado(config)
    mudancas = [
        {'campo': campo, 'antes': antes[campo], 'depois': depois[campo]}
        for campo in antes if antes[campo] != depois[campo]
    ]
    if mudancas:
        registrar(
            request, 'COMUNICACAO_PESSOAL_ALTERADA' if usuario else 'COMUNICACAO_GLOBAL_ALTERADA',
            f'Preferências de {usuario.email} atualizadas.' if usuario else 'Silenciamento global atualizado.',
            categoria='ALTERACAO', entidade='Comunicação',
            objeto=usuario.email if usuario else str(config),
            objeto_id=str(usuario.pk if usuario else config.pk),
            mudancas=mudancas, absorver=False,
        )


def _form_pessoal(usuario, data=None):
    config = PreferenciaComunicacao.objects.filter(usuario=usuario).first()
    return PreferenciaComunicacaoForm(data=data, instance=config)


@transaction.atomic
def _salvar_preferencia(request, usuario):
    config, _ = PreferenciaComunicacao.objects.get_or_create(usuario=usuario)
    config = PreferenciaComunicacao.objects.select_for_update().get(pk=config.pk)
    antes = _estado(config)
    form = PreferenciaComunicacaoForm(request.POST, instance=config)
    if not form.is_valid():
        return form, False
    config = form.save()
    _auditar(request, antes, config, usuario)
    return form, True


@transaction.atomic
def _salvar_global(request):
    config, _ = ConfiguracaoComunicacao.objects.get_or_create(pk=1)
    config = ConfiguracaoComunicacao.objects.select_for_update().get(pk=config.pk)
    antes = _estado(config)
    form = ConfiguracaoComunicacaoForm(request.POST, instance=config, prefix='global')
    if not form.is_valid():
        return form, False
    config = form.save()
    _auditar(request, antes, config)
    return form, True


class ConfiguracoesView(LoginRequiredMixin, View):
    def get(self, request):
        return self._render()

    def post(self, request):
        if not pode_receber_comunicacao(request.user):
            raise PermissionDenied('Seu perfil não recebe avisos operacionais da DESUP por e-mail.')
        # O alvo vem exclusivamente da sessão; IDs ou campos globais do POST
        # nunca podem mudar as preferências de outra pessoa ou da instituição.
        form, salvo = _salvar_preferencia(request, request.user)
        if salvo:
            messages.success(request, 'Suas preferências de comunicação foram salvas.')
            return redirect('configuracoes')
        return self._render(form)

    def _render(self, form=None):
        return render(self.request, 'accounts/configuracoes.html', {
            'form': form if form is not None else (
                _form_pessoal(self.request.user) if pode_receber_comunicacao(self.request.user) else None
            ),
            'unidades_globais': Unidade.objects.filter(configuracoes_comunicacao__pk=1),
        })


def comunicacao_admin(request, site, opts):
    if not pode_gerenciar_comunicacao(request.user):
        raise PermissionDenied
    usuarios = User.objects.filter(Q(perfil=User.Perfil.DESUP) | Q(pk=request.user.pk)).order_by('email')
    usuario_id = request.POST.get('usuario') if request.method == 'POST' else request.GET.get('usuario', str(request.user.pk))
    if not str(usuario_id or '').isdecimal():
        raise Http404
    usuario = get_object_or_404(usuarios, pk=usuario_id)
    pessoal = _form_pessoal(usuario)
    global_ = ConfiguracaoComunicacaoForm(
        instance=ConfiguracaoComunicacao.objects.filter(pk=1).first(), prefix='global',
    )
    admin_url = reverse(f'{site.name}:core_configuracaocomunicacao_changelist')
    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'preferencia':
            pessoal, salvo = _salvar_preferencia(request, usuario)
        elif acao == 'global':
            global_, salvo = _salvar_global(request)
        else:
            raise PermissionDenied('Ação de comunicação inválida.')
        if salvo:
            messages.success(request, 'Configuração de comunicação salva.')
            return redirect(f'{admin_url}?usuario={usuario.pk}')
    return TemplateResponse(request, 'admin/core/comunicacao.html', {
        **site.each_context(request), 'title': 'Comunicação', 'opts': opts,
        'usuarios': usuarios, 'usuario_selecionado': usuario, 'form': pessoal,
        'global_form': global_, 'admin_url': admin_url,
        'email_principal': settings.HARPIA_NOTIFICATION_EMAIL,
    })


class ComunicacaoView(LoginRequiredMixin, View):
    """Compatibilidade de navegação; a antiga escrita global foi desativada."""

    def get(self, request):
        if pode_gerenciar_comunicacao(request.user):
            return redirect('alloc_admin:core_configuracaocomunicacao_changelist')
        if pode_receber_comunicacao(request.user):
            return redirect('configuracoes')
        raise PermissionDenied

    def post(self, request):
        raise PermissionDenied('Use as configurações pessoais ou a comunicação no admin.')
