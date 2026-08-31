"""
Django settings for config project.
"""

from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Quick-start development settings
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
TIME_ZONE = config("TIME_ZONE", default="America/Sao_Paulo")
USE_TZ = True

# Application definition
INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'unfold.contrib.inlines',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',

    # Seu app de contas
    'apps.accounts',
    'apps.core',
    'apps.allocations',
    'apps.courses',
    'apps.professors',
    'apps.extra_curricular',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.PasswordChangeForceMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.notificacoes',
                'apps.core.context_processors.delivery_window_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'apps.accounts.validators.ComplexPasswordValidator'},
]

# Authentication
AUTH_USER_MODEL = 'accounts.User'

# Para onde o usuário vai após fazer login com sucesso
LOGIN_URL = 'login'

# Redireciona para o dashboard
LOGIN_REDIRECT_URL = 'dashboard'

# Após logout, vai para login
LOGOUT_REDIRECT_URL = 'login'

# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cache
REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "allocgest-local-cache",
        }
    }

# Email
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="no-reply@harpia.local")

# ---------------------------------------------------------------------------
# Observabilidade de erros 500 (CORR-005)
# ---------------------------------------------------------------------------
# Sem ADMINS + LOGGING o e-mail padrão de erro 500 do Django nunca dispara.
# Aqui configuramos:
#   - ADMINS: destinatários do e-mail automático de erro (o DEV / super admin).
#   - SERVER_EMAIL: remetente desse e-mail de erro.
#   - LOGGING: AdminEmailHandler (e-mail no 500, só quando DEBUG=False) +
#     handlers de console e arquivo rotativo para os loggers `django` e
#     `django.request` (traceback sempre acessível localmente/em produção).
#
# NUNCA hardcode e-mail pessoal no repositório — defina por variável de ambiente:
#   ADMINS_EMAILS="Dev Harpia <dev@exemplo.com>,outra.pessoa@exemplo.com"
# (aceita "Nome <email>" ou apenas "email", separados por vírgula). Vazio => sem
# admins (fallback seguro: nenhum e-mail é enviado, apenas console/arquivo).

def _parse_admins(raw):
    """Converte "Nome <email>,email2" em [("Nome", "email"), ("Admin", "email2")]."""
    parsed = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "<" in entry and ">" in entry:
            name = entry.split("<", 1)[0].strip() or "Admin"
            email = entry.split("<", 1)[1].split(">", 1)[0].strip()
        else:
            name, email = "Admin", entry
        if email:
            parsed.append((name, email))
    return parsed


ADMINS = _parse_admins(config("ADMINS_EMAILS", default=""))
MANAGERS = ADMINS

# Remetente do e-mail de erro do servidor (500). Cai no DEFAULT_FROM_EMAIL se
# não for definido explicitamente por ambiente.
SERVER_EMAIL = config("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# include_html no e-mail de erro traz o traceback interativo completo (mais dados
# sensíveis). Padrão False (traceback em texto puro já basta e é mais seguro);
# habilite via ADMIN_EMAIL_INCLUDE_HTML=True se precisar do relatório completo.
ADMIN_EMAIL_INCLUDE_HTML = config("ADMIN_EMAIL_INCLUDE_HTML", default=False, cast=bool)

DJANGO_LOG_LEVEL = config("DJANGO_LOG_LEVEL", default="INFO")

LOG_DIR = BASE_DIR / "logs"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Filesystem somente-leitura (ambientes efêmeros): segue só com console.
    LOG_DIR = None

_error_handlers = ["console"] + (["file"] if LOG_DIR else [])

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {process:d}/{thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        # AdminEmailHandler só envia quando DEBUG=False (filtro require_debug_false)
        # e quando há ADMINS definidos — em dev fica inerte automaticamente.
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "include_html": ADMIN_EMAIL_INCLUDE_HTML,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": DJANGO_LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": _error_handlers,
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },
        # django.request loga todo erro 500 (uncaught) em nível ERROR — é aqui
        # que o e-mail ao super admin dispara em produção.
        "django.request": {
            "handlers": _error_handlers + ["mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# Handler de arquivo rotativo — só adicionado se houver diretório de logs gravável.
if LOG_DIR:
    LOGGING["handlers"]["file"] = {
        "level": "ERROR",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOG_DIR / "errors.log"),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 5,
        "formatter": "verbose",
        "encoding": "utf-8",
    }

# Celery
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL or "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL or "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=not bool(REDIS_URL), cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

UNFOLD = {
    "SITE_TITLE": "Harpia",
    "SITE_SYMBOL": "ads_click",
    "THEMING": {
        "colors": {
            "primary": {
                "50": "239 246 255",
                "100": "219 234 254",
                "200": "191 219 254",
                "300": "147 197 253",
                "400": "96 165 250",
                "500": "59 130 246",
                "600": "37 99 235",
                "700": "29 78 216",
                "800": "30 64 175",
                "900": "30 58 138",
            },
        },
    },
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://localhost:8000"
).split(",")

# Supabase Storage
SUPABASE_URL = config("SUPABASE_URL", default="")
SUPABASE_KEY = config("SUPABASE_KEY", default="")
SUPABASE_SERVICE_ROLE_KEY = config("SUPABASE_SERVICE_ROLE_KEY", default="")

if SUPABASE_URL and SUPABASE_KEY:
    STORAGES = {
        "default": {
            "BACKEND": "apps.core.storage.SupabaseStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    # Use default storage for development
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
