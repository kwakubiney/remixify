from celery import shared_task
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from spotipy import Spotify
from celery_progress.backend import ProgressRecorder
from tasks.helpers import chunker, get_playlist_id
from tasks.models import CreatedPlaylist
from tasks.redis_utils import increment_playlist_count
from authentication.oauth import get_spotify_client


def calculate_match_confidence(original_name, original_artists, remix_track):
    """
    Calculate a confidence score (0-100) for how well a remix matches the original.
    
    IMPORTANT: Only returns positive score if track contains remix keywords.
    This ensures we only show actual remixes, not original songs.
    
    Factors:
    - MUST contain "remix" or similar keyword (required)
    - Track name similarity
    - Artist overlap (original artist featured or credited)
    """
    remix_name = remix_track["name"].lower()
    original_name_lower = original_name.lower().strip()
    remix_artists = [a["name"].lower() for a in remix_track["artists"]]
    original_artists_lower = [a.lower() for a in original_artists]
    
    score = 0
    reasons = []
    
    # CRITICAL: Must contain remix keyword - this is REQUIRED
    remix_keywords = ["remix", "remixed", "rmx", "bootleg", "rework", "flip", "vip mix", "club mix", "radio edit"]
    has_remix_keyword = any(keyword in remix_name for keyword in remix_keywords)
    
    if not has_remix_keyword:
        # Not a remix - return 0 score
        return 0, ["not_a_remix"]
    
    reasons.append("is_remix")
    score += 30  # Base score for being a remix
    
    # Check if this is the exact same song (not a remix of it)
    # If the track name is almost identical and same primary artist, skip it
    if remix_name.replace(" ", "") == original_name_lower.replace(" ", ""):
        return 0, ["same_song"]
    
    # Extract core song title from remix name (before the dash/hyphen where remix info usually starts)
    # e.g., "still - ndinga gaba remix" → "still"
    remix_core = remix_name.split(" - ")[0].strip() if " - " in remix_name else remix_name
    
    # 1. Name similarity (0-35 points)
    # Check if original name appears in remix name
    if original_name_lower in remix_name:
        score += 35
        reasons.append("name_match")
    # Check if remix core matches original name
    elif original_name_lower == remix_core or original_name_lower in remix_core or remix_core in original_name_lower:
        score += 35
        reasons.append("core_name_match")
    # Check if remix starts with the original name
    elif remix_name.startswith(original_name_lower) or remix_core.startswith(original_name_lower):
        score += 30
        reasons.append("starts_with_original")
    else:
        # Fuzzy match - check words
        original_words = set(original_name_lower.split())
        remix_words = set(remix_core.split())
        # Remove common filler words
        filler_words = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "for"}
        original_words -= filler_words
        remix_words -= filler_words
        
        if original_words and remix_words:
            overlap = len(original_words & remix_words)
            if overlap >= len(original_words):  # All original words found
                score += 30
                reasons.append("full_word_match")
            elif overlap >= 1:
                score += 15 + (overlap * 5)  # 20-25 points based on overlap
                reasons.append("partial_word_match")
    
    # 2. Artist overlap (0-25 points)
    # Check if original artist is credited in the remix
    artist_overlap = any(orig in " ".join(remix_artists) for orig in original_artists_lower)
    if artist_overlap:
        score += 25
        reasons.append("artist_match")
    else:
        # Check if original artist mentioned in track name (feat. situations)
        if any(orig in remix_name for orig in original_artists_lower):
            score += 15
            reasons.append("artist_in_title")
    
    return min(100, score), reasons


def get_confidence_level(score):
    """Convert numeric score to confidence level."""
    if score >= 70:
        return "high"
    else:
        return "medium"  # Only scores >= 40 reach here (low scores filtered out)


def get_playlist(url):
    """Fetch playlist tracks from Spotify"""
    playlist_id = get_playlist_id(url)
    pattern = re.compile(r"\(.*?\)")
    sp = get_spotify_client()
    track_details = {}
    tracks = []
    items = []
    data = sp.playlist(playlist_id)
    track_details["playlist_name"] = data["name"]
    track_details["playlist_image"] = data["images"][0]["url"] if data["images"] else None
    track_details["playlist_owner"] = data["owner"]["display_name"]
    items += data["tracks"]["items"]
    next_page = data["tracks"]["next"]
    results = data["tracks"]

    while next_page is not None:
        results = sp.next(results)
        items.extend(results["items"])
        next_page = results.get("next")

    for item in items:
        track = item["track"]
        # Skip null tracks, local files, or tracks without required data
        if track is None or not track.get("id") or not track.get("external_urls"):
            continue
            
        name = track["name"]
        # Clean name - remove parenthetical content for better searching
        clean_name = re.sub(pattern, "", name).strip()
        
        # Remove common suffixes that pollute search (e.g., "- Bonus", "- Deluxe Edition")
        suffix_pattern = r'\s*[-–—]\s*(bonus|deluxe|remaster(ed)?|anniversary|edition|version|extended|original|radio|single|album|live|acoustic|instrumental|explicit|clean)(\s+\w+)*\s*$'
        clean_name = re.sub(suffix_pattern, "", clean_name, flags=re.IGNORECASE).strip()
        
        artists = [artist["name"] for artist in track.get("artists", [])]
        tracks.append({
            "id": track["id"],  # Include track ID to exclude originals
            "original_name": name,
            "clean_name": clean_name,
            "artists": artists,
            "album_art": track["album"]["images"][0]["url"] if track.get("album", {}).get("images") else None,
            "preview_url": track.get("preview_url"),
            "spotify_url": track["external_urls"].get("spotify", "")
        })
    
    return track_details, tracks, sp


