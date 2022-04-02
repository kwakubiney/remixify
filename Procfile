release: python manage.py migrate
web: gunicorn main.wsgi --log-file -
celery: REMAP_SIGTERM=SIGQUIT celery -A main worker -l info
worker: python3 manage.py runworker
