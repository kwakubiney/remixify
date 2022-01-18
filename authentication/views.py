from django.shortcuts import HttpResponse
from django.shortcuts import render

# Create your views here.

def home(request):
    if request.user.is_authenticated:
        return HttpResponse("You are logged in")
    else:
        return HttpResponse("You are not logged in")