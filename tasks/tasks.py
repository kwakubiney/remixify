from celery import shared_task
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from celery_progress.backend import ProgressRecorder
from tasks.helpers import chunker, get_playlist_id
from tasks.models import CreatedPlaylist
from tasks.redis_utils import increment_playlist_count
from authentication.oauth import get_spotify_client

logger = logging.getLogger(__name__)


def choose_best_canonical_track(
    *,
    wanted_title_norm: str,
    wanted_artist: str,
    items: list[dict],
) -> dict | None:
    """Pick the best canonical/original track from Spotify search items.

    Pure helper (no API calls) so we can regression-test selection behavior.
    The caller is responsible for providing results from a *title+artist* constrained search.

    Selection rules (in order):
    1) Must normalize to the same base title as `wanted_title_norm`
    2) Must have artist token overlap with `wanted_artist`
    3) Prefer a truly plain original when it exists (raw name exactly equals base title)
    4) Prefer non-versioned names over versioned
    """
    version_hint_words = [
        "remix",
        "remixed",
        "rmx",
        "edit",
        "rework",
        "bootleg",
        "flip",
        "mix",
        "version",
        "extended",
        "club",
        "radio",
        "dub",
        "vip",
    ]

    def is_versioned_title(name: str) -> bool:
        name_lc = (name or "").lower()
        return any(w in name_lc for w in version_hint_words)

    def has_artist_link(candidate_artists: list[str], required_artist: str) -> bool:
        wanted = artist_tokens(required_artist)
        if not wanted:
            return False
        cand_tokens = set()
        for a in candidate_artists or []:
            cand_tokens |= artist_tokens(a)
        if not cand_tokens:
            return False
        return bool(wanted & cand_tokens)

    wanted_title_norm = wanted_title_norm or ""
    wanted_tokens = set(wanted_title_norm.split())

    best_item = None
    best_score = -10_000

    for it in items or []:
        raw_name = it.get("name") or ""
        cand_title_norm = normalize_title(raw_name)
        if not cand_title_norm:
            continue
        if cand_title_norm != wanted_title_norm:
            continue

        cand_artists = [a.get("name", "") for a in (it.get("artists") or [])]
        if not cand_artists:
            continue
        if not has_artist_link(cand_artists, wanted_artist):
            continue

        name_versioned = is_versioned_title(raw_name)
        is_plain_exact = raw_name.strip().lower() == wanted_title_norm.strip().lower()

        score = 0
        if is_plain_exact:
            score += 10_000
        if not name_versioned:
            score += 1_000
        else:
            score -= 1_000
        score -= len(raw_name)
        score += 10 * len(wanted_tokens & set(cand_title_norm.split()))

        if score > best_score:
            best_score = score
            best_item = it

    return best_item


