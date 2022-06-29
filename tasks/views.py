from django.http import JsonResponse
from tasks.tasks import create_remix
from django.contrib.auth.decorators import login_required


@login_required(login_url= "home")
def result(request):
    if request.method == 'POST':
        url = request.POST.get("url")
        user_id = request.user.id
        result = create_remix.delay(url, user_id)
        context={'task_id': result.task_id}  
    return JsonResponse(context, safe=False)