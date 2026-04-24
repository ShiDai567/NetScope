import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import IKuaiSession
from .services import login_to_ikuai, serialize_session_summary


@csrf_exempt
@require_POST
def ikuai_login_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    response_payload, status_code = login_to_ikuai(payload)
    return JsonResponse(response_payload, status=status_code)


@require_GET
def ikuai_sessions_view(request):
    try:
        limit = int(request.GET.get("limit", "20") or 20)
    except ValueError:
        return JsonResponse({"error": "limit must be an integer"}, status=400)
    if limit < 1 or limit > 100:
        return JsonResponse({"error": "limit must be between 1 and 100"}, status=400)

    sessions = IKuaiSession.objects.all()[:limit]
    return JsonResponse([serialize_session_summary(session) for session in sessions], safe=False)
