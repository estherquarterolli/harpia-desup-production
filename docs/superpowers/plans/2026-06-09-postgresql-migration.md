# PostgreSQL Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Django project to support both SQLite3 and PostgreSQL, providing a clear way to switch between them and documenting the setup process.

**Architecture:** Use `config.settings.base` for SQLite3 (default) and `config.settings.development` for configurable database settings (supporting PostgreSQL via environment variables).

**Tech Stack:** Django, PostgreSQL (psycopg2-binary), python-decouple.

---

### Task 1: Research and Environment Setup

**Files:**
- Modify: `project_root/requirements.txt`
- Modify: `project_root/.env.example`

- [ ] **Step 1: Verify requirements.txt**
Ensure `psycopg2-binary` is present and at a compatible version.
- [ ] **Step 2: Install dependencies**
Run: `pip install -r project_root/requirements.txt`
- [ ] **Step 3: Update .env.example**
Add clear PostgreSQL placeholders to `.env.example`.

```python
# Database Settings
DB_ENGINE=django.db.backends.postgresql
DB_NAME=allocgest_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

### Task 2: Refine Development Settings

**Files:**
- Modify: `project_root/config/settings/development.py`

- [ ] **Step 1: Update DATABASES in development.py**
Ensure the configuration is robust and well-documented.

```python
DATABASES = {
    'default': {
        'ENGINE': config("DB_ENGINE", default='django.db.backends.sqlite3'),
        'NAME': config("DB_NAME", default=BASE_DIR / 'db.sqlite3'),
        'USER': config("DB_USER", default=''),
        'PASSWORD': config("DB_PASSWORD", default=''),
        'HOST': config("DB_HOST", default='localhost'),
        'PORT': config("DB_PORT", default=''),
    }
}
```

### Task 3: Create Tutorial

**Files:**
- Create: `docs/database_setup_tutorial.md`

- [ ] **Step 1: Write the tutorial content**
Include instructions for:
- Database configuration structure.
- Local PostgreSQL installation.
- Creating a new database.
- Using `DJANGO_SETTINGS_MODULE` to switch databases.
- Running migrations.

### Task 4: Verification

- [ ] **Step 1: Test SQLite3 (Default)**
Run: `python project_root/manage.py check`
Expected: Success using SQLite3.
- [ ] **Step 2: Test Settings Override**
Run: `set DJANGO_SETTINGS_MODULE=config.settings.development && python project_root/manage.py check`
Expected: Success (it might fail if DB is not reachable, but it should try to use the configured values).
