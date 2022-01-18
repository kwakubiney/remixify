from celery import shared_task
import re
from authentication.oauth import oauth
from spotipy import Spotify

def get_playlist(url):
    url_pattern = re.compile(r"https:\/\/open.spotify.com/(user\/.+\/)?playlist/(?P<playlist_id>.+)")
    pattern = re.compile("(\(.*\))")
    if url_pattern.match(url):
        playlist_id = url_pattern.match(url).group("playlist_id")
    else:
        raise ValueError("Expecting a Spotify playlist URL. Try again.")
    track_details ={}
    tracks = []
    items = []
    data = Spotify(auth_manager = oauth).playlist(playlist_id)
    track_details["playlist_name"] = data["name"]
    items += data["tracks"]["items"]
    next = data["tracks"]["next"]
    results = data["tracks"]

    while next is not None:
        results = Spotify(auth_manager = oauth).next(results)
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

def chunker(array):
    [array[i:i+100] for i in range(len(array))[::100]]
    
@shared_task(bind=True)
def create_remix(self, url):
    tracks = get_playlist(url)
    sp = Spotify(auth_manager = oauth)
    track_id = []
    details = {}
    for key in tracks:
        try:
            data = sp.search(f"{key} remix", type="track", limit=1)
            if (f"{key}".lower() in data["tracks"]["items"][0]["name"].lower()) and data["tracks"]["items"][0]["name"].lower().startswith(f"{key}".lower()):
                track_id.append(data['tracks']['items'][0]['id'])
            else:
                continue
        except IndexError:
            continue
    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(user_id, name = tracks["playlist_name"], description="Remixed by Remixify!")
    details["user_id"] = user_id
    details["playlist_id"] = playlist["id"]
    user_id = details["user_id"]
    playlist_id = details["playlist_id"]
    if len(track_id) > 100:
        new_track_id = chunker(track_id)
        for x in new_track_id:
            sp.user_playlist_add_tracks(user_id, playlist_id, x)
    else:
        sp.user_playlist_add_tracks(user_id, playlist_id, track_id)
        playlist_details = sp.user_playlist(user_id, playlist_id)
    return playlist_details["external_urls"]["spotify"]
    
