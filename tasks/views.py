import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from tasks.tasks import create_remix, preview_remixes, create_remix_playlist
from tasks.models import CreatedPlaylist
from celery.result import AsyncResult


@csrf_protect
@require_http_methods(["POST"])
def preview(request):
    """
    Phase 1: Start the preview task to find remix candidates.
    Returns a task_id to poll for results.
    """
    url = request.POST.get("url")
    if not url:
        return JsonResponse({"error": "URL is required"}, status=400)
    
    result = preview_remixes.delay(url)
    return JsonResponse({"task_id": result.task_id})


@require_http_methods(["GET"])
def get_preview_result(request, task_id):
    """
    Get the result of a preview task.
    """
    result = AsyncResult(task_id)
    
    if result.ready():
        if result.successful():
            return JsonResponse({
                "status": "complete",
                "result": result.result
            })
        else:
            return JsonResponse({
                "status": "error",
                "error": str(result.result)
            }, status=500)
    else:
        return JsonResponse({
            "status": "pending",
            "progress": getattr(result, 'info', {})
        })


@csrf_protect
@require_http_methods(["POST"])
def create_playlist(request):
    """
    Phase 2: Create the playlist with user-selected tracks on the central account.
    Expects JSON body with playlist_name and selected_tracks array.
    
    No authentication required - playlist is created and made public.
    """
    try:
        data = json.loads(request.body)
        playlist_name = data.get("playlist_name", "My Playlist")
        selected_tracks = data.get("selected_tracks", [])
        original_url = data.get("original_url", "")
        
        if not selected_tracks:
            return JsonResponse({"error": "No tracks selected"}, status=400)
        
        result = create_remix_playlist.delay(playlist_name, selected_tracks, original_url)
        return JsonResponse({"task_id": result.task_id})
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@require_http_methods(["GET"])
def get_create_result(request, task_id):
    """
    Get the result of a playlist creation task.
    """
    result = AsyncResult(task_id)
    
    if result.ready():
        if result.successful():
            return JsonResponse({
                "status": "complete",
                "result": result.result
            })
        else:
            return JsonResponse({
                "status": "error", 
                "error": str(result.result)
            }, status=500)
    else:
        return JsonResponse({
            "status": "pending"
        })


# Legacy endpoint for backwards compatibility
@csrf_protect
def result(request):
    """Legacy: Direct remix creation without preview."""
    if request.method == 'POST':
        url = request.POST.get("url")
        result = create_remix.delay(url)
        context = {'task_id': result.task_id}
        return JsonResponse(context, safe=False)
    return JsonResponse({"error": "POST required"}, status=405)


@require_http_methods(["GET"])
def recent_playlists(request):
    """
    Get the 3 most recently created playlists.
    Returns playlist name, URL, image, and track count.
    """
    playlists = CreatedPlaylist.objects.all()[:3]
    
    data = [
        {
            "name": p.name,
            "url": p.spotify_url,
            "image": p.image_url,
            "original_author": p.original_author or "Unknown",
        }
        for p in playlists
    ]
    
    return JsonResponse({"playlists": data})


@require_http_methods(["GET"])
def playlist_count(request):
    """
    Get the total number of playlists created (from Redis).
    Fast counter for display on homepage.
    """
    from tasks.redis_utils import get_playlist_count
    count = get_playlist_count()
    return JsonResponse({"count": count})
