from os import kill
import shlex
import subprocess
from django.core.management.base import BaseCommand
from django.utils import autoreload


def kill():
    subprocess.call(shlex.split('pkill celery'))


class Command(BaseCommand):
    def handle(self, *args, **options):
        print('killing celery')
        kill()