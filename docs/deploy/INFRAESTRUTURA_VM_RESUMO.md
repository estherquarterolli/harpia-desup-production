# Harpia (HARPIA-DESUP) — Deploy em VM · Referência rápida

> **Aplicação:** *Harpia* — sistema acadêmico FAETEC/DESUP. Monólito **Django** server-side + HTMX
> (sem SPA, sem build de front-end). Versão detalhada: `docs/deploy/INFRAESTRUTURA_VM.md`. · 2026-07-09

## ⚠️ 3 pontos críticos
1. **Python 3.12+** — Django 6.0.3 exige 3.12+ (dev: 3.12.10). Ignore o `3.11` do `render.yaml` (desatualizado); nele não sobe.
2. **`DJANGO_SETTINGS_MODULE=config.settings.production`** — `manage.py`/`wsgi.py` têm *fallback* para `development` (DEBUG=True). Sem essa variável, sobe inseguro.
3. **Firewall de saída** — liberar `443` e `5432/6543` (Postgres do Supabase). Foi o que travou no ambiente de dev.

## Stack & versões
| Camada | Tecnologia |
|---|---|
| Runtime | **Python 3.12+** · Django **6.0.3** |
| App server (prod) | **Gunicorn 21.2.0** → `config.wsgi:application` |
| Estáticos | **WhiteNoise 6.12.0** (manifest comprimido em prod) |
| Banco | **PostgreSQL** · psycopg2-binary 2.9.12 · dj-database-url 2.1.0 |
| Config | python-decouple 3.8 (`.env`/ambiente) |
| Async (opcional) | Celery 5.6.3 + Redis 5.3.1 |
| Admin / CORS | django-unfold 0.95.0 · django-cors-headers 4.9.0 |
| Storage | Supabase SDK 2.1.0 |
| Front-end | Tailwind / HTMX 1.9.10 / Alpine 3.x / Lucide / Phosphor / SweetAlert2 — **via CDN, sem build** |
| Porta | `$PORT` (prod) · `8000` (dev) |

> Dependências travadas em `project_root/requirements.txt`.
> Apps internos: `accounts`, `core`, `courses`, `professors`, `allocations`, `extra_curricular`.

## Serviços externos
| Serviço | Uso | Portas |
|---|---|---|
| Supabase — PostgreSQL | **Sim** (banco de produção) | 5432 / 6543 · TLS |
| Supabase — Storage | **Sim** (uploads/bucket) | HTTPS 443 |
| SMTP (e-mail) | **Sim** (reset de senha, links) | 587 / TLS (provedor) |
| Redis | **Opcional** (broker/result do Celery + cache) | 6379 |
| Docker | **Não exigido** (só nos guias de dev) | — |
| n8n | **Não usado** | — |

> Sem `REDIS_URL`, o Celery roda **síncrono** (eager) e o cache usa memória local — o app funciona normalmente.

## Variáveis de ambiente (essenciais)
```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production   # obrigatório
SECRET_KEY=<forte e único>
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com

DATABASE_URL=postgresql://USER:SENHA@HOST:5432/postgres   # sslmode é forçado

SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_KEY=<anon/public key>
SUPABASE_SERVICE_ROLE_KEY=<service role key>
SUPABASE_STORAGE_BUCKET=<nome-do-bucket>

EMAIL_HOST=smtp.seu-provedor.com
EMAIL_PORT=587
EMAIL_HOST_USER=<usuario>
EMAIL_HOST_PASSWORD=<senha>
EMAIL_USE_TLS=True

REDIS_URL=redis://HOST:6379/0        # opcional
```

## Comandos
```bash
# setup (uma vez) — Python 3.12+
python3.12 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r project_root/requirements.txt
export DJANGO_SETTINGS_MODULE=config.settings.production   # + demais variáveis

# release (a partir de project_root/)
cd project_root
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py createsuperuser        # opcional, 1ª vez

# subir (produção)
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120

# worker Celery — só se usar Redis
celery -A config worker -l info
```

## VM recomendada
- **SO:** Linux (Ubuntu 22.04+). Gunicorn **não roda em Windows nativo** — use WSL ou `waitress`.
- **Recursos:** 1 vCPU · **2 GB RAM** · ~2 GB disco.
- **Rede:** saída `443` + `5432/6543`; entrada `80/443` (nginx + TLS → Gunicorn em `$PORT`).
- **Processo:** Gunicorn/Celery via **systemd**; nginx como reverse proxy.

---
*Fontes:* `project_root/requirements.txt`, `config/settings/*.py`, `config/{wsgi,celery}.py`, `Procfile`, `render.yaml`, `project_root/.env.example`.
