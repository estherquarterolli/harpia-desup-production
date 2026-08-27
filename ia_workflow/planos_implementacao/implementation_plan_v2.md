# Plano de Implementação (v2) — Isolamento e Segurança

Este plano detalha a próxima etapa do desenvolvimento do **AllocGest-DESUP**, focando no isolamento de dados por unidade e no controle de acesso refinado por perfil.

## Status Atual (Concluído na v1)
- [x] **Modelo User Refatorado**: Login via e-mail e campo `perfil` (Choices).
- [x] **UserManager Customizado**: Suporte total a autenticação baseada em e-mail.
- [x] **Suíte de Testes Base**: Validação de criação, duplicidade e autenticação.

---

## Próxima Etapa: Isolamento por Unidade (Multi-tenancy)

### 1. Modelagem e Managers (`apps/core/models.py`)
Implementar um Manager base que automatize o filtro de unidade para todos os modelos vinculados.

```python
from django.db import models

class UnitBoundQuerySet(models.QuerySet):
    def for_user(self, user):
        if user.is_superuser or user.perfil == 'COORDENADOR_DESUP':
            return self.all()
        # Assume que o model tem um campo 'unidade' ou 'unidade_principal'
        if hasattr(self.model, 'unidade'):
            return self.filter(unidade=user.unidade)
        if hasattr(self.model, 'unidade_principal'):
            return self.filter(unidade_principal=user.unidade)
        return self.all()

class UnitBoundManager(models.Manager):
    def get_queryset(self):
        return UnitBoundQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)
```

### 2. Segurança nas Views (`apps/accounts/mixins.py`)
Criar mixins para validar o perfil de acesso e impedir manipulação de IDs na URL.

```python
from django.core.exceptions import PermissionDenied

class PerfilRequiredMixin:
    allowed_profiles = []
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if request.user.is_superuser or request.user.perfil in self.allowed_profiles:
            return super().dispatch(request, *args, **kwargs)
        raise PermissionDenied("Acesso negado para este perfil.")
```

### 3. Aplicação no Domínio (`apps/professors/models.py`)
Vincular o `UnitBoundManager` ao modelo de Professores e outros modelos operacionais.

---

## Roadmap de Curto Prazo
1. **Migrações de Segurança**: Aplicar mudanças no banco de dados.
2. **Refatoração de Mixins**: Migrar a lógica de "Grupos" para o campo "Perfil".
3. **CRUD de Professores**: Implementar listagem e criação já filtradas por unidade.

## Validação de Sucesso
- Um Coordenador da Unidade A **não** consegue visualizar professores da Unidade B.
- Um Coordenador da DESUP (Global) visualiza todos os registros.
- Tentativas de acesso via ID direto na URL de outra unidade retornam 403 Forbidden.
