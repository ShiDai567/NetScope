import time

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

START_TIME = time.monotonic()


@require_GET
def health_view(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse(
        {
            "status": "ok",
            "service": "netscope-backend",
            "uptime": round(time.monotonic() - START_TIME, 3),
            "database": "ok",
            "time": timezone.now().isoformat().replace("+00:00", "Z"),
        }
    )
