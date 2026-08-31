# CORR-005 — Observabilidade de erros 500

- **Status:** Corrigido (2026-07-16)
- **Prioridade:** Alta · **Área:** Infra / Observabilidade
- **Escopo tocado:** `config/settings/base.py`, `templates/500.html`.

## O que faltava (diagnóstico)

O projeto **não tinha** `LOGGING`, `ADMINS` nem `SERVER_EMAIL` em nenhum settings.
Consequências:

1. O e-mail padrão de erro 500 do Django (`django.request` → `AdminEmailHandler`)
   **nunca disparava** — sem `ADMINS` e sem `LOGGING`, não há para quem notificar nem
   handler que capture o `ERROR`.
2. Não havia nenhum registro (arquivo/console dedicado) do traceback dos 500 — foi
   exatamente o que travou o diagnóstico da CORR-004 (o 500 ocorreu e ninguém foi avisado,
   sem stack trace acessível).
3. O `templates/500.html` afirmava **"Nossa equipe já foi notificada"**, o que era **falso**.

## O que mudou

### `config/settings/base.py`

Novo bloco **"Observabilidade de erros 500 (CORR-005)"** logo após o
`DEFAULT_FROM_EMAIL` (antes do bloco `# Celery`):

- **`_parse_admins(raw)`** — helper que converte a string de ambiente em lista de tuplas
  `(nome, email)`. Aceita `"Nome <email>"` ou apenas `"email"`, separados por vírgula.
- **`ADMINS`** = `_parse_admins(config("ADMINS_EMAILS", default=""))`. Vazio por padrão
  (fallback seguro — nenhum e-mail hardcoded no repositório).
- **`MANAGERS = ADMINS`**.
- **`SERVER_EMAIL`** = `config("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)` — remetente do
  e-mail de erro.
- **`ADMIN_EMAIL_INCLUDE_HTML`** = `config("ADMIN_EMAIL_INCLUDE_HTML", default=False, cast=bool)`
  — controla `include_html` do `AdminEmailHandler`. Padrão **False** (traceback em texto
  puro basta e evita vazar dados sensíveis por e-mail; pode ser ligado por ambiente).
- **`DJANGO_LOG_LEVEL`** = `config("DJANGO_LOG_LEVEL", default="INFO")`.
- **`LOG_DIR`** = `BASE_DIR / "logs"`, criado com `mkdir(parents=True, exist_ok=True)` dentro
  de `try/except OSError` — em filesystem somente-leitura o handler de arquivo é omitido
  e segue só com console (não quebra).
- **`LOGGING`** (dictConfig):
  - filtros `require_debug_false` / `require_debug_true`;
  - formatters `verbose` (arquivo) e `simple` (console);
  - handlers: `console` (StreamHandler), `mail_admins`
    (`django.utils.log.AdminEmailHandler`, level ERROR, filtro `require_debug_false`),
    e `file` (`RotatingFileHandler`, level ERROR, 5 MB × 5 backups, `logs/errors.log`)
    adicionado condicionalmente se `LOG_DIR` existe;
  - `root` → console;
  - logger **`django`** → console + file (level `DJANGO_LOG_LEVEL`);
  - logger **`django.request`** → console + file + **mail_admins** (level ERROR).

### `templates/500.html`

Mensagem corrigida para não mentir. Antes:

> "Não foi possível processar sua solicitação. Nossa equipe já foi notificada. / Por favor,
> tente novamente em alguns instantes."

Depois (neutro e verdadeiro):

> "Ocorreu um erro inesperado e não foi possível processar sua solicitação. / Por favor,
> tente novamente em alguns instantes. Se o problema persistir, entre em contato com o suporte."

## Como o DEV/super admin é notificado

