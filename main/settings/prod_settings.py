from .base_settings import *
import dj_database_url
from decouple import config

DATABASES = {'default' : dj_database_url.config(conn_max_age=600, ssl_require=True)}
DEBUG = False
ROOT_URLCONF = 'main.urls'
MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
ALLOWED_HOSTS = ['https://remixify-007.herokuapp.com', 'remixify-007.herokuapp.com']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

CACHES = {
    "default": {
        "BACKEND": "redis_cache.RedisCache",
        "LOCATION": config("REDIS_URL"),
        "OPTIONS": {
            "PICKLE_VERSION": 2,
            "CONNECTION_POOL_CLASS": "redis.ConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {"max_connections": 1},
        },
    }
}