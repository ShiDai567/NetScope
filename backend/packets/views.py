"""
packets/views.py
================
数据包模块视图。

提供数据包生成接口，根据请求参数随机生成若干条模拟数据包事件并持久化，
然后将生成的事件序列化后返回给前端。
"""

import random

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .services import generate_packets, serialize_packet_event


@require_GET
def packet_view(request):
    """
    生成并返回模拟数据包事件 (GET /api/packet)。

    查询参数
    --------
    count : int, optional
        要生成的数据包数量。
        - 若未提供，随机生成 1~3 条。
        - 若提供但 <= 0，默认生成 1 条。
        - 最大值限制为 10，防止滥用。

    返回格式 (JSON)
    ---------------
    [
        {
            "id": "pkt_a3f7b2c8d1e4",
            "source": {
                "ip": "192.168.1.10",
                "name": "Client (Beijing)",
                "lat": 39.9,
                "lng": 116.4,
                "type": "client"
            },
            "destination": { ... },
            "protocol": "TCP",
            "status": "success",
            "payloadSize": 1024,
            "timestamp": 1715000000
        },
        ...
    ]

    错误响应
    --------
    400 Bad Request
        - count 不是有效整数
        - count 超过 10
    """
    # 解析 count 参数，处理空字符串、非数字等异常情况。
    try:
        count = int(request.GET.get("count", "0") or 0)
    except ValueError:
        return JsonResponse({"error": "count must be an integer"}, status=400)

    # 若未提供 count 参数，随机生成 1~3 条。
    if count <= 0:
        count = 1 if request.GET.get("count") else None
    if count is None:
        count = random.randint(1, 3)

    # 限制单次请求最大生成数量，防止数据库压力过大。
    if count > 10:
        return JsonResponse({"error": "count must be between 1 and 10"}, status=400)

    # 调用服务层生成数据包并持久化。
    packets = generate_packets(count)

    # 序列化后返回 JSON 数组。
    return JsonResponse([serialize_packet_event(packet) for packet in packets], safe=False)
