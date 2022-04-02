release: python manage.py migrate
web: gunicorn main.wsgi --log-file -
celery: celery -A main worker -l info
