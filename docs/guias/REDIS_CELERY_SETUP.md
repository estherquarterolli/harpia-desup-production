# Tutorial: Rodar e Testar o AllocGest-DESUP com Redis e Celery

Este tutorial assume que você quer executar o projeto normalmente no desenvolvimento local e também validar o modo com Redis/Celery.

## 1. O que foi preparado

- `Redis` pode funcionar como cache compartilhado e broker do Celery.
- Se `REDIS_URL` não estiver definido, o projeto continua funcionando com `LocMemCache`.
- O Celery foi configurado para usar `config` como app principal.
- As tasks de e-mail foram extraídas para processamento assíncrono.

## 2. Pré-requisitos

- Python instalado
- Dependências do projeto
- PostgreSQL disponível se você for usar o banco principal
- Redis instalado se quiser testar o modo assíncrono real

## 3. Variáveis de ambiente

No arquivo `.env`, adicione ou confirme:

```env
SECRET_KEY=uma-chave-secreta
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=dev@prisma.local
```

Se você não tiver Redis no momento, pode omitir `REDIS_URL`. Nesse caso:

- o cache usa memória local;
- o Celery roda em modo eager no desenvolvimento;
- o projeto continua funcionando normalmente.

## 4. Instalar dependências

Na raiz de `project_root`:

```bash
pip install -r requirements.txt
```

## 5. Preparar banco

```bash
python manage.py migrate
python manage.py createsuperuser
```

Se o projeto já tiver dados seedados no seu ambiente, você pode reutilizar o banco atual.

## 6. Rodar sem Redis

Se você quer apenas subir o sistema localmente:

```bash
python manage.py runserver
```

Nesse modo:

- login com bloqueio por tentativas continua funcionando localmente;
- e-mails podem ser impressos no console se o backend estiver em console;
- tasks assíncronas ficam em modo eager.

## 7. Rodar com Redis

### 7.1 Iniciar o Redis

Suba o serviço Redis na porta `6379`.

Exemplos comuns:

- Docker:

```bash
docker run --name prisma-redis -p 6379:6379 redis:7
```

- Instalação local: use o serviço Redis do seu ambiente.

### 7.2 Subir o worker do Celery

Em outro terminal, dentro de `project_root`:

```bash
celery -A config worker -l info
```

### 7.3 Subir o Django

```bash
python manage.py runserver
```

## 8. O que testar

### 8.1 Login com bloqueio

1. Acesse a tela de login.
2. Faça 5 tentativas inválidas.
3. Confirme que o bloqueio aparece por 15 minutos.

Observação:
- sem Redis, o bloqueio funciona apenas no processo atual;
- com Redis, o bloqueio é compartilhado entre workers/instâncias.

### 8.2 Troca de senha

1. Faça o fluxo de troca de senha.
2. Confirme que a solicitação é criada.
3. Verifique se o e-mail é enfileirado.
4. Com `EMAIL_BACKEND` em console, confira a saída no terminal.

### 8.3 Reset de senha

1. Abra o fluxo de recuperação.
2. Solicite um reset.
3. Verifique se a notificação interna foi criada.
4. Confirme o disparo do e-mail no console ou no servidor SMTP configurado.

### 8.4 Chamado de alteração

1. Tente editar algo fora da janela de entrega.
2. Confirme que a notificação foi criada.
3. Verifique se o e-mail para DESUP foi enfileirado.

## 9. Checagens rápidas de saúde

```bash
python -m py_compile project_root/config/celery.py project_root/config/settings/base.py project_root/apps/core/tasks.py project_root/apps/core/services.py project_root/apps/accounts/views.py
```

Se quiser validar o worker manualmente:

```bash
celery -A config inspect ping
```

## 10. Problemas comuns

### Redis não responde

- confirme se o serviço está ativo na porta `6379`;
- confira `REDIS_URL` no `.env`;
- valide se o Docker container está rodando, se esse for o caso.

### Worker não consome tasks

- verifique se o worker foi iniciado com `celery -A config worker -l info`;
- confirme se o Django está apontando para o mesmo `REDIS_URL`;
- veja se `CELERY_TASK_ALWAYS_EAGER` não está forçando execução local.

### E-mail não dispara

- confira `EMAIL_BACKEND`;
- se estiver em console, o e-mail vai aparecer no terminal, não será enviado externamente;
- verifique logs do worker do Celery.

### `UnicodeDecodeError` ao iniciar o `runserver`

Se o erro aparecer ao conectar no PostgreSQL, ele normalmente não está relacionado ao Redis/Celery.

Verifique:

- se o arquivo `.env` está salvo em UTF-8;
- se não há variáveis `DB_*` com caractere estranho em outra sessão do terminal;
- se o banco PostgreSQL local existe e aceita conexão com os valores de `DB_NAME`, `DB_USER`, `DB_PASSWORD` e `DB_HOST`;
- se o cluster PostgreSQL foi criado com locale compatível com UTF-8.

Se quiser isolar rapidamente, teste a conexão direta no Python com os mesmos parâmetros do `.env`.

## 11. Fluxo recomendado de uso

1. Desenvolva localmente sem Redis se quiser simplicidade.
2. Ative Redis quando quiser testar cache compartilhado e execução assíncrona real.
3. Antes de produção, rode o projeto com:
   - `REDIS_URL`
   - worker do Celery
   - backend de e-mail de produção

## 12. Próximos passos possíveis

- mover notificações internas para Celery;
- criar task para exportações grandes;
- criar jobs agendados para limpeza de pendências e monitoramento.
