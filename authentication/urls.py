from django.urls import path
from django.http import JsonResponse
from . import views


def health_check(request):
    """Health check endpoint for Render."""
    return JsonResponse({"status": "healthy"})


urlpatterns = [
    path('', views.home, name="home"),
    path('health/', health_check, name="health_check"),
]
