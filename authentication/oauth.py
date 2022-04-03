from spotipy.cache_handler import  CacheHandler
from allauth.socialaccount.models import SocialToken
from spotipy.oauth2 import SpotifyOAuth
from authentication.timestamp import unix, deunix
from spotipy import SpotifyOAuth
from decouple import config
from spotipy import Spotify
from django.contrib.auth.models import User

class RemixifyCacheHandler(CacheHandler):

    def __init__(self, spotify_object):
        self.spotify_object = spotify_object

    def get_cached_token(self):
        
        token_info = {}

        token_info["access_token"] = self.spotify_object.token
        token_info["refresh_token"] = self.spotify_object.token_secret
        token_info["expires_at"] = unix(self.spotify_object.expires_at)
        token_info["scope"] = 'user-library-read playlist-modify-private playlist-modify-public playlist-read-collaborative playlist-read-private user-follow-modify'
        
        return token_info

    def save_token_to_cache(self, token_info):
        # save the token info back to the `SocialToken` object
        # notice that we're saving the token info back to the same place that we retrieved it from
        # in `get_cached_token`; this is crucial

        self.spotify_object.token = token_info["access_token"]
        self.spotify_object.token_secret = token_info["refresh_token"]
        self.spotify_object.expires_at = deunix(token_info["expires_at"])

      
def oauth_factory(user_id):
    return SpotifyOAuth(
        client_id=config("SPOTIPY_CLIENT_ID"),
        client_secret=config("SPOTIPY_CLIENT_SECRET"),
        redirect_uri= config("REDIRECT_URI"),
        cache_handler= RemixifyCacheHandler(SocialToken.objects.filter(account__user= User.objects.get(id=user_id), account__provider= "spotify").first()))
    

def spotify_client(oauth):
    return Spotify(auth_manager=oauth)
