"""
Central Spotify OAuth Module

This module uses a single central Spotify account for all API operations.
Instead of each user authenticating, we use ONE stored refresh token 
that belongs to the app owner's Spotify account.
"""
import time
import logging
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from decouple import config

logger = logging.getLogger(__name__)


class CentralAccountCacheHandler(CacheHandler):
    """
    Cache handler that uses a centrally stored refresh token.
    The refresh token is stored in environment variables.
    Access tokens are cached in memory and refreshed as needed.
    """
    _token_cache = None  # Class-level cache for the token
    
    def __init__(self):
        self.refresh_token = config("SPOTIFY_REFRESH_TOKEN", default=None)
        if not self.refresh_token:
            raise ValueError(
                "SPOTIFY_REFRESH_TOKEN environment variable is required. "
                "Run 'python manage.py generate_spotify_token' to generate one."
            )
    
    def get_cached_token(self):
        """Return token info from cache or construct from refresh token."""
        # If we have a valid cached token, return it
        if CentralAccountCacheHandler._token_cache:
            # Check if token is still valid (with 60s buffer)
            expires_at = CentralAccountCacheHandler._token_cache.get("expires_at", 0)
            if expires_at > time.time() + 60:
                logger.info(f"[DEBUG] get_cached_token: Using valid cached token (expires in {int(expires_at - time.time())}s)")
                return CentralAccountCacheHandler._token_cache
            else:
                logger.info(f"[DEBUG] get_cached_token: Cached token expired or expiring soon")
        else:
            logger.info("[DEBUG] get_cached_token: No cached token found, will trigger refresh")
        
        # Return a token structure that triggers refresh
        # SpotifyOAuth will use the refresh_token to get a new access_token
        logger.info("[DEBUG] get_cached_token: Returning expired token structure to trigger refresh")
        return {
            "access_token": None,
            "refresh_token": self.refresh_token,
            "expires_at": 0,  # Expired, will trigger refresh
            "scope": "user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify"
        }
    
    def save_token_to_cache(self, token_info):
        """Save refreshed token to class-level cache."""
        logger.info(f"[DEBUG] save_token_to_cache: Saving new token (expires_at: {token_info.get('expires_at', 'unknown')})")
        CentralAccountCacheHandler._token_cache = token_info


def get_spotify_oauth():
    """
    Get SpotifyOAuth manager for the central account.
    No user_id needed - uses the central account's credentials.
    """
    logger.info("[DEBUG] get_spotify_oauth called")
    try:
        oauth = SpotifyOAuth(
            client_id=config("SPOTIPY_CLIENT_ID"),
            client_secret=config("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=config("REDIRECT_URI"),
            cache_handler=CentralAccountCacheHandler(),
            scope="user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify",
            open_browser=False  # CRITICAL: Prevent hanging on server environments
        )
        logger.info("[DEBUG] SpotifyOAuth manager created successfully")
        return oauth
    except Exception as e:
        logger.error(f"[DEBUG] Failed to create SpotifyOAuth: {type(e).__name__}: {str(e)}")
        raise


def get_spotify_client():
    """
    Get authenticated Spotify client for the central account.
    This is the main entry point for all Spotify API operations.
    """
    logger.info("[DEBUG] get_spotify_client called")
    try:
        oauth = get_spotify_oauth()
        logger.info("[DEBUG] Creating Spotify client with oauth manager...")
        
        # Create client with request timeout to prevent indefinite hangs
        # NOTE: Do NOT add custom HTTPAdapter - it causes spotipy to hang!
        # The default spotipy session works fine with just the timeout.
        client = Spotify(
            auth_manager=oauth,
            requests_timeout=10  # 10 second timeout per request
        )
        
        # Add response hook to log HTTP responses for debugging
        def log_response(response, *args, **kwargs):
            url_short = response.request.url[:80] if response.request.url else "?"
            logger.info(f"[HTTP] {response.request.method} {url_short}... -> {response.status_code}")
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', 'unknown')
                logger.warning(f"[HTTP] RATE LIMITED! Retry-After: {retry_after}s")
            elif response.status_code >= 400:
                logger.warning(f"[HTTP] Error response: {response.text[:200] if response.text else 'no body'}")
            return response
        
        client._session.hooks['response'].append(log_response)
        
        logger.info("[DEBUG] Spotify client created with timeout and response logging")
        return client
    except Exception as e:
        logger.error(f"[DEBUG] Failed to create Spotify client: {type(e).__name__}: {str(e)}")
        raise


# Legacy functions for backwards compatibility during migration
def oauth_factory(user_id=None):
    """Legacy wrapper - now ignores user_id and returns central OAuth."""
    return get_spotify_oauth()


def spotify_client(oauth=None):
    """Legacy wrapper - returns central Spotify client."""
    return get_spotify_client()

