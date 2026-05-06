import random

from django.db import transaction
from django.utils import timezone

from topology.models import NetworkRoute
from .models import PacketEvent


STATUSES = [
    PacketEvent.Status.SUCCESS,
    PacketEvent.Status.SUCCESS,
    PacketEvent.Status.SUCCESS,
    PacketEvent.Status.DELAYED,
    PacketEvent.Status.DROPPED,
]
PROTOCOLS = [
    PacketEvent.Protocol.TCP,
    PacketEvent.Protocol.UDP,
    PacketEvent.Protocol.ICMP,
]


def serialize_packet_event(packet):
    return {
        "id": packet.packet_id,
        "source": {
            "ip": packet.source_node.ip_address,
            "name": packet.source_node.name,
            "lat": float(packet.source_node.latitude),
            "lng": float(packet.source_node.longitude),
            "type": packet.source_node.node_type,
        },
        "destination": {
            "ip": packet.destination_node.ip_address,
            "name": packet.destination_node.name,
            "lat": float(packet.destination_node.latitude),
            "lng": float(packet.destination_node.longitude),
            "type": packet.destination_node.node_type,
        },
        "protocol": packet.protocol,
        "status": packet.status,
        "payloadSize": packet.payload_size,
        "timestamp": int(packet.event_timestamp.timestamp()),
    }


@transaction.atomic
def generate_packets(count):
    routes = list(
        NetworkRoute.objects.select_related("source_node", "destination_node")
        .filter(is_active=True, source_node__is_active=True, destination_node__is_active=True)
    )
    if not routes:
        return []

    packets = []
    now = timezone.now()
    for _ in range(count):
        route = random.choice(routes)
        packet = PacketEvent(
            source_node=route.source_node,
            destination_node=route.destination_node,
            protocol=random.choice(PROTOCOLS),
            status=random.choice(STATUSES),
            payload_size=random.randint(64, 1563),
            event_timestamp=now,
        )
        packet.save()
        packets.append(packet)
    return packets
