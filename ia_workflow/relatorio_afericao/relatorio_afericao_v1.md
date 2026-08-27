# Relatório de Aferição — Implementação v1 e Correção de Migrações

**Data:** 2026-05-04
**Escopo:** Verificação de conformidade entre os dois documentos de referência e o estado atual do código
**Documentos de referência:**
1. `relatorio_erro_migracao.md` — Correção do `InconsistentMigrationHistory`
2. `implementation_plan_v1` — Refatoração do modelo User e autenticação por e-mail

---

## 1. Resumo da aferição

A implementação está **funcional e consistente**. Ambos os documentos foram executados com sucesso. O banco foi resetado corretamente, as migrações estão limpas, a autenticação por e-mail está operacional e os 4 testes automatizados passam sem erros.

Há, porém, **3 ressalvas** que devem ser endereçadas antes de avançar para a v2.

---

## 2. Checklist de conformidade — Relatório de Erro (Migrações)

| # | Ação requerida | Status | Evidência |
|---|---|---|---|
| 1 | Apagar `db.sqlite3` e recriar | ✅ Feito | Banco existe com 241KB, todas as migrações `[X]` |
| 2 | Apagar migrações antigas desatualizadas | ✅ Feito | `0001_initial.py` recriada em `2026-05-04 17:52` com modelo atualizado |
| 3 | `makemigrations` gerando modelo correto | ✅ Feito | Migration contém `perfil`, `email unique`, `related_name='usuarios'`, sem `is_academico` |
| 4 | `migrate` aplicado sem erro | ✅ Feito | `showmigrations` → todos `[X]`, ordem correta (`core` → `auth` → `accounts` → `admin`) |
| 5 | `makemigrations --check` sem pendências | ✅ Feito | Saída: `No changes detected` |
| 6 | `check --deploy` sem erros críticos | ✅ Feito | Apenas warnings esperados de produção (SSL, HSTS, DEBUG) |

**Veredito: ✅ Todas as ações do relatório de erro foram executadas com sucesso.**

---

## 3. Checklist de conformidade — Implementation Plan v1

| # | Requisito | Status | Detalhe |
|---|---|---|---|
| 1 | `UserManager` com suporte a e-mail | ✅ Implementado | `create_user` normaliza e-mail, espelha em `username`, valida campo vazio |
| 2 | `email` como `unique=True` | ✅ Implementado | Linha 43 do `models.py` |
| 3 | `USERNAME_FIELD = 'email'` | ✅ Implementado | Linha 69 — confirmado via Django shell |
| 4 | `REQUIRED_FIELDS` configurado | ⚠️ Divergência | Plan v1 diz `['username', 'cpf']`, implementação usa `['cpf']` — ver ressalva #1 |
| 5 | `is_academico` substituído por campo de perfil | ✅ Implementado | `perfil` com `TextChoices`: COORDENADOR_DESUP, COORDENADOR_UNIDADE, PROFESSOR |
| 6 | `ordering` por `email` | ✅ Implementado | `Meta.ordering = ['email']` |
| 7 | `__str__` usando e-mail | ✅ Implementado | `f"{self.email} ({self.get_perfil_display()})"` |
| 8 | Import do User corrigido no `admin.py` | ✅ Implementado | `from .models import User` (linha 4) |
| 9 | `list_display` atualizado no admin | ✅ Implementado | Usa `email`, `cpf`, `perfil`, `unidade`, `is_staff` |
| 10 | Import do User corrigido no `views.py` | ✅ N/A | View usa `authenticate` diretamente, sem import explícito do User |
| 11 | `login_view` simplificada para e-mail | ✅ Implementado | `authenticate(request, username=email, ...)` — funcional com `USERNAME_FIELD='email'` |
| 12 | Teste: criar usuário com e-mail | ✅ Passando | `test_create_user_with_email_success` → OK |
| 13 | Teste: autenticação por e-mail | ✅ Passando | `test_authentication_works_using_email` → OK |
| 14 | Teste: e-mail duplicado falha | ✅ Passando | `test_duplicate_email_raises_error` → OK |
| 15 | Teste: campo perfil funciona | ✅ Passando | `test_role_field_works_as_expected` → OK |

**Veredito: ✅ Implementação conforme o plan, com 1 divergência menor (ver abaixo).**

---

## 4. Ressalvas encontradas

### Ressalva #1 — Divergência em `REQUIRED_FIELDS`

