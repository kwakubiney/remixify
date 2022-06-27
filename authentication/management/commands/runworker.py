import shlex
import subprocess

from django.core.management.base import BaseCommand
from django.utils import autoreload


def restart_celery():
    subprocess.call(shlex.split("pkill -9 -f 'celery worker'"))
    subprocess.call(shlex.split('celery -A main worker -l info'))


class Command(BaseCommand):
    def handle(self, *args, **options):
        print('Starting celery worker with autoreload')
        autoreload.run_with_reloader(restart_celery)
        
    