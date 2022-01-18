from django.urls import path
from . import views

urlpatterns = [
    path('results/', views.result, name="result")
]
