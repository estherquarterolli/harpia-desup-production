# Relatório de Correção — Erro 500 no Login (Redis/Cache)

**Papel:** Agente CORRECTOR (Correção de Estabilidade e Configuração de Ambiente)
**Data:** 2026-07-07
**Escopo:** Diagnóstico e correção do erro HTTP 500 na rota `POST /login/` em ambiente de desenvolvimento local, além do endurecimento da view de login contra falhas de cache.

---

## 1. Sintoma Reportado

Requisições de login via HTMX retornando erro 500 de forma consistente:

```
login/   500   xhr   htmx.org@1.9.10   148 kB   ~4.2 s
```

O erro ocorria a cada tentativa de login, independentemente das credenciais.

---

## 2. Diagnóstico (Causa Raiz)

O 500 **não estava na lógica de autenticação**, e sim na camada de **cache**.

- O `.env` local definia `REDIS_URL=redis://localhost:6379/0`.
- Em `config/settings/base.py`, a presença de `REDIS_URL` faz o cache padrão ser `RedisCache`:
  ```python
  REDIS_URL = config("REDIS_URL", default="")
  if REDIS_URL:
      CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
  else:
      CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", ...}}
  ```
- Como **não havia Redis rodando** na máquina, a primeira operação de cache da view de login estourava a conexão:

```
apps/accounts/views.py:44  →  attempts = cache.get(cache_key, 0)
redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379
(Nenhuma conexão pôde ser feita — a máquina de destino recusou ativamente)
```

A `login_view` usa o cache para a **Regra #10 (lockout após 5 tentativas)**. Sem Redis disponível, `cache.get`/`cache.set` derrubavam a requisição antes mesmo de chamar `authenticate()`.

> Observação: o mesmo `0xe7 / ConnectionRefused` em mensagens do PostgreSQL/Redis em português (com "ç") já havia mascarado erros anteriores neste ambiente Windows.

---

## 3. Correções Aplicadas

### 🔌 Configuração de Ambiente (`project_root/.env`)
- ✅ **Redis desativado para dev local:** `REDIS_URL` comentado. Isso faz o cache cair automaticamente para `LocMemCache` (em memória) e o Celery entrar em modo **eager** (`CELERY_TASK_ALWAYS_EAGER = not bool(REDIS_URL)`), executando tasks de forma síncrona sem broker.
- ✅ **Linhas `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` comentadas** junto, com comentário explicativo para reativação.

### 🛡️ Endurecimento da View de Login (`apps/accounts/views.py`)
- ✅ Adicionados três helpers resilientes que envolvem o cache em `try/except` e registram `logger.warning` em caso de falha, sem interromper o fluxo:
  - `_cache_get(key, default)`
  - `_cache_set(key, value, timeout)`
  - `_cache_delete(key)`
- ✅ As três chamadas diretas na `login_view` foram substituídas pelos helpers:
  - `cache.get`  → `_cache_get`
  - `cache.set`  → `_cache_set`
  - `cache.delete` → `_cache_delete`

**Efeito:** se o cache estiver indisponível (Redis configurado mas fora do ar, ou qualquer falha de backend), o login **continua funcionando** — apenas o rate-limit é ignorado de forma silenciosa e logada, em vez de gerar um 500.

---

## 4. Validação

Testes executados via `django.test.Client`, incluindo cenário com **Redis propositalmente fora do ar** (`redis://localhost:6399`, backend `RedisCache`):

| Cenário | Antes | Depois |
|---|---|---|
| Login válido (cache OK, LocMem) | 500 | **200 + `HX-Redirect`** |
| Login válido, **Redis fora do ar** | 500 | **200 + `HX-Redirect=/admin/`** |
| Login inválido, **Redis fora do ar** | 500 | **200 + alerta "E-mail ou senha inválidos"** |

Autenticação confirmada para os usuários semeados:

| Usuário | Senha | Auth |
|---|---|---|
| `estagio.analista2@desup.faetec.rj.gov.br` | `Faetec@123` | ✅ |
| `estagio.analista1@desup.faetec.rj.gov.br` | `@Eq122507@` | ✅ |
| `unidadeparacambi@desup.com` | `Faetec@123` | ✅ |

> ⚠️ **Pendência identificada:** o usuário `coordenador@desup.com` (coord. DESUP, pré-existente de seed antiga) **não** autentica com `Faetec@123` — senha divergente. Recomenda-se redefinir a senha desse usuário.

---

## 5. Arquivos Alterados

| Arquivo | Alteração |
|---|---|
| `project_root/.env` | `REDIS_URL` e `CELERY_*` comentados (modo dev sem Redis) |
| `project_root/apps/accounts/views.py` | Helpers `_cache_get/_cache_set/_cache_delete` + substituição das chamadas na `login_view` |

---

## 6. Como Testar os Dois Modos

Consulte o guia complementar criado nesta mesma entrega:
**`docs/guias/RODAR_COM_E_SEM_REDIS.md`** — passo a passo para rodar o projeto **sem** e **com** Redis/Celery, com verificações e troubleshooting.
