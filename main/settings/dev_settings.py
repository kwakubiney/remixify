from .base_settings import *
from decouple import config

DEBUG = True

DATABASES = {

    'default': {

        'ENGINE': 'django.db.backends.postgresql_psycopg2',

        'NAME': config('POSTGRES_NAME'),

        'USER': config('POSTGRES_DB'),

        'PASSWORD': config('POSTGRES_PASSWORD'),

        'HOST': config('POSTGRES_HOST'),

        'PORT': config('POSTGRES_PORT'),

    }
}

ALLOWED_HOSTS = ['localhost', '127.0.0.1']
CELERY_BROKER_URL = config("REDIS_URL")
CELERY_RESULT_BACKEND = config("REDIS_URL")


