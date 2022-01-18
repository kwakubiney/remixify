from spotipy.cache_handler import  CacheHandler
from allauth.socialaccount.models import SocialToken
from spotipy.oauth2 import SpotifyOAuth
from authentication.timestamp import unix, deunix
from spotipy import SpotifyOAuth
from decouple import config


class SparisonCacheHandler(CacheHandler):

    def __init__(self, spotify_object):
        self.spotify_object = spotify_object

    def get_cached_token(self):
        
        token_info = {}

        token_info["access_token"] = self.spotify_object.token
        token_info["refresh_token"] = self.spotify_object.token_secret
        token_info["expires_at"] = unix(self.spotify_object.expires_at)
        token_info["scope"] = "user-library-read"

        return token_info

    def save_token_to_cache(self, token_info):
        # save the token info back to the `SocialToken` object
        # notice that we're saving the token info back to the same place that we retrieved it from
        # in `get_cached_token`; this is crucial

        self.spotify_object.token = token_info["access_token"]
        self.spotify_object.token_secret = token_info["refresh_token"]
        self.spotify_object.expires_at = deunix(token_info["expires_at"])
        self.spotify_object.scope = token_info["scope"]
        
        
oauth = SpotifyOAuth(
        client_id=config("SPOTIPY_CLIENT_ID"),
        client_secret=config("SPOTIPY_CLIENT_SECRET"),
        redirect_uri= config("REDIRECT_URI"),
        scope="user-library-read",
        cache_handler= SparisonCacheHandler(SocialToken.objects.filter(app__name="Spotify").first()))
    