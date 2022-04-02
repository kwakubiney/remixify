from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from decouple import config

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.dev_settings")
app = Celery("main" , broker= settings.REDIS_URL , backend=settings.REDIS_URL)
app.config_from_object("django.conf.settings", namespace="CELERY")

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f"Request : {self.request!r}")