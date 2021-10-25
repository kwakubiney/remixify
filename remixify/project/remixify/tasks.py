from celery import shared_task
from spotipy import Spotify
from spotipy import SpotifyException , SpotifyOauthError
import re
from .auth import spotify_client, oauth
from celery_progress.backend import ProgressRecorder

def get_playlist(url):
    url_pattern = re.compile(r"https:\/\/open.spotify.com/(user\/.+\/)?playlist/(?P<playlist_id>.+)")
    pattern = re.compile("(\(.*\))")
    if url_pattern.match(url):
        playlist_id = url_pattern.match(url).group("playlist_id")
    track_details ={}
    tracks = []
    items = []
    data = spotify_client(oauth).playlist(playlist_id)
    playlist_name = data["name"]
    track_details["playlist_name"] = playlist_name
    # sp.current_user()["id"]
    items += data["tracks"]["items"]
    next = data["tracks"]["next"]
    results = data["tracks"]
    artists = []

    while next is not None:
        results = spotify_client(oauth).next(results)
        items.extend(results["items"])
        next = results.get("next")

    for item in items:
        track = item["track"]
        if track is not None:
            name = track["name"]
            if pattern.search(name):
                name = re.sub(pattern,"",name)
            tracks.append(name)
        track_details[f"{name}"] = [artist["name"] for artist in track["artists"]]
      
    return track_details

@shared_task(bind=True)
def create_remix(self, tracks):
    progress_recorder = ProgressRecorder(self)
    remix = {}
    for index, key in enumerate(tracks):
        try:
            data = spotify_client(oauth).search(f"{key} Remix", type="track", limit=1)
            if 0 < len(data["tracks"]["items"]):
                element = data["tracks"]["items"][0]["artists"][0]["name"]
                if (f"{key}".lower() in data["tracks"]["items"][0]["name"].lower()) and data["tracks"]["items"][0]["name"].lower().startswith(f"{key}".lower()):
                        remix[f"{data['tracks']['items'][0]['id']}"] = data["tracks"]["items"][0]["name"]
            else:
                continue
        except IndexError:
            continue
    return remix
