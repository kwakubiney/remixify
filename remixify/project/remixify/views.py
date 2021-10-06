from spotipy import Spotify
from django.shortcuts import redirect , render
from django.http import HttpResponse
from django.urls import reverse
from django.http import JsonResponse
from .auth import oauth
from .parsers import get_playlist,create_remix,create_playlist,create_remix_playlist

# Create your views here.

def home(request):
    track_list = get_playlist(oauth, "https://open.spotify.com/playlist/4QzQ2ygXC5gj8iLvPUT097?si=927fa0cf1337484a")
    remix = create_remix(track_list, oauth)
    playlist = create_playlist(oauth,track_list)
    final = create_remix_playlist(playlist, remix , oauth)
    return JsonResponse(final, safe=False)
    
def callback(request):
    if request.GET.get("code"):
        oauth.get_access_token(code=request.GET.get("code"))
    return redirect(reverse("home"))

    

