# Migração SQLite3 → Supabase (PostgreSQL)

Este guia mostra como migrar seus dados do SQLite3 local para Supabase.

---

## 📋 Pré-requisitos

✅ Conta Supabase criada  
✅ Projeto Supabase com DATABASE_URL configurada no `.env`  
✅ Banco SQLite3 local em `project_root/db.sqlite3`  

---

## 🚀 Passos de Migração

### Passo 1: Atualizar `.env`

Certifique-se de ter as credenciais Supabase:

```env
DATABASE_URL=postgresql://postgres:SUA_SENHA@db.qmzljpiucuuxxcrxlayv.supabase.co:5432/postgres?sslmode=require
SUPABASE_URL=https://qmzljpiucuuxxcrxlayv.supabase.co
SUPABASE_KEY=seu_key_aqui
```

### Passo 2: Instalar dependência PostgreSQL

```bash
cd project_root
python -m pip install psycopg2-binary
```

### Passo 3: Rodar o script de migração

```bash
cd project_root
python migrate_to_supabase.py
```

**Esperado:**
```
============================================================
SQLite3 → Supabase (PostgreSQL) Migration
============================================================

[1] Connecting to databases...
✓ Connected to Supabase

[2] Getting tables from SQLite...
✓ Found 34 tables

[3] Creating tables in Supabase...
✓ Created table: accounts_user
✓ Created table: accounts_passwordresetrequest
... (todas as tabelas)

[4] Copying data from SQLite to Supabase...
✓ Copied 10 rows from accounts_user
✓ Copied 8 rows from core_unidade
... (todos os dados)

============================================================
✓ Migration complete!
✓ Total rows copied: 2847
============================================================
```

### Passo 4: Marcar migrations como aplicadas

```bash
python manage.py migrate --fake-initial
```

Isso marca todas as migrations como já aplicadas, já que o schema já existe no Supabase.

### Passo 5: Testar a conexão

```bash
python manage.py shell
>>> from django.db import connection
>>> connection.ensure_connection()
>>> print("✓ Connected to Supabase!")
>>> exit()
```

### Passo 6: Testar a aplicação

```bash
python manage.py runserver
```

Acesse http://localhost:8000/admin e faça login com uma das contas migradas.

---

## 🔍 Verificar dados no Supabase

Se quiser ver os dados no dashboard do Supabase:

1. Vá para https://supabase.com
2. Abra seu projeto
3. Clique em **SQL Editor**
4. Execute:
   ```sql
   SELECT COUNT(*) as total FROM accounts_user;
   SELECT COUNT(*) as total FROM courses_course;
   ```

---

## ⚠️ Troubleshooting

### Erro: "Database connection refused"

```
Verifique se a DATABASE_URL está correta no .env
Copie de: Supabase → Settings → Database → Connection String → URI
```

### Erro: "Table already exists"

Limpe as tabelas no Supabase SQL Editor:

```sql
DROP TABLE IF EXISTS courses_matrixcomponent CASCADE;
DROP TABLE IF EXISTS courses_curricularcomponent CASCADE;
-- ... (delete all tables)
```

Depois rode novamente: `python migrate_to_supabase.py`

### Erro: "Permission denied"

O SERVICE_ROLE_KEY pode ter permissões limitadas. Tente com a credencial de admin:

```bash
# Use a senha do admin Supabase (aquela que você criou)
# Em vez do ANON_KEY
```

---

## ✅ Depois da migração

1. **Backup local** (opcional):
   ```bash
   cp db.sqlite3 db.sqlite3.backup
   ```

2. **Commit das mudanças**:
   ```bash
   git add migrate_to_supabase.py
   git commit -m "feat: add Supabase migration script"
   git push
   ```

3. **Atualizar variáveis Render.com**:
   - Verificar que `DATABASE_URL` está correto
   - Fazer novo deploy

4. **Remover dependência SQLite** (opcional):
   - Pode manter `db.sqlite3` como backup
   - Ou deletar se tiver certeza que tudo funciona

---

## 🎯 Resumo

| Passo | O quê | Comando |
|-------|-------|---------|
| 1 | Configurar .env | Adicionar `DATABASE_URL` |
| 2 | Instalar deps | `pip install psycopg2-binary` |
| 3 | Migrar dados | `python migrate_to_supabase.py` |
| 4 | Marcar migrations | `python manage.py migrate --fake-initial` |
| 5 | Testar | `python manage.py runserver` |
| 6 | Deploy | Manual Deploy no Render |

---

## 🆘 Precisando de ajuda?

Se algo der errado:

1. Verifique os logs: `python manage.py migrate --fake-initial --verbosity 2`
2. Teste a conexão diretamente: `python manage.py shell`
3. Confirme os dados no Supabase SQL Editor

Boa sorte! 🚀
