# 🚀 Setup Local - AllocGest-DESUP

Guia rápido para configurar o projeto localmente antes de fazer deploy.

## 📋 Requisitos

- Python 3.11+
- PostgreSQL 12+ (ou use SQLite para desenvolvimento)
- Redis (opcional, pode usar cache local)
- Git

## 🔧 Passo 1: Clonar e instalar

```bash
# Clonar repositório
git clone https://github.com/estherquarterolli/AllocGest-DESUP.git
cd AllocGest-DESUP

# Criar virtual environment
python -m venv venv

# Ativar venv
# No Windows:
venv\Scripts\activate
# No Mac/Linux:
source venv/bin/activate

# Instalar dependências
pip install -r project_root/requirements.txt
```

## 🗂️ Passo 2: Configurar variáveis de ambiente

```bash
cd project_root

# Copiar arquivo exemplo
cp .env.example .env

# Editar .env (não commitar este arquivo!)
```

Deixar com valores locais:
```env
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=django.db.backends.postgresql
DB_NAME=harpia_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

## 🗄️ Passo 3: Preparar banco de dados

### Opção A: PostgreSQL local

```bash
# Criar banco de dados
psql -U postgres -c "CREATE DATABASE harpia_db;"

# Ou editar DB_NAME em .env para outro nome
```

### Opção B: SQLite (mais fácil para desenvolvimento)

```bash
# Django criará automaticamente
# Apenas mude em .env:
DB_ENGINE=django.db.backends.sqlite3
# (DB_NAME será ignorado, usará db.sqlite3)
```

## 🔄 Passo 4: Executar migrations

```bash
cd project_root

# Aplicar migrations
python manage.py migrate

# Criar superuser (admin)
python manage.py createsuperuser

# Email: seu-email@exemplo.com
# Senha: Faetec@123 (depois mude no primeiro login)
```

## ▶️ Passo 5: Iniciar servidor

```bash
python manage.py runserver
```

Acessar em: **http://localhost:8000**

Admin em: **http://localhost:8000/admin**

## 🧪 Passo 6: Testar integrações (Opcional)

```bash
# Verificar configuração do Supabase (quando estiver pronto)
cd project_root
python check_supabase_setup.py
```

## 📝 Estrutura do projeto

```
AllocGest-DESUP/
├── project_root/           # Django app
│   ├── apps/              # Django apps
│   ├── config/            # Configurações Django
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS
│   ├── manage.py
│   ├── requirements.txt
│   └── .env              # ⚠️ NÃO COMMITAR
├── DEPLOYMENT_GUIDE.md    # Deploy para Render + Supabase
├── SETUP_LOCAL.md         # Este arquivo
├── Procfile              # Configuração para Render
└── render.yaml           # Alternativa para Render
```

## 🚀 Próximos passos

1. **Desenvolvimento local:** Faça mudanças e teste
2. **Testar:** Rode testes (se houver)
3. **Deploy:** Siga [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

## 🆘 Problemas comuns

### "ModuleNotFoundError: No module named 'apps'"

```bash
# Certifique-se de estar no diretório correto
cd project_root
```

### "Database connection refused"

```bash
# Verificar se PostgreSQL está rodando
# Windows: Services → postgresql
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql
```

### Porta 8000 já em uso

```bash
python manage.py runserver 8001
```

## 📚 Documentação

- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Deploy completo
- [README.md](./README.md) - Visão geral do projeto

---

Pronto! 🎉 Você deve estar rodando a aplicação localmente agora.
