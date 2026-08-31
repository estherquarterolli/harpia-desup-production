from .base import *
import dj_database_url

DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost").split(",")

# Domínios dinâmicos do Vercel: VERCEL_URL é o do deploy atual (muda a cada
# build), VERCEL_PROJECT_PRODUCTION_URL é o domínio fixo de produção
# (ex.: harpia-desup-vercel.vercel.app ou domínio customizado).
for vercel_host in (config("VERCEL_URL", default=""), config("VERCEL_PROJECT_PRODUCTION_URL", default="")):
    if vercel_host and vercel_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_host)

CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host not in ("localhost", "127.0.0.1")
]

database_url = config("DATABASE_URL", default="").strip()

if database_url:
    DATABASES = {
        'default': dj_database_url.config(
            default=database_url,
            conn_max_age=0,
            conn_health_checks=False,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config("PROD_DB_NAME", default=config("DB_NAME", default="")),
            'USER': config("PROD_DB_USER", default=config("DB_USER", default="")),
            'PASSWORD': config("PROD_DB_PASSWORD", default=config("DB_PASSWORD", default="")),
            'HOST': config("PROD_DB_HOST", default=config("DB_HOST", default="")),
            'PORT': config("PROD_DB_PORT", default=config("DB_PORT", default='3306')),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

# Arquivos estáticos servidos pelo WhiteNoise (preserva o default do base.py)
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}
# STORAGES["default"] (uploads) já é decidido em base.py: usa
# apps.core.storage.SupabaseStorage quando SUPABASE_URL/SUPABASE_KEY estão
# configurados, senão cai pra FileSystemStorage local.

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
