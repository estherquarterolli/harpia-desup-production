# Database Setup Tutorial

This tutorial explains how to set up and switch between SQLite3 (default) and PostgreSQL (development) databases for the project.

## 1. Overview of Database Configuration

The project is configured to use two different database settings:

*   `project_root/config/settings/base.py`: This file defines the default database configuration, which is **SQLite3**. Any Django command run without specifying a different settings module will use this configuration.
*   `project_root/config/settings/development.py`: This file extends `base.py` and provides an alternative database configuration. It is set up to use **PostgreSQL**, but can fall back to SQLite3 if PostgreSQL-specific environment variables are not provided.

This setup allows developers to easily switch between a lightweight SQLite3 database for quick tasks and a more robust PostgreSQL database for development, which more closely mirrors production environments.

## 2. Installing PostgreSQL Driver

The `psycopg2-binary` package is required to connect to PostgreSQL from Django. This has been added to `project_root/requirements.txt`.

To install or update your project dependencies, navigate to the `project_root` directory and run:

```bash
pip install -r requirements.txt
```

## 3. Setting up PostgreSQL

### A. Install PostgreSQL

If you don't have PostgreSQL installed, here are common methods:

*   **Using Docker (Recommended for development):**
    ```bash
    docker run --name some-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres
    ```
    This command starts a PostgreSQL container named `some-postgres` with the password `postgres` and exposes it on port `5432`.

*   **Native Installation:**
    Refer to the official PostgreSQL documentation for your operating system: [https://www.postgresql.org/download/](https://www.postgresql.org/download/)

### B. Create a Database

Once PostgreSQL is running, create a new database for your project. You can do this via the `createdb` command-line tool, the `psql` interactive terminal, or a GUI client like pgAdmin.

*   **Using `createdb` (from your host machine):**
    ```bash
    createdb -h localhost -p 5432 -U postgres your_project_db
    ```

*   **Using `psql` (interactive):**
    ```bash
    # If using Docker, connect to the container's psql
    docker exec -it some-postgres psql -U postgres

    # Or if installed natively
    psql -U postgres

    # Inside psql, create the database
    CREATE DATABASE your_project_db;
    \q
    ```
Replace `your_project_db` with your desired database name (e.g., `allocgest_db`).

## 4. Switching Between Databases

The `DJANGO_SETTINGS_MODULE` environment variable controls which settings file Django uses.

*   **To use SQLite3 (default):**
    You don't need to set `DJANGO_SETTINGS_MODULE` explicitly, or you can set it to `config.settings.base`.

    ```bash
    # Implicitly uses base.py (SQLite3)
    python manage.py runserver

    # Explicitly uses base.py (SQLite3)
    DJANGO_SETTINGS_MODULE=config.settings.base python manage.py runserver
    ```

*   **To use PostgreSQL (development):**
    You need to set `DJANGO_SETTINGS_MODULE` to `config.settings.development` and provide the necessary environment variables for PostgreSQL connection.

    Create a `.env` file in your `project_root` directory (if you don't have one) and add the following, adjusting values as per your PostgreSQL setup:

    ```ini
    DB_ENGINE=django.db.backends.postgresql
    DB_NAME=allocgest_db
    DB_USER=postgres
    DB_PASSWORD=postgres
    DB_HOST=localhost
    DB_PORT=5432
    # Other settings like SECRET_KEY and DEBUG might also be in your .env
    SECRET_KEY=your_secret_key_here
    DEBUG=True
    ALLOWED_HOSTS=*
    ```

    Then, run your Django commands:

    ```bash
    # This will use config.settings.development and pick up .env variables
    DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver
    ```
    **Note:** Make sure `python-decouple` is installed (`pip install python-decouple`) as it's used to read environment variables. It should already be in your `requirements.txt`.

## 5. Performing Database Migrations

You will need to run migrations for each database independently when you switch.

*   **For SQLite3:**
    ```bash
    # Uses default settings (base.py)
    python manage.py makemigrations
    python manage.py migrate
    ```

*   **For PostgreSQL:**
    ```bash
    # Uses development settings (development.py)
    DJANGO_SETTINGS_MODULE=config.settings.development python manage.py makemigrations
    DJANGO_SETTINGS_MODULE=config.settings.development python manage.py migrate
    ```
    **Important:** Run `makemigrations` and `migrate` for each database profile after making model changes.

## 6. Testing and Verification

After setting up both configurations, verify they work correctly:

1.  **Verify SQLite3:**
    *   Ensure `DJANGO_SETTINGS_MODULE` is not set or set to `config.settings.base`.
    *   Run `python manage.py runserver`.
    *   Access the application, log in, and perform some basic CRUD (Create, Read, Update, Delete) operations on any model (e.g., create a new user, modify an existing one).
    *   Confirm data persists correctly after restarting the server.

2.  **Verify PostgreSQL:**
    *   Ensure `DJANGO_SETTINGS_MODULE=config.settings.development` is set (e.g., via your `.env` file and command prefix).
    *   Run `python manage.py runserver`.
    *   Access the application, log in, and perform basic CRUD operations.
    *   Confirm data persists and is separate from the SQLite3 database.

By following these steps, you can effectively manage and switch between SQLite3 and PostgreSQL databases during your development process.
