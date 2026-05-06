import random

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .services import generate_packets, serialize_packet_event


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