def find_remix_candidates(sp, track, num_candidates=3, original_track_id=None):
    """
    Search for remix candidates for a single track.
    Returns multiple options with confidence scores.
    Only returns actual remixes (tracks with remix keywords in name).
    
    OPTIMIZED: 
    - Reduced to 2 queries (best first)
    - Early termination if high-confidence match found
    - Increased limit per query to reduce total API calls
    """
    candidates = []
    seen_ids = set()
    
    # Exclude the original track if we have its ID
    if original_track_id:
        seen_ids.add(original_track_id)
    
    # Optimized: Only 2 queries, best one first
    search_queries = [
        f"{track['clean_name']} {track['artists'][0]} remix",
        f"{track['clean_name']} remix",
    ]
    
    for query in search_queries:
        try:
            # Increased limit to 10 to get more candidates per query
            results = sp.search(query, type="track", limit=10, market="US")
            for item in results["tracks"]["items"]:
                if item["id"] in seen_ids:
                    continue
                    
                seen_ids.add(item["id"])
                confidence, reasons = calculate_match_confidence(
                    track["clean_name"],
                    track["artists"],
                    item
                )
                
                # Only include actual remixes (confidence > 0)
                if confidence > 0:
                    candidates.append({
                        "id": item["id"],
                        "name": item["name"],
                        "artists": [a["name"] for a in item["artists"]],
                        "album_art": item["album"]["images"][0]["url"] if item["album"]["images"] else None,
                        "preview_url": item.get("preview_url"),
                        "spotify_url": item["external_urls"]["spotify"],
                        "confidence": confidence,
                        "confidence_level": get_confidence_level(confidence),
                        "match_reasons": reasons,
                        "duration_ms": item["duration_ms"]
                    })
            
            # EARLY TERMINATION: Stop if we found a high-confidence match
            high_confidence_found = any(c["confidence"] >= 70 for c in candidates)
            if high_confidence_found and len(candidates) >= num_candidates:
                break
                
        except Exception:
            continue
    
    # Filter out low confidence matches (< 40) - only keep best and medium
    candidates = [c for c in candidates if c["confidence"] >= 40]
    
    # Sort by confidence and return top candidates
    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates[:num_candidates]


@shared_task(bind=True)
def preview_remixes(self, url):
    """
    Phase 1: Find remix candidates for all tracks and return for user review.
    
    OPTIMIZED: Uses parallel processing with ThreadPoolExecutor for ~5x faster results.
    """
    progress_recorder = ProgressRecorder(self)
    playlist_info, tracks, sp = get_playlist(url)
    
    total_tracks = len(tracks)
    
    preview_results = {
        "playlist_name": playlist_info["playlist_name"],
        "playlist_image": playlist_info.get("playlist_image"),
        "total_tracks": total_tracks,
        "tracks": []
    }
    
    # Process tracks in parallel for significant speedup
    # Use 5 workers to balance speed vs API rate limits
    MAX_WORKERS = 5
    results_dict = {}  # Store results by index to maintain order
    completed_count = 0
    
    def process_single_track(index, track):
        """Process a single track and return results."""
        candidates = find_remix_candidates(sp, track, original_track_id=track.get("id"))
        return index, {
            "original": {
                "name": track["original_name"],
                "artists": track["artists"],
                "album_art": track["album_art"],
                "spotify_url": track["spotify_url"]
            },
            "candidates": candidates,
            "best_match": candidates[0] if candidates else None,
            "has_high_confidence": any(c["confidence_level"] == "high" for c in candidates)
        }
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_single_track, i, track): i 
            for i, track in enumerate(tracks)
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            try:
                index, track_result = future.result(timeout=30)
                results_dict[index] = track_result
            except Exception:
                # If a track fails, add empty result
                index = futures[future]
                results_dict[index] = {
                    "original": {
                        "name": tracks[index]["original_name"],
                        "artists": tracks[index]["artists"],
                        "album_art": tracks[index]["album_art"],
                        "spotify_url": tracks[index]["spotify_url"]
                    },
                    "candidates": [],
                    "best_match": None,
                    "has_high_confidence": False
                }
            
            completed_count += 1
            progress_recorder.set_progress(completed_count, total_tracks)
    
    # Sort results back to original order
    for i in range(total_tracks):
        preview_results["tracks"].append(results_dict[i])
    
    # Calculate summary statistics
    high_confidence_count = 0
    medium_confidence_count = 0
    low_confidence_count = 0
    no_match_count = 0
    
    for track_result in preview_results["tracks"]:
        candidates = track_result["candidates"]
        if candidates:
            best_level = candidates[0]["confidence_level"]
            if best_level == "high":
                high_confidence_count += 1
            elif best_level == "medium":
                medium_confidence_count += 1
            else:
                low_confidence_count += 1
        else:
            no_match_count += 1
    
    preview_results["summary"] = {
        "high_confidence": high_confidence_count,
        "medium_confidence": medium_confidence_count,
        "low_confidence": low_confidence_count,
        "no_match": no_match_count
    }
    
    return preview_results


