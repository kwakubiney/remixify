from . import views
from django.urls import path

urlpatterns = [
    path("", views.home, name="home"),
    path("callback/", views.callback, name="callback"),
    path("index/" , views.index, name="index"),
    path("main/" , views.main, name="main")
    ]