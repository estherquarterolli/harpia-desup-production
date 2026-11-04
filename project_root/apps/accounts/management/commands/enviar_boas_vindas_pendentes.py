from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from apps.accounts.models import DEFAULT_USER_PASSWORD, User
from apps.accounts.signals import montar_email_novo_usuario, url_login


class Command(BaseCommand):
    help = (
        "Envia o e-mail de boas-vindas (link de login + senha de primeiro acesso) "
        "a todos os usuários ativos que ainda não fizeram o primeiro login. "
        "Use --dry-run para só listar os destinatários."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista quem receberia o e-mail, sem enviar nada.",
        )
        parser.add_argument(
            "--perfil",
            choices=[p.value for p in User.Perfil],
            help="Limita o envio a um perfil (ex.: COORDENADOR_UNIDADE).",
        )
        parser.add_argument(
            "--incluir-ja-logaram",
            action="store_true",
            help="Inclui quem já fez login (use após redefinir as senhas para a padrão).",
        )
        parser.add_argument(
            "--email",
            action="append",
            default=[],
            help="Limita o envio a este e-mail (pode repetir a opção).",
        )

    def handle(self, *args, **options):
        # "Nunca logou" = sem last_login. Só entra quem ainda tem a senha padrão:
        # enviar a senha padrão a quem já a trocou seria enganoso (e vazaria um
        # valor que já não funciona), mesmo que last_login esteja vazio.
        candidatos = User.objects.filter(is_active=True).exclude(email="").order_by("email")
        if options["perfil"]:
            candidatos = candidatos.filter(perfil=options["perfil"])
        if not options["incluir_ja_logaram"]:
            candidatos = candidatos.filter(last_login__isnull=True)
        if options["email"]:
            candidatos = candidatos.filter(email__in=options["email"])

        destinatarios = []
        ignorados = 0
        for user in candidatos:
            if user.check_password(DEFAULT_USER_PASSWORD):
                destinatarios.append(user)
            else:
                ignorados += 1
                self.stdout.write(f"  (ignorado, senha não é a padrão: {user.email})")

        self.stdout.write(f"Link de login: {url_login()}")
        for user in destinatarios:
            self.stdout.write(f"  - {user.email}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] {len(destinatarios)} e-mail(s) seriam enviados; "
                f"{ignorados} ignorado(s) (senha já alterada)."
            ))
            return

        # Envio DIRETO (sem Celery): com REDIS_URL definido e sem worker rodando,
        # o .delay() só enfileira e o e-mail nunca sai, sem nenhum erro visível.
        enviados, falhas = 0, 0
        for user in destinatarios:
            try:
                send_mail(**montar_email_novo_usuario(user))
                enviados += 1
                self.stdout.write(self.style.SUCCESS(f"  enviado: {user.email}"))
            except Exception as exc:
                falhas += 1
                self.stderr.write(self.style.ERROR(f"  FALHOU: {user.email} -> {exc!r}"))

        self.stdout.write(
            f"{enviados} enviado(s), {falhas} falha(s), "
            f"{ignorados} ignorado(s) (senha já alterada)."
        )
