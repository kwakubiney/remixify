from django.shortcuts import HttpResponse
from django.http import JsonResponse
from authentication.oauth import oauth_factory
from tasks.tasks import create_remix


def result(request):
    if request.method == 'POST':
        url = request.POST.get("url")
        user_id = request.user.id
        result = create_remix.delay(url, user_id)
        context={'task_id': result.task_id}  
    return JsonResponse(context, safe=False)