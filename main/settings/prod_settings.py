from .base_settings import *
import dj_database_url
from decouple import config
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import logging
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

# Sentry error tracking with full integrations
def before_send(event, hint):
    """
    Filter out expected user input errors before sending to Sentry.
    These are not bugs but expected validation errors from user input.
    """
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        # Filter out user input validation errors
        if exc_type is ValueError and exc_value:
            error_msg = str(exc_value).lower()
            user_input_errors = [
                "playlist is private or doesn't exist",
                "spotify-generated playlist",
                "authentication error",
                "access denied",
                "unable to load this playlist",
                "too many requests",
                "something went wrong",
            ]
            if any(err in error_msg for err in user_input_errors):
                return None  # Don't send to Sentry
    return event

sentry_dsn = config('SENTRY_DSN', default='')
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,  # Capture ERROR+ as Sentry events
            ),
        ],
        traces_sample_rate=0.2,  # 20% of requests for performance monitoring
        send_default_pii=True,
        environment=config('ENVIRONMENT', default='production'),
        # Add release tracking
        release=config('FLY_ALLOC_ID', default='local'),
        before_send=before_send,
    )

# Production logging - remove file handler (use console only for containers)
# Override LOGGING to use only console handler in production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'INFO',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'tasks': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'authentication': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
