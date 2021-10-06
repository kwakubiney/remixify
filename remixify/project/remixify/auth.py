from spotipy import Spotify,SpotifyOAuth
from decouple import config
from spotipy import CacheFileHandler, CacheHandler
import os
import uuid 

client_secret = config('CLIENT_SECRET')
client_id = config("CLIENT_ID")
redirect_uri = config("REDIRECT_URI")

oauth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://127.0.0.1:8000/callback/",
        scope='user-library-read playlist-modify-private playlist-modify-public',
        cache_handler = CacheFileHandler())


    

