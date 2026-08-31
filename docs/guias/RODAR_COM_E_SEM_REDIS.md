# Guia: Rodar o HARPIA-DESUP **com** e **sem** Redis/Celery

Este mini tutorial mostra como executar o projeto em **dois modos** e como **confirmar** qual está ativo. Serve para validar que o sistema funciona tanto sem infraestrutura extra (dev rápido) quanto com Redis/Celery reais (assíncrono).

> **Como o projeto decide o modo?**
> Tudo depende da variável `REDIS_URL` no `.env` (lida em `config/settings/base.py`):
> - `REDIS_URL` **ausente/comentado** → cache `LocMemCache` (memória) + Celery **eager** (síncrono, sem broker).
> - `REDIS_URL` **definido** → cache `RedisCache` + Celery usa Redis como broker/result backend.
>
> Regra no código: `CELERY_TASK_ALWAYS_EAGER = not bool(REDIS_URL)`.

Pré-requisitos comuns aos dois modos:
- `.venv` ativado e dependências instaladas.
- PostgreSQL local rodando e `.env` com as variáveis `DB_*` corretas.
- Comandos executados dentro de `project_root/`.

---

## 🟢 Modo A — SEM Redis/Celery (padrão recomendado para dev)

Ideal para desenvolver e testar a aplicação web rapidamente. Não precisa instalar nada além do Postgres.

### 1. Ajuste o `.env`
Deixe a linha do Redis **comentada** (estado atual do projeto):

```env
# ----------- REDIS (OPTIONAL) -----------
# REDIS_URL=redis://localhost:6379/0

# ----------- CELERY -----------
# CELERY_BROKER_URL=redis://localhost:6379/0
# CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 2. Suba o servidor
```powershell
python manage.py runserver 0.0.0.0:8000
```

Pronto. **Não é preciso** subir Redis nem worker Celery. As tasks (ex.: envio de e-mail) rodam de forma síncrona, no próprio processo.

### 3. Confirme que está no modo memória
```powershell
python manage.py shell -c "from django.conf import settings; print(settings.CACHES['default']['BACKEND']); print('EAGER =', settings.CELERY_TASK_ALWAYS_EAGER)"
```
Saída esperada:
```
django.core.cache.backends.locmem.LocMemCache
EAGER = True
```

### 4. Teste o login
Acesse `http://localhost:8000/login/` e entre com um usuário válido, por exemplo:
- `estagio.analista2@desup.faetec.rj.gov.br` / `Faetec@123`

O login deve funcionar normalmente (sem erro 500).

---

## 🔵 Modo B — COM Redis/Celery (assíncrono real)

Use para validar cache compartilhado e processamento assíncrono de tasks.

### 1. Tenha um Redis rodando em `localhost:6379`
No Windows, escolha **uma** opção:
- **Docker** (mais simples):
  ```powershell
  docker run -d --name harpia-redis -p 6379:6379 redis:7
  ```
- **WSL2:** `sudo apt install redis-server && sudo service redis-server start`
- **Memurai** (Redis nativo para Windows): instale e inicie o serviço.

Verifique se responde:
```powershell
docker exec -it harpia-redis redis-cli ping   # deve responder: PONG
```

### 2. Ative o Redis no `.env`
Descomente as três linhas:

```env
# ----------- REDIS (OPTIONAL) -----------
REDIS_URL=redis://localhost:6379/0

# ----------- CELERY -----------
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 3. Confirme que está no modo Redis
```powershell
python manage.py shell -c "from django.conf import settings; print(settings.CACHES['default']['BACKEND']); print('EAGER =', settings.CELERY_TASK_ALWAYS_EAGER)"
```
Saída esperada:
```
django.core.cache.backends.redis.RedisCache
EAGER = False
```

### 4. Suba o worker do Celery
Em **um terminal separado** (dentro de `project_root/`, com a `.venv` ativa):

```powershell
# IMPORTANTE no Windows: use --pool=solo
# IMPORTANTE: force o settings de desenvolvimento (celery.py usa production por padrão)
$env:DJANGO_SETTINGS_MODULE = "config.settings.development"
celery -A config worker -l info --pool=solo
```

> Por que `--pool=solo`? O pool padrão (`prefork`) não funciona bem no Windows.
> Por que `DJANGO_SETTINGS_MODULE`? O `config/celery.py` faz `setdefault(... "config.settings.production")`; sem sobrescrever, o worker tentaria usar produção (que exige `DATABASE_URL`).

### 5. Suba o servidor (outro terminal)
```powershell
python manage.py runserver 0.0.0.0:8000
```

### 6. Teste
- Faça login normalmente em `http://localhost:8000/login/`.
- Ao disparar uma ação que gere task assíncrona (ex.: e-mail de reset), observe o **log do worker Celery** recebendo e executando a task.

Ao terminar, se usou Docker:
```powershell
docker stop harpia-redis && docker rm harpia-redis
```

---

## 🧪 Comparação rápida

| Item | Modo A (sem Redis) | Modo B (com Redis) |
|---|---|---|
| `REDIS_URL` no `.env` | comentado | definido |
| Cache backend | `LocMemCache` | `RedisCache` |
| `CELERY_TASK_ALWAYS_EAGER` | `True` | `False` |
| Precisa subir Redis? | Não | Sim |
| Precisa subir worker Celery? | Não | Sim |
| Tasks | síncronas (in-process) | assíncronas (worker) |
| Uso recomendado | dev/UI do dia a dia | validar fila/assíncrono |

---

## 🛠️ Troubleshooting

- **Erro 500 no `/login/` com `ConnectionError ... 6379`:**
  O `.env` tem `REDIS_URL` definido, mas o Redis não está rodando. Suba o Redis (Modo B) **ou** comente `REDIS_URL` (Modo A).
  Obs.: a `login_view` foi endurecida para não quebrar nesse caso — mas o ideal é alinhar o `.env` com o que está de fato rodando.

- **Alterei o `.env` e nada mudou:**
  O `python-decouple` lê o `.env` na inicialização. **Reinicie o `runserver`** (e o worker Celery) após editar.

- **Worker Celery com erro de banco/`DATABASE_URL`:**
  Você esqueceu de definir `DJANGO_SETTINGS_MODULE=config.settings.development` antes do `celery -A config worker` (veja passo B.4).

- **`celery` não encontrado:**
  Ative a `.venv`. Versões esperadas: `celery 5.6.x`, `redis-py 5.3.x`.

---

## Referências
- Setup local geral: `docs/guias/SETUP_LOCAL.md`
- Guia detalhado de Redis/Celery: `docs/guias/REDIS_CELERY_SETUP.md`
- Relatório da correção que originou este guia: `docs/relatorios/relatorio_correcao_login_redis_cache.md`
