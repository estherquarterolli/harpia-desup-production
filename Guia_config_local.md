# Guia de Configuração Local — AllocGest-DESUP
Este guia orienta como configurar e rodar o projeto localmente com MySQL ou SQLite.

Opção A: Início Rápido (Reaproveitando o Banco já Populado)
Utilize esta opção se você copiou o projeto contendo o arquivo `db.sqlite3` e o `.env` configurados.

1. Criar e Ativar o Ambiente Virtual (venv)
No terminal, dentro da pasta raiz do projeto (AllocGest-DESUP):

powershell
# Criar ambiente virtual
python -m venv .venv
# Ativar ambiente virtual
# No Windows (PowerShell):
.venv\Scripts\activate
# No Linux / MacOS:
source .venv/bin/activate
2. Instalar Dependências
Navegue até a pasta do Django e instale os pacotes necessários:

powershell
cd project_root
pip install -r requirements.txt
3. Rodar o Servidor
Com o arquivo .env e db.sqlite3 já copiados na pasta project_root/, basta rodar:

powershell
python manage.py runserver
Acesse no navegador: http://127.0.0.1:8000/

Opção B: Configuração do Zero
Utilize esta opção se você quer usar MySQL local ou recriar o banco do zero.

1. Ajustar o Arquivo .env
Certifique-se de que o arquivo `project_root/.env` está configurado para usar MySQL:

env
DB_ENGINE=django.db.backends.mysql
DB_NAME=harpia_db
DB_USER=root
DB_PASSWORD=suasenha
DB_HOST=127.0.0.1
DB_PORT=3306
2. Rodar as Migrações do Django
Crie as tabelas no banco SQLite local:

powershell
python manage.py migrate
3. Executar as Seeds (Carga de Dados)
Execute os scripts na ordem recomendada para popular o sistema:

powershell
# 1. Cria todas as unidades, cursos, matrizes e componentes curriculares
python seeds/seed_matrizes_completo.py
# 2. Cria professores de teste
python seeds/seed_professores_ficticios.py
# 3. Cria as contas administrativas de login para teste
python seeds/populate_desup.py

Observações de produção:
- Não use `db.sqlite3` em produção.
- Em produção, o banco deve ser MySQL e a aplicação deve subir com `config.settings.production`.
- Rode `python manage.py migrate` antes das seeds.
4. Credenciais de Teste Disponíveis:
Administrador DESUP (Alberto):
E-mail: alberto.alvaraes@desup.faetec.rj.gov.br
Senha: 0@Aprisma
Coordenador FAETERJ Paracambi:
E-mail: coord.paracambi@faetec.rj.gov.br
Senha: Faetec@123
Coordenador FAETERJ Rio de Janeiro:
E-mail: coord.rio@faetec.rj.gov.br
Senha: Faetec@123
