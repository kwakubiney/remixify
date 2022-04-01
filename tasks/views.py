from django.shortcuts import HttpResponse
from django.http import JsonResponse
from tasks.tasks import create_remix
from django.shortcuts import render

def result(request):
    if request.method == 'POST':
        url = request.POST.get("url")
        result = create_remix.delay(url)
        context={'task_id': result.task_id}  
    return JsonResponse(context, safe=False)