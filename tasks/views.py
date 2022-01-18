from django.shortcuts import HttpResponse
from tasks.tasks import create_remix

def result(request):
    if request.method == 'POST':
        url = request.POST.get("url")
        create_remix.delay(url)
    return HttpResponse("Working in the background")