from django.urls import path
from . import views

urlpatterns = [
    # New two-phase endpoints
    path('preview/', views.preview, name="preview"),
    path('preview/<str:task_id>/', views.get_preview_result, name="preview_result"),
    path('create-playlist/', views.create_playlist, name="create_playlist"),
    path('create-playlist/<str:task_id>/', views.get_create_result, name="create_result"),
    
    # Recent playlists
    path('recent-playlists/', views.recent_playlists, name="recent_playlists"),
    
    # Legacy endpoint
    path('results/', views.result, name="result"),
]
