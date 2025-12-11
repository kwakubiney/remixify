"""
Central Spotify OAuth Module

This module uses a single central Spotify account for all API operations.
Instead of each user authenticating, we use ONE stored refresh token 
that belongs to the app owner's Spotify account.
"""
import time
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
from decouple import config


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
            if CentralAccountCacheHandler._token_cache.get("expires_at", 0) > time.time() + 60:
                return CentralAccountCacheHandler._token_cache
        
        # Return a token structure that triggers refresh
        # SpotifyOAuth will use the refresh_token to get a new access_token
        return {
            "access_token": None,
            "refresh_token": self.refresh_token,
            "expires_at": 0,  # Expired, will trigger refresh
            "scope": "user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify"
        }
    
    def save_token_to_cache(self, token_info):
        """Save refreshed token to class-level cache."""
        CentralAccountCacheHandler._token_cache = token_info


def get_spotify_oauth():
    """
    Get SpotifyOAuth manager for the central account.
    No user_id needed - uses the central account's credentials.
    """
    return SpotifyOAuth(
        client_id=config("SPOTIPY_CLIENT_ID"),
        client_secret=config("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=config("REDIRECT_URI"),
        cache_handler=CentralAccountCacheHandler(),
        scope="user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify"
    )


def get_spotify_client():
    """
    Get authenticated Spotify client for the central account.
    This is the main entry point for all Spotify API operations.
    """
    oauth = get_spotify_oauth()
    return Spotify(auth_manager=oauth)


# Legacy functions for backwards compatibility during migration
def oauth_factory(user_id=None):
    """Legacy wrapper - now ignores user_id and returns central OAuth."""
    return get_spotify_oauth()


def spotify_client(oauth=None):
    """Legacy wrapper - returns central Spotify client."""
    return get_spotify_client()
