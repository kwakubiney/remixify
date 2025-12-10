import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from tasks.tasks import create_remix, preview_remixes, create_remix_playlist
from django.contrib.auth.decorators import login_required
from celery.result import AsyncResult


@login_required(login_url="home")
@require_http_methods(["POST"])
def preview(request):
    """
    Phase 1: Start the preview task to find remix candidates.
    Returns a task_id to poll for results.
    """
    url = request.POST.get("url")
    if not url:
        return JsonResponse({"error": "URL is required"}, status=400)
    
    user_id = request.user.id
    result = preview_remixes.delay(url, user_id)
    return JsonResponse({"task_id": result.task_id})


@login_required(login_url="home")
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


@login_required(login_url="home")
@require_http_methods(["POST"])
def create_playlist(request):
    """
    Phase 2: Create the playlist with user-selected tracks.
    Expects JSON body with playlist_name and selected_tracks array.
    """
    try:
        data = json.loads(request.body)
        playlist_name = data.get("playlist_name", "My Playlist")
        selected_tracks = data.get("selected_tracks", [])
        
        if not selected_tracks:
            return JsonResponse({"error": "No tracks selected"}, status=400)
        
        user_id = request.user.id
        result = create_remix_playlist.delay(user_id, playlist_name, selected_tracks)
        return JsonResponse({"task_id": result.task_id})
    
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)


@login_required(login_url="home")
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
@login_required(login_url="home")
def result(request):
    if request.method == 'POST':
        url = request.POST.get("url")
        user_id = request.user.id
        result = create_remix.delay(url, user_id)
        context = {'task_id': result.task_id}
        return JsonResponse(context, safe=False)
    return JsonResponse({"error": "POST required"}, status=405)