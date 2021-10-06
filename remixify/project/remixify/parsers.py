from spotipy import Spotify
from spotipy import SpotifyException , SpotifyOauthError
import re
from .auth import oauth


#Refactor!
def get_playlist(auth,url):
    
    #to strip playlist id from url
    url_pattern = re.compile(r"https:\/\/open.spotify.com\/playlist\/(?P<playlist_id>.+)")

    #to remove extra brackets which contain artiste names from track names
    pattern = re.compile("(\(.*\))")

    if url_pattern.match(url):
        playlist_id = url_pattern.match(url).group("playlist_id")
    else:
        raise ValueError(
            "Cross check the inputted URL"
        )
    track_details ={}
    tracks = []
    items = []
    sp = Spotify(auth_manager=auth)
    data = sp.playlist(playlist_id)
    # sp.current_user()["id"]
    playlist_name = data["name"]
    items += data["tracks"]["items"]
    next = data["tracks"]["next"]
    results = data["tracks"]
    artists = []

    while next is not None:
        results = sp.next(results)
        items.extend(results["items"])
        next = results.get("next")

    for item in items:
        track = item["track"]
        if track is not None:
            name = track["name"]
            if pattern.search(name):
                name = re.sub(pattern,"",name)
            tracks.append(name)
        #get artiste names in a list
        track_details[f"{name}"] = [artist["name"] for artist in track["artists"]]
        track_details["playlist_name"] = playlist_name
    return track_details
            


def create_remix(tracks, auth):
    items = []
    result = []
    remix = {}
    sp = Spotify(auth_manager=auth)

    #loop through original tracklist and find remixes of the tracks
    for key in tracks:
        data = sp.search(f"{key} remix", type="track", limit=1)
        if 0 < len(data["tracks"]["items"]):
            #nasty way to find out if both sides start with the same string; I didn't want to use Regex
            #quite inaccurate though, for now
            if (f"{key}".lower() in data["tracks"]["items"][0]["name"].lower()) and data["tracks"]["items"][0]["name"].lower().startswith(f"{key}".lower()):
                #create dictionary with track ID as keys and tracks as values
                remix[f"{data['tracks']['items'][0]['id']}"] = data["tracks"]["items"][0]["name"]
    
            else:
                continue
    return remix


def create_playlist(auth,track_details):
    details = {}
    sp = Spotify(auth_manager=auth)
    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(user_id,name=track_details["playlist_name"], description="Remixes of some songs on original :)")
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
    





        

        

        



    
