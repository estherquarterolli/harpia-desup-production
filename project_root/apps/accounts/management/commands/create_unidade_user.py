from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.core.models import Unidade
from apps.accounts.models import DEFAULT_USER_PASSWORD

User = get_user_model()

EMAIL = "coordenador@unidade.com"


class Command(BaseCommand):
    help = "Cria o usuário de teste de Coordenador de Unidade (apenas para desenvolvimento)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            default=EMAIL,
            help='E-mail do usuário de teste.',
        )

    def handle(self, *args, **kwargs):
        email = kwargs['email']

        unidade, u_criada = Unidade.objects.get_or_create(
            sigla="FAETEC-TESTE",
            defaults={"nome": "Unidade de Teste", "status": True},
        )
        if u_criada:
            self.stdout.write(self.style.SUCCESS(f"Unidade '{unidade}' criada."))
        else:
            self.stdout.write(self.style.WARNING(f"Unidade '{unidade}' já existia."))

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            self.stdout.write(self.style.WARNING(
                f"Usuário '{email}' já existe. Senha NÃO foi alterada."
            ))
        else:
            user = User.objects.create_user(
                email=email,
                password=DEFAULT_USER_PASSWORD,
                perfil=User.Perfil.COORDENADOR_UNIDADE,
                unidade=unidade,
                forcar_troca_senha=True,
            )
            self.stdout.write(self.style.SUCCESS(
                "Usuário Coordenador de Unidade criado. Troca de senha obrigatória no primeiro acesso."
            ))

        self.stdout.write("")
        self.stdout.write("=" * 50)
        self.stdout.write(" USUÁRIO DE TESTE CRIADO")
        self.stdout.write("=" * 50)
        self.stdout.write(f"  E-mail : {email}")
        self.stdout.write(f"  Senha  : [use DEFAULT_USER_PASSWORD do ambiente]")
        self.stdout.write(f"  Perfil : {user.get_perfil_display()}")
        self.stdout.write(f"  Unidade: {user.unidade}")
        self.stdout.write("=" * 50)
