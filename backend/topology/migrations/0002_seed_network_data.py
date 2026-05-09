"""
topology/migrations/0002_seed_network_data.py
=============================================
数据迁移文件：在数据库表创建后，自动写入默认的网络拓扑数据。

此迁移使用 Django 的 RunPython 操作，在 migrate 时执行 seed_network_data 函数，
在回滚（reverse migration）时执行 remove_network_data 清理数据。

数据内容
--------
包含 1 个服务器节点（美国硅谷）和 3 个客户端节点（北京、伦敦、圣保罗），
并在它们之间建立全互联路由（server <-> client、server <-> server）。
"""

from django.db import migrations


# 默认节点数据列表。
# 这些节点在系统首次部署时自动创建，确保前端可视化页面有初始数据可展示。
DEFAULT_NODES = [
    {
        "node_id": "srv_us",
        "name": "Server (Zhejiang)",
        "ip_address": "8.8.8.8",
        "node_type": "server",
        "latitude": "27.994111",
        "longitude": "120.699341",
        "is_active": True,
    },
    {
        "node_id": "cli_cn",
        "name": "Client (Beijing)",
        "ip_address": "192.168.1.10",
        "node_type": "client",
        "latitude": "39.900000",
        "longitude": "116.400000",
        "is_active": True,
    },
    {
        "node_id": "cli_eu",
        "name": "Client (London)",
        "ip_address": "192.168.1.20",
        "node_type": "client",
        "latitude": "51.500000",
        "longitude": "-0.120000",
        "is_active": True,
    },
    {
        "node_id": "cli_br",
        "name": "Client (Sao Paulo)",
        "ip_address": "192.168.1.30",
        "node_type": "client",
        "latitude": "-23.550000",
        "longitude": "-46.630000",
        "is_active": True,
    },
]


def seed_network_data(apps, schema_editor):
    """
    正向迁移函数：创建默认节点和路由。

    参数
    ----
    apps : django.apps.registry.Apps
        迁移时的应用注册表，用于获取历史版本模型（避免直接使用当前代码中的模型类）。
    schema_editor : django.db.backends.base.schema.BaseDatabaseSchemaEditor
        数据库架构编辑器，此处未直接使用，但为 RunPython 签名所要求。
    """
    # 使用 apps.get_model 获取迁移时的历史模型，而不是直接 import，
    # 这样可以保证即使未来模型发生变化，此迁移仍然能正确执行。
    NetworkNode = apps.get_model("topology", "NetworkNode")
    NetworkRoute = apps.get_model("topology", "NetworkRoute")

    nodes = {}
    for payload in DEFAULT_NODES:
        # update_or_create 保证重复执行迁移时不会报错（幂等性）。
        node, _ = NetworkNode.objects.update_or_create(
            node_id=payload["node_id"],
            defaults=payload,
        )
        nodes[node.node_id] = node

    # 按类型分组，便于后续建立规则化的路由。
    servers = [node for node in nodes.values() if node.node_type == "server"]
    clients = [node for node in nodes.values() if node.node_type == "client"]

    # 建立 server <-> client 的双向路由。
    for server in servers:
        for client in clients:
            NetworkRoute.objects.get_or_create(source_node=server, destination_node=client)
            NetworkRoute.objects.get_or_create(source_node=client, destination_node=server)

    # 建立 server <-> server 的双向路由（全互联）。
    for index, server in enumerate(servers):
        for peer in servers[index + 1 :]:
            NetworkRoute.objects.get_or_create(source_node=server, destination_node=peer)
            NetworkRoute.objects.get_or_create(source_node=peer, destination_node=server)


def remove_network_data(apps, schema_editor):
    """
    反向迁移函数：删除由 seed_network_data 创建的数据。

    按依赖顺序先删路由再删节点，避免外键约束错误。
    """
    NetworkRoute = apps.get_model("topology", "NetworkRoute")
    NetworkNode = apps.get_model("topology", "NetworkNode")
    node_ids = [payload["node_id"] for payload in DEFAULT_NODES]
    # 删除与默认节点相关的所有路由（无论作为起点还是终点）。
    NetworkRoute.objects.filter(source_node__node_id__in=node_ids).delete()
    NetworkRoute.objects.filter(destination_node__node_id__in=node_ids).delete()
    NetworkNode.objects.filter(node_id__in=node_ids).delete()


class Migration(migrations.Migration):
    """
    数据迁移类。

    dependencies
    ------------
    依赖于 topology 的初始迁移（0001_initial），确保表已存在。

    operations
    ----------
    执行 RunPython 操作，调用 seed_network_data 写入默认数据。
    """
    dependencies = [
        ("topology", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_network_data, remove_network_data),
    ]
