release: cd project_root && DJANGO_SETTINGS_MODULE=config.settings.production python manage.py migrate && DJANGO_SETTINGS_MODULE=config.settings.production python manage.py collectstatic --noinput
web: cd project_root && DJANGO_SETTINGS_MODULE=config.settings.production gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
