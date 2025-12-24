"""
Central Spotify OAuth Module

This module uses a single central Spotify account for all API operations.
Instead of each user authenticating, we use ONE stored refresh token 
that belongs to the app owner's Spotify account.
"""
import time
import logging
import random
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyOAuth
from spotipy import Spotify
import spotipy
from decouple import config

logger = logging.getLogger(__name__)


class CentralAccountCacheHandler(CacheHandler):
    """
    Cache handler that uses a centrally stored refresh token.
    The refresh token is stored in environment variables.
    Access tokens are cached in memory and refreshed as needed.
    """
    _token_caches = {}  # Class-level cache dictionary keyed by token_env_key
    
    def __init__(self, token_env_key="SPOTIFY_REFRESH_TOKEN"):
        self.token_env_key = token_env_key
        self.refresh_token = config(token_env_key, default=None)
        if not self.refresh_token:
            # Only raise if it's the primary token. Secondary tokens might be missing but we shouldn't crash until we try to use them.
            if token_env_key == "SPOTIFY_REFRESH_TOKEN":
                raise ValueError(
                    f"{token_env_key} environment variable is required. "
                    "Run 'python manage.py generate_spotify_token' to generate one."
                )
    
    def get_cached_token(self):
        """Return token info from cache or construct from refresh token."""
        # Get the specific cache for this token key
        current_cache = CentralAccountCacheHandler._token_caches.get(self.token_env_key)

        # If we have a valid cached token, return it
        if current_cache:
            expires_at = current_cache.get("expires_at", 0)
            if expires_at > time.time() + 60:
                return current_cache
        
        if not self.refresh_token:
             return None

        # Return a token structure that triggers refresh
        return {
            "access_token": None,
            "refresh_token": self.refresh_token,
            "expires_at": 0,
            "scope": "user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify"
        }
    
    def save_token_to_cache(self, token_info):
        """Save refreshed token to class-level cache."""
        CentralAccountCacheHandler._token_caches[self.token_env_key] = token_info


def get_spotify_oauth(index=0):
    """
    Get SpotifyOAuth manager for a specific client index.
    index=0 uses default credentials.
    index=1 uses _2 credentials, etc.
    """
    suffix = f"_{index + 1}" if index > 0 else ""
    # Special naming convention for index 0 (no suffix)
    
    client_id_key = f"SPOTIPY_CLIENT_ID{suffix}"
    client_secret_key = f"SPOTIPY_CLIENT_SECRET{suffix}"
    refresh_token_key = f"SPOTIFY_REFRESH_TOKEN{suffix}"
    
    client_id = config(client_id_key, default=None)
    client_secret = config(client_secret_key, default=None)
    
    if not client_id or not client_secret:
        return None

    try:
        oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=config("REDIRECT_URI"),
            cache_handler=CentralAccountCacheHandler(token_env_key=refresh_token_key),
            scope="user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify",
            open_browser=False
        )
        return oauth
    except Exception as e:
        logger.error(f"Failed to create SpotifyOAuth for index {index}: {type(e).__name__}: {str(e)}")
        return None

def create_raw_spotify_client(index=0):
    """Create a standard spotipy.Spotify client for the given index."""
    oauth = get_spotify_oauth(index)
    if not oauth:
        return None
        
    client = Spotify(
        auth_manager=oauth,
        requests_timeout=10,
        retries=0,
        status_retries=0,
        backoff_factor=0.3
    )
    
    # Add response hook to log HTTP responses for debugging
    def log_response(response, *args, **kwargs):
        url_short = response.request.url[:80] if response.request.url else "?"
        # Only log 429s prominently, debug others
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', 'unknown')
            logger.warning(f"[HTTP][Client {index}] RATE LIMITED! Retry-After: {retry_after}s")
        elif response.status_code >= 400:
            logger.warning(f"[HTTP][Client {index}] Error response: {response.status_code} - {response.text[:200] if response.text else 'no body'}")
        else:
            logger.debug(f"[HTTP][Client {index}] {response.request.method} {url_short}... -> {response.status_code}")
        return response
    
    client._session.hooks['response'].append(log_response)
    return client


