# Tutorial para Utilizar o Banco de Dados

## Passo 1: Substituir o Banco de Dados
1. Copie o arquivo `db.sqlite3` para o diretório do projeto Django no computador da sua colega.
2. Certifique-se de que o arquivo esteja no mesmo local onde o Django espera o banco de dados (geralmente na raiz do projeto).

## Passo 2: Importar os Dados (Opcional)
Se você preferir importar os dados em vez de substituir o arquivo, siga estas etapas:
1. Certifique-se de que o arquivo `backup.sql` esteja no mesmo diretório do projeto.
2. Execute o seguinte comando no terminal para importar os dados:
   ```bash
   sqlite3 db.sqlite3 < backup.sql
   ```

## Passo 3: Resetar o Banco de Dados (Se Necessário)
Se precisar resetar o banco de dados, execute os seguintes comandos:
1. Apague o arquivo `db.sqlite3`:
   ```bash
   rm db.sqlite3
   ```
   (No Windows, use `del db.sqlite3`.)
2. Recrie o banco de dados e aplique as migrações:
   ```bash
   python manage.py migrate
   ```
3. Crie um superusuário novamente:
   ```bash
   python manage.py createsuperuser
   ```

Pronto! Agora o banco de dados está configurado e pronto para uso.