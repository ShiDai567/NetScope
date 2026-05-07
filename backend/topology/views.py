"""
topology/views.py
=================
网络拓扑模块视图。

提供节点列表和路由列表两个只读接口，供前端可视化页面渲染网络拓扑图。
所有视图仅处理 GET 请求，返回 JSON 数组。
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import NetworkNode, NetworkRoute


def serialize_node(node):
    """
    将 NetworkNode 实例序列化为前端所需的字典格式。

    参数
    ----
    node : NetworkNode
        待序列化的节点实例。

    返回
    ----
    dict
        包含 id、name、ip、type、lat、lng、isActive 的字典。
        其中 lat/lng 转为 float，避免 Decimal 无法 JSON 序列化。
    """
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
    """
    将 NetworkRoute 实例序列化为前端所需的字典格式。

    参数
    ----
    route : NetworkRoute
        待序列化的路由实例。

    返回
    ----
    dict
        包含 id、sourceNodeId、destinationNodeId、isActive 的字典。
    """
    return {
        "id": route.id,
        "sourceNodeId": route.source_node.node_id,
        "destinationNodeId": route.destination_node.node_id,
        "isActive": route.is_active,
    }


@require_GET
def nodes_view(request):
    """
    获取所有活跃节点列表 (GET /api/nodes)。

    过滤条件
    --------
    仅返回 is_active=True 的节点。

    返回格式 (JSON)
    ---------------
    [
        {
            "id": "srv_us",
            "name": "Server (Silicon Valley)",
            "ip": "8.8.8.8",
            "type": "server",
            "lat": 27.994111,
            "lng": 120.699341,
            "isActive": true
        },
        ...
    ]
    """
    nodes = NetworkNode.objects.filter(is_active=True)
    return JsonResponse([serialize_node(node) for node in nodes], safe=False)


@require_GET
def routes_view(request):
    """
    获取所有活跃路由列表 (GET /api/routes)。

    过滤条件
    --------
    仅返回满足以下条件的路由：
    - 路由本身 is_active=True
    - 起点节点 is_active=True
    - 终点节点 is_active=True

    查询优化
    --------
    使用 select_related 预加载 source_node 和 destination_node，
    避免 N+1 查询问题。

    返回格式 (JSON)
    ---------------
    [
        {
            "id": 1,
            "sourceNodeId": "srv_us",
            "destinationNodeId": "cli_cn",
            "isActive": true
        },
        ...
    ]
    """
    routes = NetworkRoute.objects.select_related("source_node", "destination_node").filter(
        is_active=True,
        source_node__is_active=True,
        destination_node__is_active=True,
    )
    return JsonResponse([serialize_route(route) for route in routes], safe=False)