- **Produção (`config.settings.production`, `DEBUG=False`):** qualquer 500 é logado por
  `django.request` em nível ERROR → o `AdminEmailHandler` envia e-mail com o traceback
  para todos os `ADMINS`, usando `SERVER_EMAIL` como remetente e o `EMAIL_BACKEND`/SMTP
  configurado (já vindo de ambiente em `base.py`: `EMAIL_HOST/PORT/USER/PASSWORD/TLS`).
  Em paralelo, o traceback vai para o console (logs do Render) e para `logs/errors.log`.
- **Desenvolvimento (`config.settings.development`, `DEBUG=True`):** o `AdminEmailHandler`
  fica **inerte** (filtro `require_debug_false`) — não exige SMTP. O erro aparece no
  console e em `logs/errors.log`. O `EMAIL_BACKEND` de dev é o console backend, então mesmo
  se um e-mail fosse disparado ele seria só impresso.
- **Sem `ADMINS_EMAILS` definido:** nenhum e-mail é enviado (lista vazia), mas o log em
  console/arquivo continua funcionando — sem crash.

> Observação: o `handler500` customizado (`apps.core.views.custom_500`, referenciado em
> `config/urls.py`) apenas renderiza o `500.html`. A notificação **não** depende dele — o
> Django loga em `django.request` *antes* de chamar o handler, então o e-mail dispara
> normalmente.

## Variáveis de ambiente novas a definir

| Variável | Onde | Default | Descrição |
|---|---|---|---|
| `ADMINS_EMAILS` | **produção (obrigatória p/ e-mail)** | `""` | Destinatários do e-mail de erro. Ex.: `"Dev Harpia <dev@exemplo.com>,ops@exemplo.com"`. Vazio = ninguém notificado. |
| `SERVER_EMAIL` | produção (opcional) | `DEFAULT_FROM_EMAIL` | Remetente do e-mail de erro do servidor. |
| `ADMIN_EMAIL_INCLUDE_HTML` | opcional | `False` | Se `True`, anexa o relatório HTML completo (traceback interativo). Cuidado com dados sensíveis. |
| `DJANGO_LOG_LEVEL` | opcional | `INFO` | Nível dos loggers `django`/root. |

**Importante para produção (Render):** para o e-mail sair de fato, além de `ADMINS_EMAILS`
é preciso ter o SMTP configurado por ambiente (`EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`) — o default `localhost:25` não
envia no Render.

## Verificação executada

- `DJANGO_SETTINGS_MODULE=config.settings.development manage.py check` → **0 issues**.
- `DJANGO_SETTINGS_MODULE=config.settings.production manage.py check` (com `SECRET_KEY`
  dummy) → **0 issues**.
- Carregamento de settings com `ADMINS_EMAILS="Dev Harpia <dev@exemplo.com>,ops@exemplo.com"`:
  `ADMINS`/`MANAGERS` corretamente parseados; `django.request` com handlers
  `['console','file','mail_admins']`; `mail_admins` = `AdminEmailHandler`.
- Smoke test: `logging.getLogger('django.request').error(..., exc_info=...)` em dev →
  traceback impresso no console (formato `simple`) **e** escrito em `logs/errors.log`
  (formato `verbose`); e-mail inerte por `require_debug_false`.

### Como testar manualmente o e-mail (staging/prod)

1. Definir `DEBUG=False`, `ADMINS_EMAILS`, `SERVER_EMAIL` e o SMTP por ambiente.
2. Provocar um 500 proposital (ex.: view temporária que faz `raise Exception("teste 500")`).
3. Conferir a chegada do e-mail aos `ADMINS` e o traceback em `logs/errors.log`/console.
   (Não foi criado teste automatizado em `apps/core/` para não conflitar com outros agentes —
   validação por `check` + smoke test acima.)

## Rollback

- `git checkout -- project_root/config/settings/base.py project_root/templates/500.html`
  (únicos arquivos de código tocados).
- Reverter, se desejado, esta seção do checklist / este relatório.
- Nenhuma migração, dependência nova ou mudança de schema envolvida. O arquivo
  `project_root/logs/errors.log` é gerado em runtime e já está coberto por `*.log` no
  `.gitignore` — pode ser removido livremente.
