release: cd project_root && python manage.py migrate && python manage.py collectstatic --noinput
web: cd project_root && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
