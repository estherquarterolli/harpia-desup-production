# Deploy na HostGator com MySQL

Este guia descreve como subir o **AllocGest-DESUP** em hospedagem HostGator usando apenas MySQL.

## 1. O que você precisa

- Acesso ao painel da HostGator
- Um banco MySQL criado no painel
- Usuário e senha do MySQL
- A aplicação publicada em Python/WSGI ou via aplicação Node/Passenger com acesso ao projeto
- Domínio configurado para apontar para a hospedagem

## 2. Preparar o banco MySQL

1. No painel da HostGator, crie um banco MySQL.
2. Anote:
   - `DB_NAME`
   - `DB_USER`
   - `DB_PASSWORD`
   - `DB_HOST`
   - `DB_PORT=3306`
3. Se o painel fornecer um host específico do banco, use esse valor em `DB_HOST`.

## 3. Configurar variáveis de ambiente

Defina as variáveis abaixo na hospedagem:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
SECRET_KEY=<chave-forte>
ALLOWED_HOSTS=seudominio.com,www.seudominio.com

DB_ENGINE=django.db.backends.mysql
DB_NAME=<nome_do_banco>
DB_USER=<usuario_do_banco>
DB_PASSWORD=<senha_do_banco>
DB_HOST=<host_do_banco>
DB_PORT=3306

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@seudominio.com
```

Se você usar Redis ou e-mail externo, adicione as variáveis correspondentes.

## 4. Instalar dependências

No ambiente da hospedagem, instale os pacotes do projeto:

```bash
pip install -r project_root/requirements.txt
```

Se a HostGator não permitir instalar em ambiente compartilhado, use um ambiente virtual no diretório do projeto.

## 5. Rodar migrações

Com o banco já configurado:

```bash
cd project_root
python manage.py migrate --noinput
```

## 6. Coletar arquivos estáticos

```bash
cd project_root
python manage.py collectstatic --noinput
```

## 7. Rodar as seeds

As seeds já foram ajustadas para usar produção/MySQL. Rode na ordem que fizer sentido para o seu ambiente:

```bash
cd project_root
python seeds/seed_matrizes_completo.py
python seeds/seed_faetec_completo.py
python seeds/populate_desup.py
```

Se você quiser uma carga menor para validação inicial, use:

```bash
python seeds/seed_unidade_teste.py
python seeds/seed_professores_teste.py
```

## 8. Superusuário

Se ainda não existir uma conta administrativa:

```bash
cd project_root
python manage.py createsuperuser
```

## 9. Se a hospedagem exigir arquivo de inicialização

Use como referência:

```bash
cd project_root && python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Se a HostGator não suportar Gunicorn no seu plano, ajuste para o método recomendado pelo painel da hospedagem.

## 10. Checklist final

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `DB_ENGINE=django.db.backends.mysql`
- `DB_PORT=3306`
- `python manage.py migrate` concluído
- `python manage.py collectstatic --noinput` concluído
- seeds executadas
- domínio apontando para a hospedagem

## 11. Observações importantes

- Não use SQLite em produção.
- Não use PostgreSQL como dependência obrigatória na HostGator.
- A aplicação foi ajustada para trabalhar com MySQL como backend padrão.
- Se o provedor bloquear execução Python persistente, será necessário usar um plano que suporte apps Python/WSGI.
