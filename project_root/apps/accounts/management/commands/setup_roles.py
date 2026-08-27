from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.db import transaction

class Command(BaseCommand):
    help = 'Cria os grupos de usuários padrão e atribui permissões básicas.'

    def handle(self, *args, **kwargs):
        # Mapeamento de grupos e codinomes de permissões básicos
        grupos_permissoes = {
            'Superuser': [
                'add_user', 'change_user', 'delete_user', 'view_user',
                'add_unidade', 'change_unidade', 'delete_unidade', 'view_unidade',
            ],
            'Admin DESUP': [
                'view_user', 'change_user',
                'add_unidade', 'change_unidade', 'view_unidade', 'delete_unidade',
            ],
            'Gestor Unidade': [
                'view_user',
                'view_unidade',
            ]
        }

        try:
            with transaction.atomic():
                for nome_grupo, codinomes in grupos_permissoes.items():
                    # get_or_create garante que a criação seja idempotente
                    grupo, created = Group.objects.get_or_create(name=nome_grupo)
                    
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Grupo '{nome_grupo}' criado com sucesso."))
                    else:
                        self.stdout.write(self.style.WARNING(f"Grupo '{nome_grupo}' já existia."))

                    # Busca as permissões no banco de dados pelos codinomes
                    permissoes = Permission.objects.filter(codename__in=codinomes)
                    
                    # Atualiza as permissões do grupo de forma idempotente
                    grupo.permissions.set(permissoes)
                    
                    self.stdout.write(self.style.SUCCESS(f"Permissões atualizadas para o grupo '{nome_grupo}'."))
                    
            self.stdout.write(self.style.SUCCESS('Configuração de roles (grupos e permissões) finalizada com sucesso!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao configurar roles: {e}'))
