# Harpia DESUP

Sistema Django para gestão de professores, matrizes curriculares, alocações e
pendências extracurriculares da DESUP.

## Estrutura necessária

- `project_root/apps/`: aplicações Django e migrações.
- `project_root/config/`: configurações, URLs, WSGI, ASGI e Celery.
- `project_root/templates/`: templates do sistema.
- `project_root/static/`: CSS, JavaScript e imagens-fonte.
- `project_root/locale/`: traduções compiladas.
- `project_root/manage.py`: comandos Django.
- `project_root/requirements.txt`: dependências Python.
- `project_root/vercel.json`, `render.yaml` e `Procfile`: deploy.
- `tailwind.config.js`, `package.json` e `package-lock.json`: geração do CSS.

`project_root/staticfiles/` e `node_modules/` são artefatos gerados e não devem
ser versionados.

## Desenvolvimento local

```powershell
cd project_root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Preencha o `.env` com as credenciais do ambiente antes de iniciar.

## CSS

O navegador usa o CSS Tailwind já compilado. Após alterar classes nos templates
ou formulários, execute na raiz do repositório:

```powershell
npm ci
npm run build:css
```

O arquivo gerado é `project_root/static/css/tailwind.min.css`.

## Testes

```powershell
cd project_root
python manage.py check
python manage.py test --settings=config.settings._tmp_test
python manage.py makemigrations --check --dry-run
```

## Produção

Use `config.settings.production`. O deploy deve executar `collectstatic` e
`migrate`; as configurações versionadas já incluem essas etapas para Vercel,
Render e processos compatíveis com o `Procfile`.
