# Harpia (HARPIA-DESUP) — Documento de Infraestrutura para Deploy em VM

> **Objetivo:** reunir tudo que os responsáveis pela VM precisam para subir a aplicação:
> stack, versões, serviços externos, arquivos de configuração, variáveis de ambiente e comandos.
> **Aplicação:** *Harpia* — sistema acadêmico da FAETEC/DESUP (gestão de matrizes curriculares,
> alocação de docentes e pendências extracurriculares).
> **Arquitetura:** monólito **Django** com renderização no servidor (server-side) + **HTMX**;
> **não há SPA nem build de front-end** (CSS/JS vêm de CDN). Data: 2026-07-09.

---

## ⚠️ 3 pontos críticos (ler antes de tudo)

1. **Python 3.12+ é obrigatório.** O projeto usa **Django 6.0.3**, que exige **Python 3.12 ou
   superior**. O ambiente de desenvolvimento roda **Python 3.12.10**. O arquivo `render.yaml`
   está desatualizado (fixa `3.11`) — **não** use 3.11, a aplicação não sobe.
2. **Defina `DJANGO_SETTINGS_MODULE=config.settings.production`** no ambiente. Os arquivos
   `manage.py` e `config/wsgi.py` têm *fallback* para `config.settings.development` (DEBUG=True).
   Sem essa variável, a aplicação sobe em **modo de desenvolvimento** — inseguro em produção.
3. **A rede da VM precisa liberar as portas do banco.** O PostgreSQL de produção é o
   **Supabase**, acessado nas portas **5432** (session pooler) / **6543** (transaction pooler)
   e **443** (REST/Storage). No ambiente de dev, o firewall da unidade bloqueava 5432/6543 —
   confirme com a rede da VM que essas saídas estão liberadas.

---

## 1. Web service / servlet

| Item | Valor |
|---|---|
| Tipo | Aplicação web **WSGI** (Django), HTML server-side + HTMX |
| Servidor de aplicação (produção) | **Gunicorn 21.2.0** (`config.wsgi:application`) |
| Callable WSGI | `config.wsgi:application` |
| Servidor de dev | `manage.py runserver` (não usar em produção) |
| Porta | `runserver`: **8000**; Gunicorn: **`$PORT`** (definido pelo ambiente) |
| Arquivos estáticos | **WhiteNoise 6.12.0** (servidos pelo próprio app; `CompressedManifestStaticFilesStorage` em produção) |
| Proxy reverso | Recomendado **nginx** na frente do Gunicorn (TLS, headers). Configurar `SECURE_PROXY_SSL_HEADER` já está previsto no código |

> **Gunicorn é Linux-only.** Se a VM for **Windows**, o Gunicorn não roda nativamente — use
> **WSL** ou troque por **waitress** (`pip install waitress` +
> `waitress-serve --port=$PORT config.wsgi:application`). Recomendado: **VM Linux (Ubuntu)**.

---

## 2. Tecnologias / stack

### Backend
| Tecnologia | Versão | Papel |
|---|---|---|
| **Python** | **3.12+** (dev: 3.12.10) | Linguagem |
| **Django** | **6.0.3** | Framework web |
| Gunicorn | 21.2.0 | Servidor WSGI (produção) |
| WhiteNoise | 6.12.0 | Servir estáticos |
| psycopg2-binary | 2.9.12 | Driver PostgreSQL |
| dj-database-url | 2.1.0 | Parse de `DATABASE_URL` |
| python-decouple | 3.8 | Ler config do `.env`/ambiente |
| Celery | 5.6.3 | Fila de tarefas assíncronas |
| redis (redis-py) | 5.3.1 | Cliente Redis (broker/cache) |
| django-unfold | 0.95.0 | Tema do Django Admin |
| django-cors-headers | 4.9.0 | CORS |
| supabase (SDK) | 2.1.0 | Integração Supabase (Storage) |
| asgiref | 3.11.1 | Suporte ASGI (dependência do Django) |
| sqlparse | 0.5.5 | Dependência do Django |
| tzdata | 2026.1 | Fusos horários |

> Lista completa e travada em `project_root/requirements.txt`. O `pip freeze` do ambiente traz
> também as dependências transitivas (pydantic, httpx, gotrue, storage3, kombu, billiard etc.).

### Banco de dados
- **PostgreSQL** (produção: **Supabase**). Conexão via `DATABASE_URL` com **`sslmode=require`**
  (forçado no código). `conn_max_age=0` (compatível com pooler transaction/session).
- Sem `DATABASE_URL`, o *dev* cai em Postgres local (variáveis `DB_*`). Há um `sqlite_backup`
  **apenas** para desenvolvimento — **não** é usado em produção.

