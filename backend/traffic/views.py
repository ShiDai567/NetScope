import random
import time

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import NetworkNode, NetworkRoute
from .services import generate_packets, serialize_node, serialize_route, serialize_packet_event

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


@require_GET
def packet_view(request):
    try:
        count = int(request.GET.get("count", "0") or 0)
    except ValueError:
        return JsonResponse({"error": "count must be an integer"}, status=400)
    if count <= 0:
        count = 1 if request.GET.get("count") else None
    if count is None:
        count = random.randint(1, 3)
    if count > 10:
        return JsonResponse({"error": "count must be between 1 and 10"}, status=400)

    packets = generate_packets(count)
    return JsonResponse([serialize_packet_event(packet) for packet in packets], safe=False)


@require_GET
def nodes_view(request):
    nodes = NetworkNode.objects.filter(is_active=True)
    return JsonResponse([serialize_node(node) for node in nodes], safe=False)


@require_GET
def routes_view(request):
    routes = NetworkRoute.objects.select_related("source_node", "destination_node").filter(
        is_active=True,
        source_node__is_active=True,
        destination_node__is_active=True,
    )
    return JsonResponse([serialize_route(route) for route in routes], safe=False)
