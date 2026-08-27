from .base import *
import dj_database_url
import os

DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost").split(",")

database_url = config("DATABASE_URL", default="").strip()

if database_url:
    # Força sslmode=require se não estiver na URL (obrigatório no Supabase pooler)
    if "sslmode" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{sep}sslmode=require"

    DATABASES = {
        'default': dj_database_url.config(
            default=database_url,
            # Transaction-mode pooler não suporta conexões persistentes;
            # session-mode pooler suporta (porta 5432 pooler). Usar 0 é seguro
            # para ambos os modos.
            conn_max_age=0,
            conn_health_checks=False,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config("PROD_DB_NAME", default=""),
            'USER': config("PROD_DB_USER", default=""),
            'PASSWORD': config("PROD_DB_PASSWORD", default=""),
            'HOST': config("PROD_DB_HOST", default=""),
            'PORT': config("PROD_DB_PORT", default='5432'),
            'OPTIONS': {'sslmode': 'require'},
        }
    }

# Arquivos estáticos servidos pelo WhiteNoise (preserva o default do base.py)
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}

# Segurança HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
# Render já termina SSL no proxy — não redirecionar internamente
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
