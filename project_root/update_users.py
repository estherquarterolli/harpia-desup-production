import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()

from django.contrib.auth import get_user_model
from apps.core.models import Unidade

User = get_user_model()

# Delete users with empty usernames if they exist due to previous bug
User.objects.filter(username="").delete()

unidade_email = "unidadefatec@desup.com"
unidade_password = "Faetec@123"

desup_email = "coordenadordesup@desup.com"
desup_password = "Faetec@123"

unidade, _ = Unidade.objects.get_or_create(
    sigla="FAETEC-TESTE",
    defaults={"nome": "Unidade de Teste", "status": True},
)

# Unidade User
if not User.objects.filter(email=unidade_email).exists():
    u_user = User.objects.create_user(
        email=unidade_email,
        password=unidade_password,
        perfil=User.Perfil.COORDENADOR_UNIDADE,
        unidade=unidade
    )
    print(f"Created {unidade_email}")
else:
    u_user = User.objects.get(email=unidade_email)
    u_user.set_password(unidade_password)
    u_user.save()
    print(f"Updated password for {unidade_email}")

# DESUP User
if not User.objects.filter(email=desup_email).exists():
    d_user = User.objects.create_user(
        email=desup_email,
        password=desup_password,
        perfil=User.Perfil.DESUP,
    )
    print(f"Created {desup_email}")
else:
    d_user = User.objects.get(email=desup_email)
    d_user.set_password(desup_password)
    d_user.save()
    print(f"Updated password for {desup_email}")