### Front-end (via CDN — **sem etapa de build**)
| Biblioteca | Versão | Origem |
|---|---|---|
| TailwindCSS | runtime CDN | `cdn.tailwindcss.com` |
| HTMX | 1.9.10 | `unpkg.com` |
| Alpine.js | 3.x | `unpkg.com` (em algumas telas) |
| Lucide icons | latest | `unpkg.com` |
| Phosphor icons | latest | `unpkg.com` |
| SweetAlert2 | 11 | `cdn.jsdelivr.net` |

> **Não há pipeline Node/npm de produção.** Existe `package.json` (só `lucide-react`) e
> `node_modules/`, mas a aplicação **não depende** deles para rodar. Requisito prático: a VM (ou
> o navegador do usuário) precisa de **acesso à internet** para carregar os CDNs de front-end.
> Se a rede for fechada, será necessário *self-host* desses assets (mudança futura, fora deste escopo).

### Apps internos (Django)
`apps.accounts` (usuário/auth), `apps.core` (comum, storage, notificações), `apps.courses`
(matrizes/componentes), `apps.professors` (docentes), `apps.allocations` (alocação curricular),
`apps.extra_curricular` (pendências extracurriculares).

---

## 3. APIs e serviços externos

| Serviço | Usado? | Para quê | Portas / protocolo |
|---|---|---|---|
| **Supabase — PostgreSQL** | **Sim** | Banco de dados de produção | 5432 (session pooler) / 6543 (transaction pooler), TLS |
| **Supabase — Storage** | **Sim** (se configurado) | Armazenamento de arquivos/uploads (bucket) | HTTPS **443** |
| **Redis** | **Opcional** | Broker/result do Celery **e** cache | 6379 (TCP) |
| **SMTP (e-mail)** | **Sim** | Envio de e-mails (reset de senha, links) | conforme provedor (ex.: 587/TLS) |
| **Docker** | **Não obrigatório** | Aparece **apenas** nos guias de dev para subir Postgres/Redis locais. Não é exigido para deploy | — |
| **n8n** | **Não** | Não é utilizado pelo projeto | — |
| Render.com | Referência | PaaS onde rodava (`render.yaml`); serve de modelo para replicar na VM | — |

### Comportamento sem Redis
Se **`REDIS_URL` não for definido**: o Celery entra em **modo *eager*** (tarefas executam de
forma **síncrona**, no próprio processo web) e o cache usa **`LocMemCache`** (memória local).
A aplicação **funciona** assim — Redis é uma **otimização**, não um requisito rígido. Para
processamento assíncrono real, provisione um Redis e defina `REDIS_URL`.

---

## 4. Arquivos de configuração

| Arquivo | Papel |
|---|---|
| `project_root/requirements.txt` | Dependências Python (versões travadas) |
| `project_root/.env` | Variáveis do ambiente **(NÃO versionar segredos; usar como referência)** |
| `project_root/.env.example` | Modelo com todas as chaves esperadas |
| `project_root/config/settings/base.py` | Settings comuns (apps, middleware, cache, e-mail, Celery, storage) |
| `project_root/config/settings/production.py` | Produção: DEBUG off, banco via `DATABASE_URL`, HTTPS/HSTS, WhiteNoise manifest |
| `project_root/config/settings/development.py` | Desenvolvimento: DEBUG on, banco local |
| `project_root/config/wsgi.py` | Entrada WSGI (⚠️ *fallback* p/ development) |
| `project_root/config/asgi.py` | Entrada ASGI (não usado no deploy atual) |
| `project_root/config/celery.py` | App Celery (`config`), *fallback* p/ production |
| `Procfile` | Comandos de release e web (modelo Render/Heroku) |
| `render.yaml` | Build/start/envVars no Render (⚠️ Python 3.11 desatualizado — usar 3.12+) |

### Variáveis de ambiente (produção)
```dotenv
# --- Django ---
DJANGO_SETTINGS_MODULE=config.settings.production   # OBRIGATÓRIO
SECRET_KEY=<gerar um valor forte e único>
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com,www.seu-dominio.com
TIME_ZONE=America/Sao_Paulo                          # opcional (default já é este)
DEFAULT_USER_PASSWORD=<senha inicial p/ resets/criação> # trocada no 1º login

# --- Banco (Supabase / PostgreSQL) ---
DATABASE_URL=postgresql://USER:SENHA@HOST:5432/postgres   # pooler do Supabase; sslmode é forçado

# --- Supabase (Storage) ---
SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_KEY=<anon/public key>
SUPABASE_SERVICE_ROLE_KEY=<service role key>
SUPABASE_STORAGE_BUCKET=<nome-do-bucket>

# --- Redis / Celery (OPCIONAL) ---
REDIS_URL=redis://HOST:6379/0
CELERY_BROKER_URL=redis://HOST:6379/0        # default cai no REDIS_URL
CELERY_RESULT_BACKEND=redis://HOST:6379/0    # default cai no REDIS_URL

# --- E-mail (SMTP) ---
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seu-provedor.com
EMAIL_PORT=587
EMAIL_HOST_USER=<usuario>
EMAIL_HOST_PASSWORD=<senha>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=no-reply@seu-dominio.com

# --- CORS (se houver front separado) ---
CORS_ALLOWED_ORIGINS=https://seu-front.com
```

