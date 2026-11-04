from django.core.management.base import BaseCommand

from apps.accounts.models import DEFAULT_USER_PASSWORD, User
from apps.accounts.signals import enviar_email_novo_usuario, url_login


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
            "--email",
            action="append",
            default=[],
            help="Limita o envio a este e-mail (pode repetir a opção).",
        )

    def handle(self, *args, **options):
        # "Nunca logou" = sem last_login. Só entra quem ainda tem a senha padrão:
        # enviar a senha padrão a quem já a trocou seria enganoso (e vazaria um
        # valor que já não funciona), mesmo que last_login esteja vazio.
        candidatos = User.objects.filter(
            is_active=True, last_login__isnull=True,
        ).exclude(email="").order_by("email")
        if options["email"]:
            candidatos = candidatos.filter(email__in=options["email"])

        destinatarios = []
        ignorados = 0
        for user in candidatos:
            if user.check_password(DEFAULT_USER_PASSWORD):
                destinatarios.append(user)
            else:
                ignorados += 1

        self.stdout.write(f"Link de login: {url_login()}")
        for user in destinatarios:
            self.stdout.write(f"  - {user.email}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] {len(destinatarios)} e-mail(s) seriam enviados; "
                f"{ignorados} ignorado(s) (senha já alterada)."
            ))
            return

        for user in destinatarios:
            enviar_email_novo_usuario(user)

        self.stdout.write(self.style.SUCCESS(
            f"{len(destinatarios)} e-mail(s) enfileirado(s); "
            f"{ignorados} ignorado(s) (senha já alterada)."
        ))
