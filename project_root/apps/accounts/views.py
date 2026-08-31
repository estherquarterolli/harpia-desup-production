from django.shortcuts import render, redirect, get_object_or_404
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
from django.contrib.auth.forms import SetPasswordForm
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
    form_class = SetPasswordForm

    def get_success_url(self):
        return str(reverse_lazy('login')) + '?changed=1'

    def get(self, request, *args, **kwargs):
        if not request.user.forcar_troca_senha:
            # CORR-018: tela de confirmação SEM campo de e-mail — o endereço já é
            # conhecido (`request.user.email`) e é para ele que o link é enviado.
            return render(
                request,
                'registration/password_change_email_prompt.html',
                {'user_email': request.user.email},
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.user.forcar_troca_senha:
            return self._request_email_confirmation(request)
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
        self.request.user.save()
        registrar_auditoria(
            self.request,
            "PASSWORD_CHANGED_FIRST_LOGIN",
            usuario=self.request.user,
            email=self.request.user.email,
            detalhes="Senha alterada no fluxo obrigatorio do primeiro acesso.",
        )
        logger.info(
            "Senha alterada pelo usuario autenticado.",
            extra={
                "user_id": self.request.user.pk,
                "user_email": self.request.user.email,
                "path": self.request.path,
            },
        )
        from django.contrib.auth import logout
        logout(self.request)
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
from django.utils.decorators import method_decorator
from .models import User, PasswordResetRequest, DEFAULT_USER_PASSWORD

def is_coordinator_or_desup(user):
    return user.is_authenticated and (user.is_superuser or user.perfil in ['DESUP', 'COORDENADOR_UNIDADE'])

class ForgotPasswordView(View):
    def get(self, request):
        return render(request, 'registration/forgot_password.html')

    def post(self, request):
        email = request.POST.get('email')

        # Buscar usuário pelo e-mail informado
        user = User.objects.filter(email=email).first()
        if user:
            # SEC-004: já existe pedido em aberto para esta conta → não cria outro,
            # não notifica de novo e não dispara e-mail. A resposta é a MESMA do
            # caminho de sucesso: avisar "você já pediu" diria a um terceiro que a
            # conta existe e que há um reset pendente.
            if PasswordResetRequest.pedido_pendente(user) is not None:
                logger.info(
                    "Pedido de reset ignorado por cooldown.",
                    extra={"user_id": user.pk, "user_email": user.email},
                )
                return render(request, 'registration/forgot_password.html', {
                    'success': (
                        "Sua solicitação foi enviada para o administrador do DESUP e para a "
                        "coordenação acadêmica da sua unidade. Por favor, aguarde o reset."
                    ),
                })

            # Criar a solicitação de reset no banco
            reset_request = PasswordResetRequest.objects.create(user=user)
            
            # Notificar os usuários do DESUP e superusuários
            destinatarios_qs = User.objects.filter(perfil='DESUP') | User.objects.filter(is_superuser=True)
            
            # Acrescentar a coordenação acadêmica da unidade do usuário, se houver.
            # SEC-002: só quando o solicitante É um coordenador de unidade — a
            # notificação carrega o token de aprovação no `url_acao`, e coordenador
            # não aprova reset de conta administrativa. Antes, um pedido de reset
            # do DESUP entregava o token a todos os coordenadores da unidade dele.
            if user.unidade and user.perfil == User.Perfil.COORDENADOR_UNIDADE:
                coordenadores_unidade = User.objects.filter(
                    perfil=User.Perfil.COORDENADOR_UNIDADE,
                    unidade=user.unidade,
                )
                destinatarios_qs = destinatarios_qs | coordenadores_unidade
            
            # Lista de emails para envio (evitando duplicados e nulos)
            email_recipients = list(destinatarios_qs.exclude(email='').exclude(email__isnull=True).values_list('email', flat=True).distinct())
            
            titulo = "Solicitação de Reset de Senha"
            mensagem = f"O usuário {user.get_full_name() or user.email} ({user.email}) solicitou a redefinição de senha."
            url_admin = f"{request.build_absolute_uri('/')[:-1]}/admin/accounts/user/{user.id}/change/"
            from django.urls import reverse
            url_aprovacao_interna = reverse('approve_password_reset', kwargs={'token': reset_request.token})
            url_aprovacao_absoluta = request.build_absolute_uri(url_aprovacao_interna)
            
            # Enviar notificações no sistema para todos os destinatários únicos identificados
            for destinatario in destinatarios_qs.distinct():
                Notificacao.objects.create(
                    destinatario=destinatario,
                    titulo=titulo,
                    mensagem=mensagem,
                    url_acao=url_aprovacao_interna
                )
            
            # Envio de E-mail
            if email_recipients:
                email_body = f"{mensagem}\n\nPara APROVAR este reset, acesse o link de aprovação: {url_aprovacao_absoluta}\n\nOu acesse o painel administrativo: {url_admin}"
                def _queue_reset_email():
                    try:
                        send_email_task.delay(
                            subject=f"HARPIA - {titulo}",
                            message=email_body,
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                            recipient_list=email_recipients,
                            fail_silently=True,
                        )
                    except Exception:
                        pass  # Falha de fila não deve bloquear o fluxo do usuário

                transaction.on_commit(_queue_reset_email)
            
            msg = "Sua solicitação foi enviada para o administrador do DESUP e para a coordenação acadêmica da sua unidade. Por favor, aguarde o reset."
            return render(request, 'registration/forgot_password.html', {'success': msg})
        else:
            msg = "Não foi encontrado nenhum usuário com o e-mail informado."
            return render(request, 'registration/forgot_password.html', {'error': msg})


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

