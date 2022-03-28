from django.contrib import admin
from django.urls import path
from django.urls.conf import include
import re

urlpatterns = [
    path('celery-progress/', include('celery_progress.urls')), 
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('authentication.urls')),
    path('', include('tasks.urls'))
]
