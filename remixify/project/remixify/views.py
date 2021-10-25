from spotipy import Spotify
from django.shortcuts import redirect , render
from django.http import HttpResponse
from django.urls import reverse
from django.http import JsonResponse
from .tasks import get_playlist, create_remix
from .auth import oauth

def home(request):
    url = oauth.get_authorize_url()
    return render(request, "home.html" , {"url":url})
    
def callback(request):
    if request.GET.get("code"):
        oauth.get_access_token(code=request.GET.get("code"))
    return redirect(reverse("index"))


def index(request):
    return render(request, "index.html")

    
def main(request):
    if request.method == 'POST':
        url = request.POST.get("url")
    playlists = get_playlist(url)
    task = create_remix.delay(playlists)
    context = {'task_id': task.task_id}
    return render(request, "results.html", context)
    


    

