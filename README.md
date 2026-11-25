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

A configuração e o fluxo da Central de Ajuda estão em [doc/central-ajuda.md](doc/central-ajuda.md).
O suporte usa a caixa de `DEFAULT_FROM_EMAIL` como destino, com a configuração de
e-mail existente do Django. `HARPIA_SUPPORT_EMAIL` é opcional para um destino diferente.

Use `config.settings.production`. O deploy deve executar `collectstatic` e
`migrate`; as configurações versionadas já incluem essas etapas para Vercel,
Render e processos compatíveis com o `Procfile`.

### Comunicação por e-mail

No admin, **Configurações do Sistema → Comunicação** permite à TI gerenciar o
recebimento e o silenciamento pessoal dos usuários DESUP e da própria conta,
além de silenciar unidades globalmente. A tela permanece dentro do admin.

No site, o menu do usuário oferece **Configurações**, logo abaixo de **Meu Perfil**,
com o acesso à alteração de senha e, para DESUP/TI, preferências pessoais de
comunicação. Cada usuário DESUP altera somente as próprias preferências; o
silenciamento pessoal afeta apenas seu endereço. Administrador e usuário editam
a mesma preferência: vale a última alteração salva, sem impedir a reativação
pelo próprio usuário. O silenciamento global, exclusivo da TI, sempre prevalece.

Por padrão, os avisos à DESUP vão somente para
`harpia@desup.faetec.rj.gov.br`. Novas contas não são incluídas automaticamente.
Silenciar globalmente uma unidade impede o e-mail à caixa principal e às pessoas inscritas,
mas mantém solicitações, notificações no sino e registros no sistema. E-mails de
acesso/senha, suporte, erros do servidor e respostas às unidades seguem os fluxos
existentes. O remetente continua vindo de `DEFAULT_FROM_EMAIL`.

A migração `core.0022_comunicacao_email` acrescenta a configuração e a unidade
de origem das notificações; não altera períodos de matrizes nem reenvia avisos
históricos. `core.0023_preferencias_comunicacao` transfere a seleção antiga de
destinatários para as preferências pessoais, preservando os silenciamentos globais.
Contas sem preferência permanecem com recebimento pessoal desativado por padrão.
Novas matrizes e importações usam “1º Período” a “8º Período”. A edição
e a cópia preservam o texto dos períodos legados, inclusive “1o periodo” e
“1º Semestre”; uma nova escolha no seletor grava o padrão atual. A reimportação
SQL preserva o período dos vínculos já existentes.

Antes da produção, valide em banco isolado com e-mails capturados localmente:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
$env:CELERY_TASK_ALWAYS_EAGER = 'true'
python manage.py test apps.core.tests_communication apps.core.tests_communication_migration apps.courses.tests_periods --settings=config.settings.development
```

Na raiz do repositório, `node --test project_root/apps/courses/tests_period_copy.cjs`
verifica também a seleção de períodos na cópia feita pelo navegador.

Na implantação, aplique as migrações e atualize também os workers Celery, quando
existirem, para reconhecer `send_notification_email_task`. Tarefas antigas de
notificação já enfileiradas no `send_email_task` carregam os destinatários antigos;
devem ser identificadas e canceladas antes da troca, preservando tarefas de
acesso/senha. Os novos avisos conferem a política atual antes de enviar e em
cada retentativa. Logs distinguem silenciamento, enfileiramento, aceitação pelo
serviço e falha; aceitação pelo serviço não confirma entrega na caixa postal.

A migração `extra_curricular.0008_regularizar_sei_legado` corrige SEIs antigos
inválidos que impediam a exclusão de usuários no admin. Antes de deixar o SEI
como não informado, preserva seu valor original e os identificadores da pendência
na Auditoria Global, com a ação `SEI_LEGADO_INVALIDO`. O número correto deve ser
conferido e informado pelo fluxo normal; a migração não altera o status nem as
justificativas da pendência. Também passa a gerenciar a restrição
`chk_sei_formato` pelas migrações, inclusive onde ela já existia no PostgreSQL.

Os testes desta migração precisam das migrações reais, habilitadas por
`config.settings.development` (o `_tmp_test` as desabilita):

```powershell
python manage.py test apps.extra_curricular.tests_sei_migration --settings=config.settings.development
```
