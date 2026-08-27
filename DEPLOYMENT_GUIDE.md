# 🚀 Guia de Deployment: Supabase + Render.com

Este guia detalhado para fazer deploy da aplicação AllocGest-DESUP totalmente **GRÁTIS** usando Supabase e Render.com.

---

## 📋 Pré-requisitos

- [x] Conta GitHub com repositório `AllocGest-DESUP`
- [x] Python 3.11+ instalado localmente
- [x] Git configurado

---

## ✅ Passo 1: Configurar Supabase (Gratuito)

### 1.1 Criar conta Supabase
1. Acesse https://supabase.com
2. Clique em "Sign Up"
3. Faça login com GitHub (recomendado)

### 1.2 Criar novo projeto
1. Click em "New project"
2. **Name:** `allocgest`
3. **Database password:** Salve uma senha forte
4. **Region:** Brazil (São Paulo) se disponível, senão a mais próxima
5. Wait ~3 min para criação

### 1.3 Anotar credenciais
Após criação, você verá:
- **Project URL:** `https://xxxxx.supabase.co`
- **Anon key:** Copiar
- **Service role key:** Copiar (em Settings → API)

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

### 1.4 Migrar schema do PostgreSQL local

No Supabase Dashboard → SQL Editor:

```sql
-- Executar migrations do Django
-- Isso será feito automaticamente no deploy via:
-- python manage.py migrate
```

**Alternativa:** Se quiser migrar dados locais primeiro:

```bash
cd project_root

# Exportar schema do local
pg_dump -s -U postgres -h localhost harpia_db > schema.sql

# Depois copiar conteúdo do schema.sql e executar
# na SQL Editor do Supabase
```

### 1.5 Criar Storage Bucket

1. Na Dashboard → Storage
2. Click "New bucket"
3. **Name:** `allocgest-storage`
4. **Public:** False (ajuste conforme necessário)
5. Confirm

---

## ✅ Passo 2: Preparar código local

### 2.1 Instalar dependências

```bash
cd project_root
pip install -r requirements.txt
```

### 2.2 Configurar `.env` local

```bash
cp .env.example .env
```

Editar `.env`:

```env
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Local PostgreSQL (para desenvolvimento)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=harpia_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Supabase (comentado por enquanto)
# DATABASE_URL=postgresql://postgres:xxxxx@db.supabase.co:5432/postgres
# SUPABASE_URL=https://xxxxx.supabase.co
# SUPABASE_KEY=eyJhbGc...
# SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

### 2.3 Testar localmente

```bash
cd project_root

# Rodar migrations
python manage.py migrate

# Criar superuser (DESUP admin)
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

Acessar em `http://localhost:8000`

---

## ✅ Passo 3: Preparar para Deploy

### 3.1 Gerar nova SECRET_KEY

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiar saída (será usada no Render)

### 3.2 Commit das mudanças

```bash
cd ..
git add -A
git commit -m "feat: add Supabase and Render configuration"
git push origin feat/matriz-curricular
```

### 3.3 Merge para main (opcional antes de deploy)

```bash
# Se quiser fazer deploy direto de feat/matriz-curricular, pode pular isso
# Senão:
git checkout main
git pull origin main
git merge feat/matriz-curricular
git push origin main
```

---

## ✅ Passo 4: Deploy em Render.com (Gratuito)

### 4.1 Criar conta Render
1. Acesse https://render.com
2. Sign up com GitHub
3. Autorizar acesso ao repositório

### 4.2 Criar novo Web Service
1. Dashboard → "New +" → "Web Service"
2. Selecionar repositório `AllocGest-DESUP`

### 4.3 Configurar Web Service

**Name:** `allocgest-api`

**Runtime:** `Python`

**Build Command:**
```bash
pip install --upgrade pip && pip install -r project_root/requirements.txt && cd project_root && python manage.py migrate && python manage.py collectstatic --noinput
```

**Start Command:**
```bash
cd project_root && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

**Region:** São Paulo (ou mais próximo)

**Plan:** Free (com sleep após 15 min inatividade)

### 4.4 Adicionar variáveis de ambiente

No Render Dashboard → Web Service → "Environment":

```env
DEBUG=False
SECRET_KEY=<cole-a-chave-gerada-em-3.1>
ALLOWED_HOSTS=allocgest-api.onrender.com
DJANGO_SETTINGS_MODULE=config.settings.production
DATABASE_URL=postgresql://postgres:<senha>@db.<seu-supabase>.supabase.co:5432/postgres
SUPABASE_URL=https://<seu-supabase>.supabase.co
SUPABASE_KEY=<sua-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<sua-service-role-key>
PYTHON_VERSION=3.11
```

**Onde encontrar DATABASE_URL:**
- Supabase Dashboard → Settings → Database
- Connection String → URI (escolher "Application default")

### 4.5 Deploy

Click em "Create Web Service"

⏳ Render vai:
1. Instalar dependências (~2 min)
2. Rodar migrations (~1 min)
3. Fazer collectstatic (~30 seg)
4. Iniciar aplicação (~30 seg)

**Total:** ~5 minutos

---

## ✅ Passo 5: Verificar Deployment

### 5.1 Acessar aplicação

Seu site estará em:
```
https://allocgest-api.onrender.com
```

### 5.2 Acessar admin

```
https://allocgest-api.onrender.com/admin
```

Use credenciais do superuser criado (ou resete password se necessário)

### 5.3 Monitorar logs

No Render Dashboard → Logs:
```
Você verá logs em tempo real do deploy
```

---

## ⚠️ Comportamento do Render Free Tier

- ✅ **Gratuito:** $0/mês
- ⏰ **Sleep:** Aplicação entra em sleep após 15 min sem requisições
- 🚀 **Wake-up:** Primeira requisição após sleep leva ~30s
- 📈 **Horas/mês:** Máximo 750 horas (cobre ~31 dias)

**Solução para evitar sleep:**
- Ping a cada 14 minutos via cron job externo
- Ou upgrade para plano pago

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'supabase'"

```bash
# No Render, rodar build command correto que instala requirements.txt
```

### "DATABASE connection refused"

- Verificar `DATABASE_URL` está correto
- Verificar IP do Render está autorizado no Supabase

Supabase → Settings → Database → SSL → Allow all connections

### "ALLOWED_HOSTS error"

Adicionar seu domínio Render em `ALLOWED_HOSTS`:
```env
ALLOWED_HOSTS=allocgest-api.onrender.com
```

### Aplicação dorme muito

Render Free vai dormir. Upgrade para pago ou aceite a latência inicial.

---

## 📊 Custos

| Serviço | Tier | Custo |
|---------|------|-------|
| Supabase | Free | $0 |
| Render | Free | $0 |
| Domain (opcional) | - | $0 (usar .onrender.com) |
| **Total** | | **$0/mês** ✅ |

---

## 🎯 Próximos passos (Opcional)

1. **Custom domain:** Mapear domínio próprio
   - Render → Settings → Custom Domain
   - Atualizar DNS CNAME para Render

2. **CI/CD melhorado:** GitHub Actions
   - Testes antes de deploy
   - Deploy automático em push

3. **Monitoramento:** Sentry
   - Rastrear erros em produção

4. **Upgrade:**
   - Render Starter: $7/mês (sem sleep)
   - Supabase Pro: $25/mês (1GB storage)

---

## 🆘 Suporte

- **Render Docs:** https://render.com/docs
- **Supabase Docs:** https://supabase.io/docs
- **Django Docs:** https://docs.djangoproject.com
- **Este repo:** Problemas e issues no GitHub

---

Boa sorte! 🚀