def normalize_title(title):
    """
    Normalize a song title for comparison.
    Removes parenthetical content, featured artists, and common suffixes.
    Returns the core song name.
    """
    title = title.lower().strip()
    
    # Remove content in parentheses and brackets (often contains remix info, features, etc.)
    title = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', title)
    
    # Remove "feat.", "ft.", "featuring", etc.
    title = re.sub(r'\s*(feat\.?|ft\.?|featuring)\s+.*$', '', title, flags=re.IGNORECASE)
    
    # Remove common suffixes after dash
    # 1) Simple: "Song - Remix" / "Song - Extended" / etc.
    title = re.sub(
        r"\s*[-–—]\s*(remix|remaster|radio|extended|club|vip|edit|mix|version|original|single|album|live|acoustic|instrumental|explicit|clean|bonus|deluxe|anniversary|edition)\b.*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    # 2) More general: version labels that end with a known tail word.
    # This catches cases like "Hey Hey - DF's Attention Vocal Mix" where the suffix
    # doesn't start with "mix" but *ends* with "mix".
    title = re.sub(
        r"\s*[-–—]\s*.*\b(vocal\s+mix|instrumental\s+mix|dub\s+mix|club\s+mix|extended\s+mix|radio\s+edit|vip|mix|edit|remix|version)\b\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    )
    
    # Remove trailing/leading punctuation and whitespace
    title = re.sub(r'^[\s\-–—:]+|[\s\-–—:]+$', '', title)
    
    return title.strip()


def extract_remix_base_title(remix_name):
    """
    Extract the base song title from a remix name.
    
    Examples:
    - "Alien - Club Remix" → "alien"
    - "Bad Guy (Tiesto Remix)" → "bad guy"  
    - "Blinding Lights - Major Lazer Remix" → "blinding lights"
    - "A Bar Song (Tipsy) - Remix" → "a bar song tipsy" (IMPORTANT: this is NOT "Tipsy")
    """
    name = remix_name.lower().strip()
    
    # First, try to split on " - " and take the first part (before remix info)
    if " - " in name:
        parts = name.split(" - ")
        # Check if first part looks like the song title (not the remix credit)
        first_part = parts[0].strip()
        # If the first part doesn't contain remix keywords, it's likely the title
        remix_indicators = [
            "remix",
            "remixed",
            "rmx",
            "edit",
            "bootleg",
            "rework",
            "flip",
            "version",
            "remaster",
            "extended",
            "club",
            "dub",
            "vip",
        ]
        if not any(ind in first_part for ind in remix_indicators):
            name = first_part
    
    # Remove parenthetical remix info but KEEP other parenthetical content that's part of the title
    # e.g., "A Bar Song (Tipsy)" should keep "(Tipsy)" as it's part of the title
    # but "Bad Guy (Tiesto Remix)" should remove "(Tiesto Remix)"
    
    # Only remove parentheses if they contain remix-related words
    def remove_remix_parens(match):
        content = match.group(1).lower()
        remix_words = ["remix", "rmx", "mix", "edit", "bootleg", "rework", "flip", "version", "remaster", "extended", "club", "radio", "vip", "dub"]
        if any(word in content for word in remix_words):
            return ""
        return match.group(0)  # Keep the parenthetical content
    
    name = re.sub(r'\s*\(([^)]+)\)', remove_remix_parens, name)
    name = re.sub(r'\s*\[([^\]]+)\]', remove_remix_parens, name)
    
    # Clean up
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def normalize_artist(artist_name: str) -> str:
    """Normalize an artist name for safer matching (lowercase, strip punctuation, collapse spaces)."""
    if not artist_name:
        return ""
    artist_name = artist_name.lower().strip()
    # Remove punctuation that often varies in credits (e.g., A$AP Rocky / ASAP Rocky)
    artist_name = re.sub(r"[^a-z0-9\s]", " ", artist_name)
    artist_name = re.sub(r"\s+", " ", artist_name).strip()
    return artist_name


def artist_tokens(name: str) -> set[str]:
    """Tokenize artist name; avoids substring matching bugs (e.g., 'ram' matching 'rema')."""
    norm = normalize_artist(name)
    if not norm:
        return set()
    tokens = set(norm.split())
    # remove very common tokens that don't help identify an artist
    tokens -= {"the", "dj", "mc"}
    return tokens


def calculate_match_confidence(original_name, original_artists, remix_track):
    """
    Calculate a confidence score for how well a remix matches the original track.
    
    STRICT MATCHING RULES:
    1. For single-word titles like "Why", "Alien", "Tipsy" - ONLY exact matches allowed
    2. The remix must be OF the original song, not just contain the word
    3. Artist verification is required for weak matches
    """
    remix_name = remix_track["name"].lower()
    original_normalized = normalize_title(original_name)
    remix_artists = [a["name"] for a in remix_track["artists"]]
    original_artists_lower = [a for a in original_artists]
    
    # STEP 1: Must contain a *version* keyword.
    # We accept a careful set of DJ-usable alternates in addition to explicit remixes.
    # This is intentionally conservative: title + artist checks do the real filtering.
    version_keywords = [
        # explicit remixes/edits
        "remix",
        "remixed",
        "rmx",
        "edit",
        "bootleg",
        "rework",
        "flip",
        "version",
        # DJ-friendly alternates
        "extended mix",
        "extended",
        "club mix",
        "club",
        "dub mix",
        "dub",
        "vip",
        "vip mix",
        "radio edit",
    ]
    has_remix_keyword = any(keyword in remix_name for keyword in version_keywords)
    
    if not has_remix_keyword:
        return 0, ["not_a_version"]
    
    # STEP 2: Extract the base title from the remix
    remix_base = extract_remix_base_title(remix_name)
    
    # STEP 3: Compare titles - this is the CRITICAL check
    score = 0
    reasons = ["is_remix"]
    
    # Get word sets for comparison
    original_words = set(original_normalized.split())
    remix_words = set(remix_base.split())
    
    stop_words = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "for", "is", "it", "my", "your", "i", "you", "me", "we"}
    original_significant = original_words - stop_words
    remix_significant = remix_words - stop_words
    
    # Fallback if all words are stop words
    if not original_significant:
        original_significant = original_words
    if not remix_significant:
        remix_significant = remix_words
    
    # CRITICAL: Determine if this is a "short title" (1-2 significant words)
    # Short titles like "Why", "Alien", "Bad Guy" need STRICT matching
    is_short_title = len(original_significant) <= 2
    
    # Method 1: Exact match (best case)
    if original_normalized == remix_base:
        score += 50
        reasons.append("exact_title_match")
    
    # Method 2: Exact word match (handles punctuation differences)
    elif original_significant == remix_significant:
        score += 48
        reasons.append("exact_words_match")
    
    # Method 3: For SHORT titles, be VERY strict - no fuzzy matching
    elif is_short_title:
        # The remix title words must EXACTLY match original words
        # "Why" should NOT match "Why Can't It Wait Till Morning"
        # But "Why" SHOULD match "Why - Club Remix" (remix_base would be "why")
        
        # Allow only if remix has at most 1 extra word
        if original_significant <= remix_significant:
            extra_words = len(remix_significant - original_significant)
            if extra_words == 0:
                score += 45
                reasons.append("short_title_exact")
            elif extra_words == 1:
                # Only allow 1 extra word if original is 2+ words
                if len(original_significant) >= 2:
                    score += 35
                    reasons.append("short_title_close")
                # Single word + 1 extra = too risky, no match
        # Otherwise: NO MATCH for short titles
    
    # Method 4: For LONGER titles (3+ words), allow more flexibility
    else:
        overlap = original_significant & remix_significant
        overlap_ratio = len(overlap) / len(original_significant) if original_significant else 0
        
        if overlap_ratio >= 0.8:
            score += 45
            reasons.append("high_word_overlap")
        elif overlap_ratio >= 0.6 and len(overlap) >= 2:
            score += 35
            reasons.append("good_word_overlap")
        elif overlap_ratio >= 0.5 and len(overlap) >= 3:
            score += 25
            reasons.append("moderate_word_overlap")
        # Lower overlap = no match
    
    # If no title match found, reject immediately
    if score == 0:
        return 0, ["title_mismatch"]
    
    # STEP 4: Artist verification (STRICT)
    # We want to be careful here: Spotify search returns lots of noisy matches.
    # A real remix usually credits the original artist OR the remix is by the original artist.
    remix_artist_text = normalize_artist(" ".join(remix_artists))
    remix_artist_token_set = set()
    for a in remix_artists:
        remix_artist_token_set |= artist_tokens(a)

    original_artist_token_sets = [artist_tokens(a) for a in original_artists_lower]
    original_artist_token_sets = [s for s in original_artist_token_sets if s]

    # Token overlap is safer than substring matching.
    def has_artist_token_overlap() -> bool:
        for orig_tokens in original_artist_token_sets:
            if orig_tokens and (orig_tokens <= remix_artist_token_set):
                return True
            if orig_tokens and len(orig_tokens & remix_artist_token_set) >= max(1, min(2, len(orig_tokens))):
                return True
        return False

    artist_credited = has_artist_token_overlap()
    # Artist mentioned in title (rare but happens). Use normalized form + word boundaries.
    artist_in_title = False
    for orig in original_artists_lower:
        o = normalize_artist(orig)
        if not o or len(o) < 3:
            continue
        if re.search(rf"\b{re.escape(o)}\b", normalize_artist(remix_name)):
            artist_in_title = True
            break
    
    if artist_credited:
        score += 25
        reasons.append("artist_credited")
    elif artist_in_title:
        score += 15
        reasons.append("artist_in_title")
    else:
        # If we can't connect the remix to the original artist at all, we should be conservative.
        # Allow ONLY when title match is extremely strong (exact match); otherwise reject.
        if "exact_title_match" in reasons or "exact_words_match" in reasons:
            score -= 10
            reasons.append("no_artist_penalty")
        else:
            return 0, ["no_artist_link"]
    
    # STEP 5: Final sanity check with sequence similarity
    seq_ratio = SequenceMatcher(None, original_normalized, remix_base).ratio()
    
    # For short titles, require higher similarity
    if is_short_title and seq_ratio < 0.5 and score < 60:
        return 0, ["short_title_low_similarity"]
    
    # For any title, very low similarity is a red flag
    if seq_ratio < 0.25 and score < 50:
        return 0, ["low_similarity"]
    
    return min(100, score), reasons


def get_confidence_level(score):
    """Convert numeric score to confidence level."""
    if score >= 70:
        return "high"
    else:
        return "medium"  # Only scores >= 40 reach here (low scores filtered out)


def get_playlist(url):
    """Fetch playlist tracks from Spotify"""
    from spotipy.exceptions import SpotifyException
    
    logger.info(f"[DEBUG] get_playlist called with URL: {url}")
    
    playlist_id = get_playlist_id(url)
    
    logger.info(f"[DEBUG] Extracted playlist ID: {playlist_id}")
    
    # Check if this is a Spotify-generated playlist (known limitation)
    # These IDs start with '37i9dQZF1' (Daily Mix, Discover Weekly, etc.)
    is_spotify_generated = playlist_id and playlist_id.startswith('37i9dQZF1')
    if is_spotify_generated:
        logger.warning(f"Spotify-generated playlist detected: {playlist_id}")
        raise ValueError("Spotify-generated playlists (like Daily Mix, Discover Weekly, or artist \"This Is\" playlists) aren't accessible via the API. Please use a playlist you or someone else created.")
    
    pattern = re.compile(r"\(.*?\)")
    logger.info(f"[DEBUG] About to get Spotify client...")
    try:
        sp = get_spotify_client()
        logger.info(f"[DEBUG] Spotify client obtained successfully")
    except Exception as e:
        logger.error(f"[DEBUG] Failed to get Spotify client: {type(e).__name__}: {str(e)}")
        raise
    track_details = {}
    tracks = []
    items = []
    
    try:
        logger.info(f"[DEBUG] Fetching playlist data from Spotify API...")
        data = sp.playlist(playlist_id)
        logger.info(f"[DEBUG] Playlist data fetched successfully: {data.get('name', 'Unknown')}")
    except SpotifyException as e:
        logger.error(f"SpotifyException for playlist {playlist_id}: {e.http_status} - {str(e)}")
        if e.http_status == 404:
            # Double-check for Spotify-generated playlists that slipped through
            if playlist_id and playlist_id.startswith('37i'):
                raise ValueError("This appears to be a Spotify-generated playlist which isn't accessible via the API. Please use a playlist you or someone else created.")
            raise ValueError("This playlist is private or doesn't exist. Please use a public playlist.")
        elif e.http_status == 401:
            raise ValueError("Authentication error. Please try again later.")
        elif e.http_status == 403:
            raise ValueError("Access denied. This playlist may be restricted.")
        else:
            raise ValueError("Unable to load this playlist. Please check the link and try again.")
    except Exception as e:
        logger.error(f"Unexpected error fetching playlist {playlist_id}: {str(e)}", exc_info=True)
        raise ValueError("Unable to load this playlist. Please try again.")
    
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
        # Clean name for searching: strip remix/mix/edit/version/remaster/etc.
        # Important for cases where the source track is *already* a remix/edit.
        clean_name = normalize_title(name)
        
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
    
    # Build a base title for searching even if the playlist track is already a remix/edit.
    # Example: "Fall For You (Sandy Rivera's Classic Mix) - Moodymann Edit" -> "fall for you"
    version_hint_words = [
        "remix",
        "remixed",
        "rmx",
        "edit",
        "rework",
        "bootleg",
        "flip",
        "mix",
        "version",
        "extended",
        "club",
        "radio",
        "dub",
        "vip",
    ]

    base_title = normalize_title(track.get("original_name") or track.get("clean_name") or "")
    primary_artist = (track.get("artists") or [""])[0]
    # If the original track name contains mix/remix/edit markers, it's a hint that the playlist track might
    # itself be a *version*.
    # In that case: do a reverse lookup to find the *canonical/original* song first, then search alternates.
    original_name_lc = (track.get("original_name") or "").lower()
    original_already_versioned = any(w in original_name_lc for w in version_hint_words)

    def resolve_canonical_track_id(title: str, artist: str) -> tuple[str | None, str]:
        """Best-effort resolve of the canonical/original track for a versioned source.

        Returns (track_id, canonical_title). canonical_title may fall back to the input title.
        Kept intentionally conservative to avoid extra noisy API calls.
        """
        if not title or not artist:
            return None, title

        # Use only documented field filters; then do deterministic post-filtering below.
        query = f"track:{title} artist:{artist}"
        try:
            res = sp.search(query, type="track", limit=20)
        except Exception:
            return None, title

        items = (res.get("tracks") or {}).get("items") or []
        if not items:
            return None, title

        best_item = choose_best_canonical_track(
            wanted_title_norm=title,
            wanted_artist=artist,
            items=items,
        )
        if best_item:
            canonical_title = normalize_title(best_item.get("name") or title)
            return best_item.get("id"), canonical_title

        # If nothing passes gates, fall back.
        return None, title

    # Reverse lookup: attempt to use the canonical/original track as the search seed.
    search_seed_title = base_title
    canonical_track_id = None
    if original_already_versioned:
        canonical_track_id, canonical_title = resolve_canonical_track_id(base_title, primary_artist)
        if canonical_title:
            search_seed_title = canonical_title
        if canonical_track_id:
            seen_ids.add(canonical_track_id)

    # IMPORTANT: when the playlist track is already a version (mix/edit/etc), we still want to match
    # candidates against the canonical/base title, not the full versioned title.
    match_original_title = search_seed_title if original_already_versioned else (track.get("clean_name") or base_title)

    # Search strategy (ordered):
    # 1) Base title + primary artist + remix (best precision)
    # 2) Base title + remix
    # 3) Base title + primary artist (fallback to collect versioned titles; scoring will filter to remixes)
    # 4) If original already includes remix-ish words, also try "version" queries.
    search_queries = [
        f"{search_seed_title} {primary_artist} remix",
        f"{search_seed_title} remix",
        f"{search_seed_title} {primary_artist}",
    ]
    if original_already_versioned:
        search_queries.extend(
            [
                f"{search_seed_title} {primary_artist} mix",
                f"{search_seed_title} {primary_artist} edit",
                f"{search_seed_title} {primary_artist} version",
            ]
        )
    
    for query in search_queries:
        try:
            # Increased limit to 10 to get more candidates per query
            results = sp.search(query, type="track", limit=10)
            for item in results["tracks"]["items"]:
                if item["id"] in seen_ids:
                    continue
                    
                seen_ids.add(item["id"])
                confidence, reasons = calculate_match_confidence(
                    match_original_title,
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
    from spotipy.exceptions import SpotifyException
    
    logger.info(f"[DEBUG] ========================================")
    logger.info(f"[DEBUG] Starting preview_remixes task")
    logger.info(f"[DEBUG] URL: {url}")
    logger.info(f"[DEBUG] Task ID: {self.request.id}")
    logger.info(f"[DEBUG] ========================================")
    
    try:
        logger.info(f"[DEBUG] Creating ProgressRecorder...")
        progress_recorder = ProgressRecorder(self)
        logger.info(f"[DEBUG] ProgressRecorder created successfully")
        
        logger.info(f"[DEBUG] Calling get_playlist...")
        playlist_info, tracks, sp = get_playlist(url)
        logger.info(f"[DEBUG] get_playlist returned successfully")
        
        total_tracks = len(tracks)
        logger.info(f"[DEBUG] Playlist ingested successfully")
        logger.info(f"[DEBUG] Playlist name: {playlist_info['playlist_name']}")
        logger.info(f"[DEBUG] Total tracks: {total_tracks}")
        
        preview_results = {
            "playlist_name": playlist_info["playlist_name"],
            "playlist_image": playlist_info.get("playlist_image"),
            "total_tracks": total_tracks,
            "tracks": []
        }
    except ValueError as e:
        # User-friendly errors from get_playlist
        logger.error(f"[DEBUG] ValueError in get_playlist: {str(e)}")
        raise
    except SpotifyException as e:
        # Catch any Spotify errors that weren't handled in get_playlist
        logger.error(f"[DEBUG] SpotifyException in preview_remixes: {e.http_status} - {str(e)}", exc_info=True)
        if e.http_status == 404:
            raise ValueError("This playlist is private or doesn't exist. Please use a public playlist.")
        elif e.http_status == 429:
            raise ValueError("Too many requests. Please try again in a moment.")
        else:
            raise ValueError("Unable to load this playlist. Please check the link and try again.")
    except Exception as e:
        logger.error(f"[DEBUG] Unexpected exception in preview_remixes: {type(e).__name__}: {str(e)}", exc_info=True)
        raise ValueError("Something went wrong. Please try again.")
    
    # Process tracks in parallel for significant speedup
    # Use 5 workers to balance speed vs API rate limits
    MAX_WORKERS = 5
    results_dict = {}  # Store results by index to maintain order
    completed_count = 0
    failed_count = 0
    
    logger.info(f"[DEBUG] Starting parallel track processing with {MAX_WORKERS} workers")
    logger.info(f"[DEBUG] Processing {total_tracks} tracks...")
    
    def process_single_track(index, track):
        """Process a single track and return results."""
        logger.debug(f"[DEBUG] Processing track {index}: {track.get('original_name', 'Unknown')}")
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
                failed_count += 1
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
            if completed_count % 10 == 0 or completed_count == 1:
                logger.info(f"[DEBUG] Progress update: {completed_count}/{total_tracks} tracks processed")
            progress_recorder.set_progress(completed_count, total_tracks)

    logger.info(
        "preview_remixes complete: total_tracks=%s processed=%s failed=%s",
        total_tracks,
        completed_count,
        failed_count,
    )
    
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
