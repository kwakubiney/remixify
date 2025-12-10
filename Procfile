release: python manage.py migrate
web: gunicorn main.wsgi:application --bind 0.0.0.0:$PORT --workers 2
celery: celery -A main worker -l info --concurrency=2
