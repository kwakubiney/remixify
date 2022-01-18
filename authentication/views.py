from django.shortcuts import render

def home(request):
    if request.user.is_authenticated:
        return render(request, "index.html")
    else:
        return render(request, "welcome.html")