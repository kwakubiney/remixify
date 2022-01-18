from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

app = Celery("main" ,)

app.config_from_object("django.conf.settings", namespace="CELERY")

app.autodiscover_tasks()

#celery beat settings
app.conf.beat_schedule = {

}

@app.task(bind=True)
def debug_task(self):
    print(f"Request : {self.request!r}")