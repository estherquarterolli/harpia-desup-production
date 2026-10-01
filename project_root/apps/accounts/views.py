from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.http import HttpResponse
from django.core.cache import cache
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.conf import settings
from django.db import transaction
import logging

_cache_logger = logging.getLogger(__name__)


def _cache_get(key, default=None):
    """cache.get resiliente: se o backend de cache estiver fora, retorna o default."""
    try:
        return cache.get(key, default)
    except Exception:
        _cache_logger.warning("Cache indisponivel em get(%s); usando default.", key, exc_info=True)
        return default


def _cache_set(key, value, timeout=None):
    """cache.set resiliente: falha de cache nao interrompe o fluxo."""
    try:
        cache.set(key, value, timeout)
    except Exception:
        _cache_logger.warning("Cache indisponivel em set(%s).", key, exc_info=True)


def _cache_delete(key):
    """cache.delete resiliente."""
    try:
        cache.delete(key)
    except Exception:
        _cache_logger.warning("Cache indisponivel em delete(%s).", key, exc_info=True)


def get_redirect_url_for_user(user):
    """
    Retorna a URL de redirecionamento com base no perfil do usuário.
    """
    # CORR-021: ADMIN (TI DESUP) pode existir sem ser superusuário.
    if user.is_superuser or user.perfil == 'ADMIN':
        return '/admin/'
    return get_dashboard_url_for_user(user)


def get_dashboard_url_for_user(user):
    """
    Retorna a URL do dashboard operacional com base no perfil do usuário.
    """
    # CORR-019: o superuser (DEV/ADMIN) NÃO é operador DESUP. Antes esta função
    # devolvia '/dashboard/desup/' para ele; como a raiz '/' e o
    # LOGIN_REDIRECT_URL='dashboard' passam por aqui, qualquer redirect a
    # '/'/'dashboard' (inclusive quando o /admin/ exige re-login e não há `next`
    # válido) jogava o admin no dashboard da DESUP. Agora ele fica no admin Django.
    # CORR-021: idem para o perfil ADMIN (TI DESUP), que não é perfil operacional.
    if user.is_superuser or user.perfil == 'ADMIN':
        return '/admin/'
    if user.perfil == 'DESUP' or user.groups.filter(name='Admin DESUP').exists():
        return '/dashboard/desup/'
    elif user.perfil == 'COORDENADOR_UNIDADE' or user.groups.filter(name='Gestor Unidade').exists():
        return '/dashboard/unidade/'
    return '/dashboard/'


@never_cache
@ensure_csrf_cookie
def login_view(request):
    if request.method == "GET":
        return render(request, 'registration/login.html')

    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Regra #10: Bloqueio após 5 tentativas
        cache_key = f"login_failed_attempts_{email}"
        attempts = _cache_get(cache_key, 0)
        max_attempts = 5
        
        if attempts >= max_attempts:
            msg = "Conta bloqueada temporariamente por excesso de tentativas. Tente novamente em 15 minutos."
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="p-3 bg-red-50 border border-red-200 rounded-md">'
                    f'<p class="text-xs text-red-600 font-semibold text-center">{msg}</p>'
                    '</div>'
                )
            return render(request, 'registration/login.html', {'error': msg})

        # Agora o authenticate funciona com o email como username
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            _cache_delete(cache_key) # Limpa tentativas ao logar

            redirect_url = get_redirect_url_for_user(user)
            if request.headers.get('HX-Request'):
                response = HttpResponse()
                response['HX-Redirect'] = redirect_url
                return response
            return redirect(redirect_url)
        else:
            # Incrementa tentativas falhas
            new_attempts = attempts + 1
            _cache_set(cache_key, new_attempts, 900) # Expira em 15 min (900s)
            
            remaining = max_attempts - new_attempts
            warning_msg = ""
            if remaining > 0:
                warning_msg = f'<div class="p-3 bg-amber-50 border border-amber-200 rounded-md mt-2">' \
                             f'<p class="text-[10px] text-amber-700 font-bold text-center">' \
                             f'<i class="ph ph-warning-circle mr-1"></i> Atenção: Você tem mais {remaining} tentativa{"s" if remaining > 1 else ""} antes do bloqueio temporário.</p>' \
                             f'</div>'
            
            # Se for HTMX, retorna apenas o alerta para o div #form-errors
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    '<div class="p-3 bg-red-50 border border-red-200 rounded-md">'
                    '<p class="text-xs text-red-600 font-semibold text-center">E-mail ou senha inválidos.</p>'
                    '</div>' + warning_msg
                )
            
            return render(request, 'registration/login.html', {
                'error': 'E-mail ou senha inválidos.',
                'warning': f'Atenção: Você tem mais {remaining} tentativa{"s" if remaining > 1 else ""} antes do bloqueio temporário.' if remaining > 0 else ''
            })


