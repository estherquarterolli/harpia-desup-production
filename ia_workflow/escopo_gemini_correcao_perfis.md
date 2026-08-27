# Correção de domínio — Remoção do perfil PROFESSOR do modelo User

Esta tarefa é uma **correção de domínio** para aplicar junto ou logo depois do escopo anterior.

---

## Contexto

Identificamos uma divergência entre o modelo implementado e as regras reais de negócio:

- O sistema AllocGest-DESUP é usado **apenas por coordenadores**.
- **Professores não logam no sistema.** Eles são entidades de domínio gerenciadas pelos coordenadores.
- O perfil `PROFESSOR` no `TextChoices` do modelo `User` não reflete nenhum caso de uso real de login.

---

## Escopo da correção

### 1. Alterar o modelo `User` em `apps/accounts/models.py`

Remover o valor `PROFESSOR` do `TextChoices` de `Perfil`, deixando apenas os dois perfis reais:

```python
class Perfil(models.TextChoices):
    COORDENADOR_DESUP    = 'COORDENADOR_DESUP',    'Coordenador DESUP'
    COORDENADOR_UNIDADE  = 'COORDENADOR_UNIDADE',  'Coordenador de Unidade'
```

O `default` do campo `perfil` deve ser alterado para `Perfil.COORDENADOR_UNIDADE` (o perfil menos privilegiado restante).

### 2. Gerar e aplicar a migration

A remoção de uma `Choice` **não altera o schema do banco**, mas o Django pode ou não gerar uma migration dependendo da versão. Verificar com `makemigrations --check`. Se gerar migration, aplicar normalmente.

### 3. Ajustar a `login_view` em `apps/accounts/views.py`

A função auxiliar `get_redirect_url_for_user(user)` deve tratar apenas os dois perfis válidos. Remover o caso `PROFESSOR`. Exemplo esperado:

```python
def get_redirect_url_for_user(user):
    if user.is_superuser:
        return '/admin/'
    if user.perfil == 'COORDENADOR_DESUP':
        return '/dashboard/desup/'
    if user.perfil == 'COORDENADOR_UNIDADE':
        return '/dashboard/unidade/'
    # Fallback seguro — perfil inválido ou não mapeado
    return '/login/'
```

### 4. Ajustar os stubs de dashboard

Remover a view stub `/dashboard/professor/` e sua rota, caso tenham sido criados no escopo anterior.

Manter apenas:
- `/dashboard/desup/`
- `/dashboard/unidade/`

### 5. Ajustar testes em `apps/accounts/tests.py`

Se o escopo anterior gerou testes com `perfil='PROFESSOR'`, substituir por `perfil='COORDENADOR_UNIDADE'` para manter os testes válidos.

---

## Restrições

- Não alterar o model `Professor` em `apps/professors/models.py`. `Professor` é uma entidade de domínio, não um usuário.
- Não criar nenhum novo campo no modelo `User`.
- Não usar Groups do Django.
- Não criar portal ou área de acesso para professores — isso é fase 2, se houver.

---

## Critérios de validação

1. `User.Perfil.choices` retorna exatamente 2 opções: `COORDENADOR_DESUP` e `COORDENADOR_UNIDADE`.
2. Não existe mais referência a `PROFESSOR` em nenhum arquivo de `apps/accounts/`.
3. Login com `COORDENADOR_DESUP` → redireciona para `/dashboard/desup/`.
4. Login com `COORDENADOR_UNIDADE` → redireciona para `/dashboard/unidade/`.
5. `makemigrations --check` → sem pendências (ou migration limpa aplicada).
6. Testes passam sem erro.
