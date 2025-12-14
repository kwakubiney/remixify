from .base_settings import *
import dj_database_url
from decouple import config
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
import os


# Database - works with Render's DATABASE_URL
DATABASES = {'default': dj_database_url.config(conn_max_age=600, ssl_require=True)}

DEBUG = False
ROOT_URLCONF = 'main.urls'

# Security
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.fly.dev',
    'remixify.xyz',
    'www.remixify.xyz',
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.fly.dev',  # Fly.io
    'https://remixify.xyz',
    'https://www.remixify.xyz',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Static files with WhiteNoise
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# OAuth
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# Celery - use REDIS_URL from Render
CELERY_BROKER_URL = os.environ.get('REDIS_URL', config('REDIS_URL', default='redis://localhost:6379/0'))
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', config('REDIS_URL', default='redis://localhost:6379/0'))

# Sentry error tracking
sentry_sdk.init(
    dsn=config('SENTRY_DSN', default=''),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False
)
# Enhanced Sentry configuration
sentry_dsn = config('SENTRY_DSN', default='')
if sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=True,
        environment=config('ENVIRONMENT', default='production'),
    )

# Production logging
LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['loggers']['django']['level'] = 'INFO'
LOGGING['loggers']['django.request']['level'] = 'INFO'
