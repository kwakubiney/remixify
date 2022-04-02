import dj_database_url
from decouple import config

from main.settings.base_settings import MIDDLEWARE

DATABASES = {'default' : dj_database_url.config(conn_max_age=600, ssl_require=True)}
DEBUG = False
MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
ALLOWED_HOSTS = ['https://remixify-007.herokuapp.com/', 'remixify-007.herokuapp.com/']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
CELERY_BROKER_URL = config("REDIS_URL")