@shared_task(bind=True)
def create_remix_playlist(self, playlist_name, selected_tracks, original_url):
    """
    Phase 2: Create the playlist with user-selected tracks on the central account.
    selected_tracks is a list of Spotify track IDs.
    
    The playlist is created and made public so users can access it.
    """
    progress_recorder = ProgressRecorder(self)
    sp = get_spotify_client()
    
    # Get original playlist info for author
    playlist_info, _, _ = get_playlist(original_url)
    
    user_id = sp.me()["id"]
    
    # Create the playlist as public so users can access it
    playlist = sp.user_playlist_create(
        user_id, 
        name=f"{playlist_name} (Remixed)", 
        public=True,
        description="Curated by Remixify with your help."
    )
    
    playlist_id = playlist["id"]
    
    # Add tracks in chunks of 100
    if len(selected_tracks) > 100:
        chunks = chunker(selected_tracks)
        for i, chunk in enumerate(chunks):
            sp.user_playlist_add_tracks(user_id, playlist_id, chunk)
            progress_recorder.set_progress(i + 1, len(chunks))
    else:
        sp.user_playlist_add_tracks(user_id, playlist_id, selected_tracks)
        progress_recorder.set_progress(1, 1)
    
    playlist_details = sp.user_playlist(user_id, playlist_id)
    
    # Get playlist image (use first image if available)
    image_url = None
    if playlist_details.get("images") and len(playlist_details["images"]) > 0:
        image_url = playlist_details["images"][0]["url"]
    
    # Save to database for recent playlists display
    CreatedPlaylist.objects.create(
        name=playlist_details["name"],
        spotify_url=playlist_details["external_urls"]["spotify"],
        image_url=image_url,
        track_count=len(selected_tracks),
        original_author=playlist_info.get("playlist_owner", "")
    )
    
    # Increment the global playlist counter in Redis
    increment_playlist_count()
    
    # Keep only the most recent 20 playlists to avoid database bloat
    old_playlists = CreatedPlaylist.objects.all()[20:]
    for playlist_obj in old_playlists:
        playlist_obj.delete()
    
    return {
        "url": playlist_details["external_urls"]["spotify"],
        "name": playlist_details["name"],
        "track_count": len(selected_tracks)
    }


# Keep legacy function for backwards compatibility
@shared_task(bind=True)
def create_remix(self, url):
    """Legacy: Direct remix creation without preview. Uses central account."""
    sp = get_spotify_client()
    playlist_info, tracks, _ = get_playlist(url)
    track_ids = []
    progress_recorder = ProgressRecorder(self)
    
    for index, track in enumerate(tracks):
        candidates = find_remix_candidates(sp, track, num_candidates=1)
        if candidates and candidates[0]["confidence_level"] in ["high", "medium"]:
            track_ids.append(candidates[0]["id"])
        progress_recorder.set_progress(index + 1, len(tracks))
    
    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(
        user_id, 
        name=f"{playlist_info['playlist_name']} (Remixed)",
        public=True,
        description="Curated by Remixify with your help."
    )
    
    playlist_id = playlist["id"]
    
    if len(track_ids) > 100:
        for chunk in chunker(track_ids):
            sp.user_playlist_add_tracks(user_id, playlist_id, chunk)
    else:
        sp.user_playlist_add_tracks(user_id, playlist_id, track_ids)
    
    playlist_details = sp.user_playlist(user_id, playlist_id)
    return playlist_details["external_urls"]["spotify"]
