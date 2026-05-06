from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import NetworkNode, NetworkRoute


def serialize_node(node):
    return {
        "id": node.node_id,
        "name": node.name,
        "ip": node.ip_address,
        "type": node.node_type,
        "lat": float(node.latitude),
        "lng": float(node.longitude),
        "isActive": node.is_active,
    }


def serialize_route(route):
    return {
        "id": route.id,
        "sourceNodeId": route.source_node.node_id,
        "destinationNodeId": route.destination_node.node_id,
        "isActive": route.is_active,
    }


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
