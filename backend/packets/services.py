"""
packets/services.py
===================
数据包模块业务逻辑层。

封装数据包生成和序列化的核心逻辑，供视图层调用。
生成逻辑基于 topology 模块中的 NetworkRoute，确保数据包只在实际存在的路由上传输。
"""

import random

from django.db import transaction
from django.utils import timezone

from topology.models import NetworkRoute
from .models import PacketEvent


# 状态权重列表：SUCCESS 出现 3 次，DELAYED 和 DROPPED 各 1 次，
# 因此成功概率为 60%，延迟和丢包各 20%。
STATUSES = [
    PacketEvent.Status.SUCCESS,
    PacketEvent.Status.SUCCESS,
    PacketEvent.Status.SUCCESS,
    PacketEvent.Status.DELAYED,
    PacketEvent.Status.DROPPED,
]

# 协议均匀分布：TCP、UDP、ICMP 各占 1/3。
PROTOCOLS = [
    PacketEvent.Protocol.TCP,
    PacketEvent.Protocol.UDP,
    PacketEvent.Protocol.ICMP,
]


def serialize_packet_event(packet):
    """
    将 PacketEvent 实例序列化为前端所需的字典格式。

    参数
    ----
    packet : PacketEvent
        待序列化的数据包事件实例。

    返回
    ----
    dict
        包含完整源/目标节点信息、协议、状态、负载大小和时间戳的字典。
        其中 lat/lng 转为 float，timestamp 转为 Unix 秒级整数。
    """
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
    """
    随机生成指定数量的数据包事件并写入数据库。

    参数
    ----
    count : int
        要生成的数据包数量（调用方已做范围校验）。

    返回
    ----
    list[PacketEvent]
        生成的 PacketEvent 实例列表。

    实现细节
    --------
    1. 从 topology 模块获取所有活跃路由（含预加载的节点信息）。
    2. 若路由为空，直接返回空列表（避免前端无数据可展示时崩溃）。
    3. 使用 @transaction.atomic 保证批量写入的原子性：
       要么全部成功，要么全部回滚，避免脏数据。
    4. 每条数据包随机选择路由、协议、状态和负载大小。
    5. 所有数据包共享同一 event_timestamp（当前时间），便于批量查询。
    """
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
