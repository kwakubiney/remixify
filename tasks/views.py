import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from tasks.tasks import preview_remixes, create_remix_playlist
from tasks.models import CreatedPlaylist
from tasks.helpers import get_playlist_id
from celery.result import AsyncResult
from authentication.oauth import get_spotify_client

logger = logging.getLogger(__name__)


def _extract_spotify_track_id(value: str) -> str | None:
    """Extract a Spotify track ID from a URL/URI/ID string."""
    if not value:
        return None

    raw = (value or "").strip()
    if not raw:
        return None

    if raw.startswith("spotify:track:"):
        parts = raw.split(":")
        return parts[-1] if parts else None

    if "/track/" in raw:
        # e.g. https://open.spotify.com/track/<id>?si=...
        try:
            after = raw.split("/track/", 1)[1]
        except Exception:
            return None
        return after.split("?", 1)[0].split("/", 1)[0]

    # If it looks like a bare ID (Spotify IDs are 22 chars base62)
    if len(raw) == 22 and raw.isalnum():
        return raw

    return None


@csrf_protect
@require_http_methods(["POST"])
def resolve_track(request):
    """Resolve a Spotify track link into canonical metadata for manual curation."""
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    raw = (data.get("url") or data.get("value") or "").strip()
    track_id = _extract_spotify_track_id(raw)
    if not track_id:
        return JsonResponse({"error": "Please paste a Spotify track link"}, status=400)

    try:
        sp = get_spotify_client()
        t = sp.track(track_id)

        track = {
            "id": t.get("id"),
            "name": t.get("name") or "",
            "artists": [a.get("name", "") for a in (t.get("artists") or []) if a.get("name")],
            "album_art": ((t.get("album") or {}).get("images") or [{}])[0].get("url"),
            "preview_url": t.get("preview_url"),
            "spotify_url": (t.get("external_urls") or {}).get("spotify", ""),
            "duration_ms": t.get("duration_ms"),
            "type": "track",
        }

        if not track.get("id"):
            return JsonResponse({"error": "Track not found"}, status=404)

        return JsonResponse({"track": track})
    except Exception as e:
        logger.error(f"Error resolving track '{raw}': {str(e)}", exc_info=True)
        return JsonResponse({"error": "Failed to resolve track"}, status=500)


@csrf_protect
@require_http_methods(["POST"])
def preview(request):
    """
    Phase 1: Start the preview task to find remix candidates.
    Returns a task_id to poll for results.
    """
    url = request.POST.get("url")
    
    logger.info(f"Preview request received - URL: {url}, User: {request.user}")

    if not url:
        logger.warning(f"Preview request without URL from user: {request.user}")
        return JsonResponse({"error": "URL is required"}, status=400)
    
    # Validate playlist URL before queuing task
    try:
        get_playlist_id(url)
    except ValueError as e:
        logger.warning(f"Invalid playlist URL from user {request.user}: {url}")
        return JsonResponse({"error": str(e)}, status=400)
    
    try:
        result = preview_remixes.delay(url)
        logger.info(f"Preview task started - Task ID: {result.task_id}, URL: {url}")
        return JsonResponse({"task_id": result.task_id})
    except Exception as e:
        logger.error(f"Error starting preview task for URL {url}: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Failed to start preview task"}, status=500)


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
        
        logger.info(f"Create playlist request - Name: {playlist_name}, Tracks: {len(selected_tracks)}, Original URL: {original_url}, User: {request.user}")
        
        if not selected_tracks:
            logger.warning(f"Create playlist request with no tracks from user: {request.user}")
            return JsonResponse({"error": "No tracks selected"}, status=400)
        
        result = create_remix_playlist.delay(playlist_name, selected_tracks, original_url)
        logger.info(f"Playlist creation task started - Task ID: {result.task_id}, Name: {playlist_name}")
        return JsonResponse({"task_id": result.task_id})
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in create playlist request: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error creating playlist: {str(e)}", exc_info=True)
        return JsonResponse({"error": "Failed to create playlist"}, status=500)


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


@require_http_methods(["GET"])
def debug_spotify_search(request):
    """
    DEBUG ENDPOINT: Test Spotify search using raw requests to bypass spotipy.
    
    Usage: GET /debug-search/?q=fever+remix
    """
    import time
    import requests as raw_requests
    
    query = request.GET.get("q", "fever remix")
    use_raw = request.GET.get("raw", "true") == "true"  # Default to raw requests
    
    logger.info(f"[DEBUG] debug_spotify_search called with query: {query}, use_raw: {use_raw}")
    start_time = time.time()
    
    try:
        # First, get a fresh token
        logger.info("[DEBUG] Getting fresh access token...")
        sp = get_spotify_client()
        token = sp.auth_manager.get_access_token(as_dict=False)
        logger.info(f"[DEBUG] Got access token (length: {len(token) if token else 0})")
        
        if use_raw:
            # Use raw requests to bypass spotipy entirely
            logger.info("[DEBUG] Using RAW requests to test search endpoint...")
            url = "https://api.spotify.com/v1/search"
            headers = {"Authorization": f"Bearer {token}"}
            params = {"q": query, "type": "track", "limit": 5}
            
            logger.info(f"[DEBUG] Making raw GET request to {url}...")
            response = raw_requests.get(url, headers=headers, params=params, timeout=10)
            elapsed = time.time() - start_time
            
            logger.info(f"[DEBUG] Raw request completed in {elapsed:.2f}s with status {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                tracks = []
                for item in data.get("tracks", {}).get("items", []):
                    tracks.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "artists": [a.get("name") for a in item.get("artists", [])],
                    })
                return JsonResponse({
                    "status": "success",
                    "method": "raw_requests",
                    "query": query,
                    "elapsed_seconds": elapsed,
                    "track_count": len(tracks),
                    "tracks": tracks,
                })
            else:
                return JsonResponse({
                    "status": "error",
                    "method": "raw_requests",
                    "query": query,
                    "elapsed_seconds": elapsed,
                    "http_status": response.status_code,
                    "error": response.text[:500],
                }, status=response.status_code)
        else:
            # Use spotipy
            logger.info("[DEBUG] Using SPOTIPY to test search...")
            results = sp.search(query, type="track", limit=5)
            elapsed = time.time() - start_time
            
            logger.info(f"[DEBUG] Spotipy search completed in {elapsed:.2f}s")
            
            tracks = []
            for item in results.get("tracks", {}).get("items", []):
                tracks.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "artists": [a.get("name") for a in item.get("artists", [])],
                })
            
            return JsonResponse({
                "status": "success",
                "method": "spotipy",
                "query": query,
                "elapsed_seconds": elapsed,
                "track_count": len(tracks),
                "tracks": tracks,
            })
    except raw_requests.Timeout as e:
        elapsed = time.time() - start_time
        logger.error(f"[DEBUG] Raw request TIMED OUT after {elapsed:.2f}s")
        return JsonResponse({
            "status": "timeout",
            "query": query,
            "elapsed_seconds": elapsed,
            "error": "Request timed out after 10 seconds",
        }, status=504)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[DEBUG] Search failed after {elapsed:.2f}s: {type(e).__name__}: {str(e)}")
        return JsonResponse({
            "status": "error",
            "query": query,
            "elapsed_seconds": elapsed,
            "error": f"{type(e).__name__}: {str(e)}",
        }, status=500)