class RotatingSpotifyClient:
    """
    A wrapper around spotipy.Spotify that automatically rotates through
    available credentials when a 429 Rate Limit error is encountered.
    """
    def __init__(self):
        self.current_index = 0
        self.max_clients = 10
        self._current_client_instance = None
        self._available_indices = self._discover_available_indices()

    def _discover_available_indices(self):
        indices = []
        # Check first 10 possible slots
        for i in range(10):
            suffix = f"_{i + 1}" if i > 0 else ""
            if config(f"SPOTIPY_CLIENT_ID{suffix}", default=None):
                indices.append(i)
        return indices

    def _get_client(self):
        if self._current_client_instance is None:
            self._current_client_instance = create_raw_spotify_client(self.current_index)
            if not self._current_client_instance:
                 # If current index fails to create (e.g. missing tokens), try next
                 self._rotate_client()
        return self._current_client_instance

    def _rotate_client(self):
        """Switch to the next available client index."""
        logger.warning(f"[ROTATION] Rotating client from index {self.current_index}...")
        
        # Find next index in the list that wraps around
        try:
            current_pos = self._available_indices.index(self.current_index)
            next_pos = (current_pos + 1) % len(self._available_indices)
            next_index = self._available_indices[next_pos]
            
            # If we wrapped around to the same index, we are out of options
            if next_index == self.current_index:
                logger.error("[ROTATION] Only one client available, cannot rotate!")
                # We don't raise here, we just keep using it (and presumably fail again)
                # But typically we want to return False to indicate rotation failed/useless
                return False
                
            self.current_index = next_index
            self._current_client_instance = create_raw_spotify_client(self.current_index)
            return True
        except ValueError:
            # Current index not in available? Should not happen. reset to 0
            if self._available_indices:
                self.current_index = self._available_indices[0]
                self._current_client_instance = create_raw_spotify_client(self.current_index)
                return True
            return False

    def __getattr__(self, name):
        """Proxy method calls to the underlying Spotify client with retry logic."""
        
        def wrapper(*args, **kwargs):
            return self._call_with_retry(name, *args, **kwargs)
            
        return wrapper

    def _call_with_retry(self, method_name, *args, **kwargs):
        """Execute method with automatic rotation on 429."""
        attempts = 0
        max_attempts = len(self._available_indices) * 2 # Allow one full rotation + safety
        
        while attempts < max_attempts:
            client = self._get_client()
            if not client:
                 raise Exception("No available Spotify clients configured.")

            method = getattr(client, method_name)
            
            try:
                return method(*args, **kwargs)
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 429:
                    logger.warning(f"[ROTATION] 429 Rate Limit detected during {method_name}. Attempting rotation...")
                    rotated = self._rotate_client()
                    if rotated:
                        attempts += 1
                        time.sleep(1) # Brief pause before retry
                        continue
                    else:
                        # No options left
                        logger.error("[ROTATION] 429 detected but no other clients available to rotate to.")
                        raise e
                else:
                    # Other spotify errors bubble up normally
                    raise e
            except Exception as e:
                # Other generic errors
                raise e
        
        raise Exception("Max retry attempts exceeded in RotatingSpotifyClient")


def get_spotify_client():
    """
    Get authenticated Spotify client (Rotating).
    This is the main entry point for all Spotify API operations.
    """
    return RotatingSpotifyClient()


# Legacy functions for backwards compatibility during migration
def oauth_factory(user_id=None):
    """Legacy wrapper - now ignores user_id and returns central OAuth for default client."""
    return get_spotify_oauth(0)


def spotify_client(oauth=None):
    """Legacy wrapper - returns central Spotify client."""
    return get_spotify_client()
