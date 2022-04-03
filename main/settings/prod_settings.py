from .base_settings import *
import dj_database_url
from decouple import config
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


DATABASES = {'default' : dj_database_url.config(conn_max_age=600, ssl_require=True)}
DEBUG = False
ROOT_URLCONF = 'main.urls'
MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
ALLOWED_HOSTS = ['https://remixify-007.herokuapp.com', 'remixify-007.herokuapp.com']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'



sentry_sdk.init(
    dsn="https://2604c6bbe4db4ee69b134f9b2e1b6218@o1187598.ingest.sentry.io/6307454",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=True
)