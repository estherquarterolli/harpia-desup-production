# 🚀 Guia de Deployment: Supabase + Vercel

Guia para fazer deploy da aplicação AllocGest-DESUP usando Supabase (banco de dados + storage) e Vercel (app Django).

> Este projeto também suporta deploy via **Render + MySQL** (ver `Procfile` e `render.yaml` na raiz do repositório) e via **HostGator + MySQL** (ver
> [`docs/guias/HOSTGATOR_MYSQL_DEPLOYMENT.md`](/D:/Repositorios/HARPIA-DESUP/docs/guias/HOSTGATOR_MYSQL_DEPLOYMENT.md)). Escolha o caminho que corresponde ao ambiente de produção atual.

---

## 📋 Pré-requisitos

- [x] Conta GitHub com repositório `AllocGest-DESUP`
- [x] Conta Vercel (https://vercel.com) e conta Supabase (https://supabase.com)
- [x] Python 3.11+ instalado localmente
- [x] Node.js (para usar `npx vercel` / `npx supabase`)
- [x] Git configurado

---

## ✅ Passo 1: Configurar Supabase (Gratuito)

### 1.1 Criar conta e projeto

1. Acesse https://supabase.com e faça login (recomendado via GitHub)
2. "New project" → **Name:** `allocgest` → salve a senha do banco → **Region:** a mais próxima
3. Aguarde ~3 min para criação

### 1.2 Anotar credenciais

Em Settings → API:

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...          # anon key
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

Em Settings → Database → Connection string, use a opção **Transaction pooler** (porta 6543) — é a mais adequada para conexões serverless do Vercel:

```env
DATABASE_URL=postgresql://postgres.xxxxx:SENHA@aws-0-xxx.pooler.supabase.com:6543/postgres
```

### 1.3 (Mais tarde, se for usar upload de arquivo) Criar bucket de Storage

O projeto já tem um backend de storage pronto (`apps/core/storage.py`), que liga sozinho assim que `SUPABASE_URL`/`SUPABASE_KEY` estiverem configurados — sem precisar de credenciais S3 separadas. Quando for usar upload de arquivo (ex.: comprovante de ausência) em produção, crie o bucket em Dashboard → Storage → "New bucket", nome `allocgest-storage`. Não é necessário para o app funcionar — pode ser feito depois.

### 1.4 (Opcional) CLI do Supabase

```bash
npx supabase login
npx supabase link --project-ref xxxxx
```

O schema do banco **não** é gerenciado pelo Supabase CLI — quem cuida disso são as migrations do Django (`python manage.py migrate`), que rodam automaticamente no build do Vercel (Passo 4). O link do CLI serve só para conveniência de inspeção via terminal.

---

## ✅ Passo 2: Preparar código local

```bash
cd project_root
pip install -r requirements.txt
cp .env.example .env
```

Editar `.env` com os valores locais (Postgres local ou SQLite) — ver `SETUP_LOCAL.md`.

Testar localmente:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## ✅ Passo 3: Preparar para Deploy

### 3.1 Gerar SECRET_KEY de produção

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3.2 Commit das mudanças

```bash
git add -A
git commit -m "feat: deploy config para Vercel + Supabase"
git push origin main
```

---

## ✅ Passo 4: Deploy no Vercel (Gratuito)

O projeto já vem com `project_root/vercel.json`, que configura a function e roda `python manage.py migrate --noinput` a cada build (via `buildCommand`).

### 4.1 Instalar CLI e autenticar

```bash
npx vercel login
```

### 4.2 Linkar o projeto

Rode a partir da raiz do repo e, quando perguntado o **Root Directory**, informe `project_root`:

```bash
npx vercel link
```

### 4.3 Configurar variáveis de ambiente

```bash
npx vercel env add DJANGO_SETTINGS_MODULE production
npx vercel env add SECRET_KEY production
npx vercel env add ALLOWED_HOSTS production
npx vercel env add DATABASE_URL production
npx vercel env add SUPABASE_URL production
npx vercel env add SUPABASE_KEY production
npx vercel env add SUPABASE_SERVICE_ROLE_KEY production
```

Para `DJANGO_SETTINGS_MODULE`, use `config.settings.production`.

> **Não** configure `REDIS_URL` nem `CELERY_BROKER_URL` — sem elas, `CELERY_TASK_ALWAYS_EAGER` fica `True` automaticamente e as tasks (ex.: envio de e-mail) rodam de forma síncrona, sem precisar de worker/broker no Vercel.

Repita para o ambiente `preview` se quiser testar em PRs antes de produção.

### 4.4 Deploy

```bash
npx vercel deploy
```

Isso gera uma **preview URL** — teste tudo antes de ir pra produção. Quando estiver validado:

```bash
npx vercel deploy --prod
```

---

## ✅ Passo 5: Verificar Deployment

- App: `https://<seu-projeto>.vercel.app`
- Admin: `https://<seu-projeto>.vercel.app/admin`
- Teste login, navegação e um upload de arquivo (comprovante de ausência) para validar o Supabase Storage.
- Logs: `npx vercel logs <url-do-deploy>` ou no dashboard do Vercel.

---

## 🔧 Troubleshooting

### "ModuleNotFoundError" no build

Confirme que o Root Directory do projeto Vercel está apontando para `project_root` (Settings → General → Root Directory).

### "DATABASE connection refused" / erro de SSL

- Verificar `DATABASE_URL` (usar o pooler de **Transaction mode**, porta 6543)
- Supabase → Settings → Database → confirmar que a conexão pooled está habilitada

### Upload de arquivo falha

Confirme que `SUPABASE_URL`/`SUPABASE_KEY` estão setados no Vercel e que o bucket `allocgest-storage` existe no Supabase (Storage → New bucket).

### "CSRF verification failed" / 403 no login

Confirme que o domínio usado está em `ALLOWED_HOSTS` — o domínio `*.vercel.app` de cada deploy é adicionado automaticamente via `VERCEL_URL`, mas um domínio customizado precisa estar em `ALLOWED_HOSTS`.

---

## 📊 Custos

| Serviço | Tier | Custo |
|---------|------|-------|
| Supabase | Free | $0 |
| Vercel | Hobby | $0 |
| **Total** | | **$0/mês** ✅ |

---

## 🎯 Próximos passos (Opcional)

1. **Custom domain:** Vercel → Project → Settings → Domains
2. **CI/CD:** todo push no GitHub já gera preview deploy automático no Vercel
3. **Monitoramento:** Sentry, Vercel Analytics

---

## 🆘 Suporte

- **Vercel Docs (Django):** https://vercel.com/docs/frameworks/full-stack/django
- **Supabase Docs:** https://supabase.io/docs
- **Django Docs:** https://docs.djangoproject.com

---

Boa sorte! 🚀