- **Severidade:** Baixa
- **Arquivo:** [models.py:70](file:///d:/Repositorios/AllocGest-DESUP/project_root/apps/accounts/models.py#L70)
- **Problema:** O `implementation_plan_v1` especifica `REQUIRED_FIELDS = ['username', 'cpf']`, mas a implementação usa `REQUIRED_FIELDS = ['cpf']`.
- **Impacto:** Nenhum impacto funcional negativo. Na verdade, a implementação atual é **melhor** que o plan, porque o `UserManager.create_user` já espelha o e-mail no `username` automaticamente (`extra_fields.setdefault('username', email)`). Exigir `username` no `createsuperuser` seria redundante e confuso.
- **Recomendação:** Manter como está (`['cpf']`). A implementação é mais coerente que o plan original.

### Ressalva #2 — Mixin `RoleRequiredMixin` desatualizado

- **Severidade:** Alta
- **Arquivo:** [mixins.py](file:///d:/Repositorios/AllocGest-DESUP/project_root/apps/accounts/mixins.py)
- **Problema:** O mixin existente ainda usa lógica baseada em **Groups** (`request.user.groups.filter(name='Admin DESUP')`) em vez do campo `perfil` que substituiu essa abordagem na v1.
- **Impacto:** Qualquer view que use `RoleRequiredMixin` vai **bloquear todos os usuários** que não estejam em grupos Django, mesmo que tenham o perfil correto. Isso contradiz a decisão de usar `TextChoices` para controle de acesso.
- **Como corrigir:** Refatorar o mixin para usar `request.user.perfil` em vez de `groups`:

```python
class PerfilRequiredMixin:
    """
    Mixin que valida se o usuário possui um dos perfis permitidos.
    """
    allowed_profiles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        if request.user.is_superuser or request.user.perfil in self.allowed_profiles:
            return super().dispatch(request, *args, **kwargs)

        logger.warning(
            f"Acesso negado (403) para usuário ID: {request.user.id}, "
            f"perfil: {request.user.perfil}."
        )
        
        is_htmx = (
            getattr(request, 'htmx', False)
            or request.headers.get('HX-Request') == 'true'
        )
        
        if is_htmx:
            html_erro = (
                "<div class='p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50' role='alert'>"
                "Acesso negado: Você não possui o perfil necessário para este recurso."
                "</div>"
            )
            return HttpResponseForbidden(html_erro)

        raise PermissionDenied("Acesso negado para este perfil.")
```

> [!WARNING]
> Esta é a ressalva mais importante. O `implementation_plan_v2.md` já propõe o `PerfilRequiredMixin` no design, mas o código em `mixins.py` ainda contém a versão antiga baseada em Groups. **Isso deve ser corrigido antes de criar qualquer view protegida.**

### Ressalva #3 — `create_superuser` não define `cpf`

- **Severidade:** Média
- **Arquivo:** [models.py:21-31](file:///d:/Repositorios/AllocGest-DESUP/project_root/apps/accounts/models.py#L21-L31)
- **Problema:** O `create_superuser` não tem um default para `cpf`. Como `cpf` está em `REQUIRED_FIELDS`, o Django pede o valor interativamente no terminal — o que funciona. Porém, ao criar superusers **programaticamente** (ex: em scripts de seed, fixtures ou testes), esquecer de passar `cpf` resulta em `IntegrityError` por campo NOT NULL.
- **Impacto:** Baixo para uso interativo, mas pode causar falhas em scripts de automação e CI/CD.
- **Recomendação:** Não é necessário um default, mas documente que `cpf` é obrigatório em chamadas programáticas de `create_superuser`.

---

## 5. Resultados dos testes automatizados

```
Ran 4 tests in 13.438s — OK

✅ test_create_user_with_email_success
✅ test_authentication_works_using_email
✅ test_duplicate_email_raises_error
✅ test_role_field_works_as_expected
```

**Ordem de migrações no banco de teste (verificada):**
`core → contenttypes → auth → accounts → admin → courses → professors → sessions`

A ordem está correta: `accounts` é aplicado **antes** de `admin`, eliminando a inconsistência original.

---

## 6. Verificações de sistema

| Verificação | Resultado |
|---|---|
| `showmigrations` | Todas `[X]`, nenhuma pendente |
| `makemigrations --check` | `No changes detected` |
| `check --deploy` | 0 erros, 6 warnings (todos de produção — esperados em dev) |
| `USERNAME_FIELD` | `email` ✅ |
| `REQUIRED_FIELDS` | `['cpf']` ✅ |
| Manager ativo | `UserManager` ✅ |
| `email` unique | `True` ✅ |
| Usuários no banco | 0 (banco limpo, pós-reset) |

---

## 7. Mini-Relatório Profissional

| Campo | Detalhe |
|---|---|
| **Título** | Aferição de conformidade: Correção de migrações + Implementation Plan v1 |
| **Contexto analisado** | Estado atual do código após reset de banco e refatoração do modelo User para autenticação por e-mail com sistema de perfis |
| **Problemas encontrados** | 1 divergência baixa (REQUIRED_FIELDS), 1 mixin desatualizado (alta), 1 risco menor em scripts (média) |
| **Classificação geral** | 🟡 Funcional com ressalvas |
| **Impacto no sistema** | O sistema está operacional, mas o mixin de autorização não reflete o novo modelo de perfis |
| **Recomendação principal** | Corrigir `mixins.py` para usar `perfil` em vez de `groups` **antes** de prosseguir com a v2 |
| **Status final** | ✅ **Aprovado com ressalvas** — Implementação funcional e testada. Corrigir mixin antes do próximo ciclo. |
