from .base import *

# Configurações de Desenvolvimento
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Email de desenvolvimento no console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "dev@harpia.local"

# Database config via environment variables
DATABASES = {
    'default': {
        'ENGINE': config("DB_ENGINE", default='django.db.backends.postgresql'),
        'NAME': config("DB_NAME", default='desup_alloc_db'),
        'USER': config("DB_USER", default='postgres'),
        'PASSWORD': config("DB_PASSWORD", default='postgres'),
        'HOST': config("DB_HOST", default='localhost'),
        'PORT': config("DB_PORT", default='5432'),
    },
    'sqlite_backup': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',        
    }
}