from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.urls import reverse, reverse_lazy
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
import logging
from apps.core.models import AuditoriaGlobal, Notificacao
from apps.core.tasks import send_email_task
from .models import User

logger = logging.getLogger(__name__)


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def registrar_auditoria(request, acao, usuario=None, email="", detalhes=""):
    AuditoriaGlobal.objects.create(
        usuario=usuario if getattr(usuario, "is_authenticated", False) else usuario,
        email=email or getattr(usuario, "email", ""),
        acao=acao,
        detalhes=detalhes,
        ip=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


class ProfileView(LoginRequiredMixin, View):
    """
    CORR-017 — página "Meu Perfil" (somente leitura).

    Antes o item "Meu Perfil" do menu de usuário apontava direto para a troca de
    senha (`password_change`) e não existia nenhuma tela de perfil. Aqui o usuário
    vê e-mail, tipo de perfil e unidade; a troca de senha virou um item separado.
    """

    template_name = 'accounts/profile.html'

    def get(self, request, *args, **kwargs):
        user = request.user
        # CORR-021: os três perfis são oficiais, então `get_perfil_display()` sempre
        # devolve um rótulo legível (antes 'ADMIN' era valor legado fora de
        # Perfil.choices e saía cru).
        return render(request, self.template_name, {
            'perfil_label': user.get_perfil_display(),
            # A unidade só faz sentido para o perfil de unidade.
            'mostra_unidade': user.perfil == User.Perfil.COORDENADOR_UNIDADE,
        })


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'registration/password_change_form.html'
    form_class = PasswordChangeForm

    def get_success_url(self):
        return str(reverse_lazy('profile'))

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def _request_email_confirmation(self, request):
        # CORR-018: usa sempre o e-mail do usuário autenticado. Antes o fluxo lia
        # `request.POST["email"]` e exigia que fosse idêntico ao do login — passo
        # redundante (o e-mail já está na sessão) e que parecia uma brecha.
        from .models import SelfPasswordChangeRequest

        # CORR-020: rate-limit de 1 pedido por dia. Sem ele, qualquer sessão aberta
        # podia disparar e-mails sem limite. Em DEBUG o bloqueio não se aplica, para
        # não atrapalhar o desenvolvimento.
        #
        # A checagem e a criação do token ficam na MESMA transação, com a linha do
        # usuário travada: sem o lock, um duplo clique no botão dispara dois POSTs
        # que passariam os dois pela checagem e gerariam dois links. Em SQLite o
        # `select_for_update` é inócuo; em PostgreSQL (produção) ele serializa.
        with transaction.atomic():
            User.objects.select_for_update().filter(pk=request.user.pk).first()

            if not settings.DEBUG:
                recente = SelfPasswordChangeRequest.pedido_recente(request.user)
                if recente is not None:
                    registrar_auditoria(
                        request,
                        "PASSWORD_CHANGE_RATE_LIMITED",
                        usuario=request.user,
                        email=request.user.email,
                        detalhes="Novo pedido bloqueado: limite de 1 link de troca de senha por dia.",
                    )
                    liberado = timezone.localtime(recente.liberado_em)
                    return render(
                        request,
                        'registration/password_change_email_prompt.html',
                        {
                            'user_email': request.user.email,
                            'error': (
                                'Você já solicitou uma troca de senha nas últimas 24 horas. '
                                f'Um novo pedido só poderá ser feito a partir de '
                                f'{liberado.strftime("%d/%m/%Y às %H:%M")}. '
                                'Verifique sua caixa de entrada (e o spam) — o link anterior '
                                'vale por 1 hora.'
                            ),
                        },
                    )

            change_request = SelfPasswordChangeRequest.objects.create(
                user=request.user,
                solicitado_ip=get_client_ip(request),
            )
        confirm_url = request.build_absolute_uri(
            reverse('password_change_confirm', kwargs={'token': change_request.token})
        )

        try:
            def _queue_email():
                try:
                    send_email_task.delay(
                        subject="HARPIA - Link para troca de senha",
                        message=(
                            "Foi solicitada uma troca de senha para sua conta no HARPIA.\n\n"
                            f"Acesse o link para definir uma nova senha: {confirm_url}\n\n"
                            "Este link expira em 1 hora. Se voce nao solicitou esta acao, ignore este e-mail."
                        ),
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                        recipient_list=[request.user.email],
                        fail_silently=False,
                    )
                except Exception:
                    logger.exception(
                        "Falha ao enfileirar e-mail de troca de senha",
                        extra={"user_id": request.user.pk, "user_email": request.user.email},
                    )

            transaction.on_commit(_queue_email)
            registrar_auditoria(
                request,
                "PASSWORD_CHANGE_LINK_SENT",
                usuario=request.user,
                email=request.user.email,
                detalhes="Link de troca de senha enviado para o e-mail do usuario.",
            )
            return render(
                request,
                'registration/password_change_email_prompt.html',
                {
                    'user_email': request.user.email,
                    'success': (
                        'Enviamos um link de troca de senha para '
                        f'{request.user.email}.'
                    ),
                },
            )
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail de troca de senha: {e}")
            registrar_auditoria(
                request,
                "PASSWORD_CHANGE_EMAIL_FAILURE",
                usuario=request.user,
                email=request.user.email,
                detalhes=f"Falha tecnica ao enviar e-mail: {str(e)}",
            )
            return render(
                request,
                'registration/password_change_email_prompt.html',
                {
                    'user_email': request.user.email,
                    'error': 'Ocorreu um erro ao enviar o e-mail. Por favor, tente novamente mais tarde.',
                },
            )

    def form_valid(self, form):
        response = super().form_valid(form)
        # Ao alterar a senha com sucesso, desativa a flag de forçar troca
        self.request.user.forcar_troca_senha = False
        self.request.user.save(update_fields=['forcar_troca_senha'])
        registrar_auditoria(
            self.request,
            "PASSWORD_CHANGED_BY_USER",
            usuario=self.request.user,
            email=self.request.user.email,
            detalhes="Senha alterada pelo próprio usuário após confirmação da senha atual.",
        )
        logger.info(
            "Senha alterada pelo usuario autenticado.",
            extra={
                "user_id": self.request.user.pk,
                "user_email": self.request.user.email,
                "path": self.request.path,
            },
        )
        messages.success(self.request, "Senha alterada com sucesso.")
        return response


class PasswordChangeConfirmView(View):
    template_name = 'registration/password_change_form.html'

    def get_change_request(self, token):
        from .models import SelfPasswordChangeRequest

        return get_object_or_404(SelfPasswordChangeRequest, token=token)

    def _is_invalid(self, change_request):
        return change_request.usado or change_request.is_expirado

    def _render_invalid(self, request, change_request):
        registrar_auditoria(
            request,
            "PASSWORD_CHANGE_TOKEN_INVALID",
            usuario=change_request.user,
            email=change_request.user.email,
            detalhes="Tentativa de uso de token de troca de senha usado ou expirado.",
        )
        # CORR-018: `somente_erro` esconde o botão "Enviar link" — aqui o usuário
        # pode nem estar autenticado (o link chega por e-mail), então não há
        # solicitação nova a fazer nesta tela.
        return render(request, 'registration/password_change_email_prompt.html', {
            'error': 'Este link de troca de senha expirou ou ja foi utilizado.',
            'somente_erro': True,
        })

    def get(self, request, token):
        change_request = self.get_change_request(token)
        if self._is_invalid(change_request):
            return self._render_invalid(request, change_request)

        form = SetPasswordForm(change_request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request, token):
        change_request = self.get_change_request(token)
        if self._is_invalid(change_request):
            return self._render_invalid(request, change_request)

        form = SetPasswordForm(change_request.user, request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        form.save()
        change_request.usado = True
        change_request.usado_em = timezone.now()
        change_request.save(update_fields=['usado', 'usado_em'])
        registrar_auditoria(
            request,
            "PASSWORD_CHANGED_BY_EMAIL_TOKEN",
            usuario=change_request.user,
            email=change_request.user.email,
            detalhes="Senha alterada com token enviado por e-mail.",
        )
        return redirect(str(reverse_lazy('login')) + '?changed=1')




from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from .models import (
    EmailPasswordResetToken,
    User,
    PasswordResetRequest,
    DEFAULT_USER_PASSWORD,
)
from .services import issue_email_password_reset, password_reset_token_hash

def is_coordinator_or_desup(user):
    return user.is_authenticated and (user.is_superuser or user.perfil in ['DESUP', 'COORDENADOR_UNIDADE'])

class ForgotPasswordView(View):
    """Recuperação direta por e-mail, sem revelar se a conta existe."""

    def get(self, request):
        return render(request, 'registration/forgot_password.html')

    def post(self, request):
        email = (request.POST.get('email') or '').strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user is not None:
            result = issue_email_password_reset(user=user, request=request)
            registrar_auditoria(
                request,
                "PASSWORD_RESET_EMAIL_REQUESTED",
                usuario=user,
                email=user.email,
                detalhes=(
                    "Link de redefinição enviado ao próprio usuário."
                    if result.sent else
                    f"Pedido não reenviado ({result.reason})."
                ),
            )

        # Resposta deliberadamente idêntica para e-mail existente ou inexistente.
        # Isso impede enumeração de contas pelo endpoint público.
        return render(request, 'registration/forgot_password.html', {
            'success': (
                'Se o e-mail estiver cadastrado e ativo, enviaremos um link individual '
                'para você definir uma nova senha. Verifique também a caixa de spam.'
            ),
        })


class EmailPasswordResetConfirmView(View):
    """Valida o token opaco e permite cadastrar uma nova senha uma única vez."""

    template_name = 'registration/password_reset_confirm_email.html'

    def _token(self, raw_token, *, lock=False):
        queryset = EmailPasswordResetToken.objects.select_related('user')
        if lock:
            queryset = queryset.select_for_update()
        return queryset.filter(token_hash=password_reset_token_hash(raw_token)).first()

    @staticmethod
    def _invalid(token):
        return token is None or not token.valido

    def get(self, request, token):
        reset_token = self._token(token)
        if self._invalid(reset_token):
            return render(request, self.template_name, {'invalid': True})
        return render(request, self.template_name, {
            'form': SetPasswordForm(reset_token.user),
            'email': reset_token.user.email,
        })

    def post(self, request, token):
        with transaction.atomic():
            reset_token = self._token(token, lock=True)
            if self._invalid(reset_token):
                return render(request, self.template_name, {'invalid': True})

            form = SetPasswordForm(reset_token.user, request.POST)
            if not form.is_valid():
                return render(request, self.template_name, {
                    'form': form,
                    'email': reset_token.user.email,
                })

            user = form.save(commit=False)
            user.forcar_troca_senha = False
            user.save(update_fields=['password', 'forcar_troca_senha'])
            now = timezone.now()
            EmailPasswordResetToken.objects.filter(
                user=user,
                usado=False,
            ).update(usado=True, usado_em=now)

        registrar_auditoria(
            request,
            "PASSWORD_RESET_COMPLETED_BY_EMAIL",
            usuario=user,
            email=user.email,
            detalhes="Senha redefinida com token aleatório enviado ao próprio e-mail.",
        )
        return redirect(str(reverse_lazy('login')) + '?changed=1')


class DesupUserListView(LoginRequiredMixin, ListView):
    """Gestão operacional de contas disponível somente para o perfil DESUP."""

    model = User
    template_name = 'accounts/desup_user_list.html'
    context_object_name = 'usuarios'
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.perfil != User.Perfil.DESUP:
            return HttpResponse('Você não tem permissão para gerenciar usuários.', status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = (
            User.objects
            .select_related('unidade')
            .exclude(is_superuser=True)
            .exclude(perfil=User.Perfil.ADMIN)
            .order_by('email')
        )
        query = (self.request.GET.get('q') or '').strip()
        if query:
            queryset = queryset.filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(unidade__nome__icontains=query)
                | Q(unidade__sigla__icontains=query)
            )
        return queryset


class DesupUserCreateView(LoginRequiredMixin, View):
    """Cria conta com senha padrão e troca obrigatória no primeiro acesso."""

    template_name = 'accounts/desup_user_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.perfil != User.Perfil.DESUP:
            return HttpResponse('Você não tem permissão para criar usuários.', status=403)
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _form(data=None):
        from .forms import DesupUserCreateForm
        return DesupUserCreateForm(data=data)

    def get(self, request):
        return render(request, self.template_name, {'form': self._form()})

    def post(self, request):
        form = self._form(request.POST)
        if form.is_valid():
            with transaction.atomic():
                created_user = form.save()
                registrar_auditoria(
                    request,
                    'DESUP_USER_CREATED',
                    usuario=request.user,
                    email=request.user.email,
                    detalhes=(
                        f'Usuário {created_user.email} criado com perfil '
                        f'{created_user.perfil} e unidade '
                        f'{created_user.unidade_id or "não aplicável"}.'
                    ),
                )

            messages.success(request, 'Usuário criado com sucesso.')
            return redirect('desup_user_list')

        return render(request, self.template_name, {'form': form})


class DesupUserPasswordResetView(LoginRequiredMixin, View):
    template_name = 'accounts/desup_user_reset_confirm.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.perfil != User.Perfil.DESUP:
            return HttpResponse('Você não tem permissão para redefinir senhas.', status=403)
        self.target = get_object_or_404(
            User.objects.exclude(is_superuser=True).exclude(perfil=User.Perfil.ADMIN),
            pk=kwargs['pk'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        return render(request, self.template_name, {'target': self.target})

    def post(self, request, pk):
        if request.POST.get('confirmar') != 'sim':
            return render(request, self.template_name, {
                'target': self.target,
                'error': 'Marque a confirmação antes de enviar o link.',
            })

        if request.POST.get('modo') == 'forcar':
            self.target.set_password(DEFAULT_USER_PASSWORD)
            self.target.forcar_troca_senha = True
            self.target.save(update_fields=['password', 'forcar_troca_senha'])
            messages.success(
                request,
                f'Senha de {self.target.email} redefinida para o padrão. '
                'A troca será exigida no próximo acesso.',
            )
            registrar_auditoria(
                request,
                "DESUP_PASSWORD_FORCE_RESET",
                usuario=request.user,
                email=request.user.email,
                detalhes=f"Senha de {self.target.email} redefinida para o padrão com troca obrigatória.",
            )
            return redirect('desup_user_list')

        result = issue_email_password_reset(
            user=self.target,
            request=request,
            requested_by=request.user,
        )
        if result.sent:
            messages.success(
                request,
                f'Link de redefinição enviado para {self.target.email}.',
            )
            registrar_auditoria(
                request,
                "DESUP_PASSWORD_RESET_EMAIL_SENT",
                usuario=request.user,
                email=request.user.email,
                detalhes=f"Link de redefinição enviado para {self.target.email}.",
            )
        elif result.reason == 'rate_limited':
            messages.warning(
                request,
                'Um link já foi emitido recentemente para este usuário. Aguarde antes de reenviar.',
            )
        else:
            messages.error(request, 'Não foi possível enviar o link para esta conta.')
        return redirect('desup_user_list')


def _pode_aprovar_reset(aprovador, solicitante):
    """
    SEC-002 — quem pode aprovar o reset de senha de quem.

    DESUP e superusuário aprovam qualquer um. O coordenador de unidade aprova
    APENAS coordenadores da **própria** unidade, e nunca contas administrativas.

    O guard anterior era `if reset_req.user.unidade != request.user.unidade: 403`.
    Como DESUP, ADMIN e superusuário têm `unidade = None` — e um coordenador
    também pode ter, já que o campo é `null=True` —, a comparação virava
    `None != None`, que é `False`, e a checagem **passava**. Somado ao vazamento
    do token pela notificação (SEC-001), isso dava takeover de superusuário.
    """
    if aprovador.is_superuser or aprovador.perfil == User.Perfil.DESUP:
        return True
    if aprovador.perfil != User.Perfil.COORDENADOR_UNIDADE:
        return False
    # Coordenador só aprova par da mesma unidade — e unidade nula nunca casa.
    if aprovador.unidade_id is None or solicitante.unidade_id != aprovador.unidade_id:
        return False
    # Nunca deixar coordenador resetar conta administrativa (escalonamento).
    if solicitante.is_superuser or solicitante.perfil != User.Perfil.COORDENADOR_UNIDADE:
        return False
    return True


class ApprovePasswordResetView(View):
    """
    Página de aprovação de reset de senha.
    Apenas DESUP, Superusers e Coordenadores da Unidade do solicitante podem acessar.
    """
    @method_decorator(login_required)
    @method_decorator(user_passes_test(is_coordinator_or_desup))
    def get(self, request, token):
        reset_req = get_object_or_404(PasswordResetRequest, token=token)

        if not _pode_aprovar_reset(request.user, reset_req.user):
            return HttpResponse("Você não tem permissão para aprovar este reset.", status=403)

        return render(request, 'registration/approve_reset.html', {'reset_req': reset_req})

    @method_decorator(login_required)
    @method_decorator(user_passes_test(is_coordinator_or_desup))
    def post(self, request, token):
        reset_req = get_object_or_404(PasswordResetRequest, token=token)

        if not _pode_aprovar_reset(request.user, reset_req.user):
            registrar_auditoria(
                request,
                "PASSWORD_RESET_APPROVAL_DENIED",
                usuario=request.user,
                email=request.user.email,
                detalhes=f"Tentativa de aprovar reset de {reset_req.user.email} sem permissão.",
            )
            return HttpResponse("Permissão negada.", status=403)

        if reset_req.finalizado:
            return render(request, 'registration/approve_reset.html', {'reset_req': reset_req, 'error': "Esta solicitação já foi processada."})
        
        if reset_req.is_expirado:
            return render(request, 'registration/approve_reset.html', {'reset_req': reset_req, 'error': "Esta solicitação expirou (mais de 24h)."})

        # Aprovar o reset
        user_to_reset = reset_req.user
        user_to_reset.set_password(DEFAULT_USER_PASSWORD)
        user_to_reset.forcar_troca_senha = True
        user_to_reset.save()

        # Finalizar a requisição
        reset_req.finalizado = True
        reset_req.finalizado_em = timezone.now()
        reset_req.aprovado_por = request.user
        reset_req.save()

        msg_sucesso = f"Senha de {user_to_reset.email} resetada com sucesso para o padrão do sistema."
        return render(request, 'registration/approve_reset.html', {'reset_req': reset_req, 'success': msg_sucesso})

