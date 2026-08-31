"""
WSGI config for backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# SEC-003: o default é o settings de PRODUÇÃO. Este módulo só é importado por
# servidor de aplicação (gunicorn/uvicorn), nunca no desenvolvimento local —
# quem roda local usa o manage.py, que continua com o default de development.
# Com o default anterior, um deploy que não exportasse DJANGO_SETTINGS_MODULE
# (o Procfile não exportava; só o render.yaml define) subia com DEBUG=True e
# ALLOWED_HOSTS=['*'], expondo a página de debug do Django.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_wsgi_application()