---

## 5. Comandos para rodar o servidor

### 5.1 Preparação (uma vez)
```bash
# 1. Python 3.12+ e virtualenv
python3.12 -m venv .venv
source .venv/bin/activate            # Linux/macOS
# .venv\Scripts\activate            # Windows

# 2. Dependências
pip install --upgrade pip
pip install -r project_root/requirements.txt

# 3. Variáveis de ambiente (exportar ou usar um .env no project_root/)
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY=... ALLOWED_HOSTS=... DATABASE_URL=...   # etc (ver seção 4)

# 4. Migrações e estáticos (a partir de project_root/)
cd project_root
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 5. (Opcional) primeiro superusuário
python manage.py createsuperuser
```

### 5.2 Subir a aplicação (produção)
```bash
cd project_root
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```
> Equivale ao `Procfile`/`render.yaml`. Ajuste `--workers` ao número de vCPUs
> (regra prática: `2 × vCPUs + 1`). Rode atrás de um **nginx** com TLS.

### 5.3 Celery (somente se usar Redis)
```bash
cd project_root
celery -A config worker -l info
# Windows: adicionar -P solo (ou usar eventlet)
```

### 5.4 Desenvolvimento (referência)
```bash
cd project_root
export DJANGO_SETTINGS_MODULE=config.settings.development   # ou deixar o fallback
python manage.py runserver 0.0.0.0:8000
```

### 5.5 Fluxo de release sugerido (a cada deploy)
```bash
pip install -r project_root/requirements.txt
cd project_root
python manage.py migrate --noinput
python manage.py collectstatic --noinput
# reiniciar o serviço gunicorn
```

---

## 6. Requisitos recomendados da VM

| Recurso | Recomendação |
|---|---|
| SO | **Linux (Ubuntu 22.04+)** — evita o problema do Gunicorn no Windows |
| Python | **3.12+** |
| CPU / RAM | 1 vCPU / **2 GB RAM** (confortável); mínimo ~1 GB |
| Disco | ~2 GB (app + venv + estáticos) |
| Rede — **saída** | HTTPS **443** (Supabase REST/Storage, CDNs de front) e **5432/6543** (Supabase Postgres pooler). **Confirmar liberação no firewall.** Opcional: 6379 se Redis externo |
| Rede — **entrada** | 80/443 (nginx) → Gunicorn em `$PORT` interno |
| Serviços de apoio | (Opcional) Redis 7 se quiser Celery assíncrono; servidor SMTP para e-mails |
| Processo | Gerenciar Gunicorn/Celery via **systemd** (ou supervisor); nginx como reverse proxy + TLS |

---

## 7. Checklist de subida na VM

- [ ] VM Linux com Python 3.12+.
- [ ] Firewall: saídas 443 e 5432/6543 (Supabase) liberadas; entradas 80/443.
- [ ] `git clone` do repositório; `python3.12 -m venv .venv`; `pip install -r project_root/requirements.txt`.
- [ ] Variáveis de ambiente definidas (seção 4), com **`DJANGO_SETTINGS_MODULE=config.settings.production`** e `DEBUG=False`.
- [ ] `SECRET_KEY` forte e único; `ALLOWED_HOSTS` com o domínio real.
- [ ] `DATABASE_URL` do Supabase válido (testar conexão).
- [ ] `python manage.py migrate` e `collectstatic` sem erros.
- [ ] Gunicorn sob systemd; nginx com TLS na frente.
- [ ] (Opcional) Redis + `REDIS_URL` + worker Celery.
- [ ] SMTP configurado e testado (reset de senha envia e-mail).
- [ ] Acesso HTTPS ao domínio retorna a tela de login.

---

*Fontes no repositório:* `project_root/requirements.txt`, `project_root/config/settings/*.py`,
`project_root/config/{wsgi,celery}.py`, `Procfile`, `render.yaml`, `project_root/.env.example`.
