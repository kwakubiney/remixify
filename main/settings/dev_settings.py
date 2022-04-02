from .base_settings import *
from decouple import config

DEBUG = True

DATABASES = {

    'default': {

        'ENGINE': 'django.db.backends.postgresql_psycopg2',

        'NAME': config('DB_NAME'),

        'USER': config('DB_USER'),

        'PASSWORD': config('DB_PASSWORD'),

        'HOST': config('DB_HOST'),

        'PORT': config('DB_PORT'),

    }

}

ALLOWED_HOSTS = list(config("ALLOWED_HOSTS"))
CELERY_BROKER_URL = config("REDIS_URL")
CELERY_RESULT_BACKEND = config("REDIS_URL")
CELERY_CACHE_BACKEND = config("CELERY_CACHE_BACKEND")

