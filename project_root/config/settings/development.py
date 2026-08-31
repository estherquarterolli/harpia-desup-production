from .base import *
import dj_database_url

# Configurações de Desenvolvimento
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Email de desenvolvimento no console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "dev@harpia.local"

# Database config via environment variables.
# Se DATABASE_URL estiver definido, ele tem prioridade.
# Caso contrário, usa as variáveis DB_* com MySQL como padrão.
database_url = config("DATABASE_URL", default="").strip()

if database_url:
    default_db = dj_database_url.config(
        default=database_url,
        conn_max_age=0,
        conn_health_checks=False,
    )
else:
    default_db = {
        'ENGINE': config("DB_ENGINE", default="django.db.backends.mysql"),
        'NAME': config("DB_NAME", default='desup_alloc_db'),
        'USER': config("DB_USER", default='root'),
        'PASSWORD': config("DB_PASSWORD", default=''),
        'HOST': config("DB_HOST", default='localhost'),
        'PORT': config("DB_PORT", default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }

DATABASES = {
    'default': default_db,
}
