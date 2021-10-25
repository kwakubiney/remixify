from spotipy import Spotify
from spotipy import SpotifyException , SpotifyOauthError
import re



def create_playlist(auth, remix):
    details = {}
    sp = Spotify(auth_manager=auth)
    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(user_id,name= remix["playlist_name"], description="Remixes of some songs on original :)")
    details["user_id"] = user_id
    details["playlist_id"] = playlist["id"]
    return details

def create_remix_playlist(details, remix, auth):
    sp = Spotify(auth_manager=auth)
    track_id = [x for x in remix]
    user_id = details["user_id"]
    playlist_id = details["playlist_id"]

    final = sp.user_playlist_add_tracks(user_id, playlist_id, track_id)
    return final
    





        

        

        



    
