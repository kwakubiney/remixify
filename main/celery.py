from __future__ import absolute_import, unicode_literals
import os
from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.dev_settings")
app = Celery("main" ,)
#app = Celery("main" , broker= settings.CELERY_BROKER_URL , backend=settings.CELERY_RESULT_BACKEND)
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f"Request : {self.request!r}")