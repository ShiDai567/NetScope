"""
topology/models.py
==================
网络拓扑数据模型。

定义了网络可视化系统的核心实体：
- NetworkNode（网络节点）：表示服务器或客户端设备，包含地理位置信息。
- NetworkRoute（网络路由）：表示两个节点之间的有向连接关系。

设计思路
--------
节点与路由分离，路由通过外键关联节点，支持有向图建模。
节点类型分为 SERVER 和 CLIENT，用于在业务层限制非法路由（如 client -> client）。
"""

from django.db import models


class NetworkNode(models.Model):
    """
    网络节点模型。

    每个节点代表网络中的一个设备（服务器或客户端），
    包含标识、名称、IP 地址、类型以及地理坐标。

    字段说明
    --------
    node_id : str
        业务层唯一标识（如 'srv_us'、'cli_cn'），非自增主键。
    name : str
        人类可读的节点名称，用于前端展示。
    ip_address : str
        IPv4 或 IPv6 地址，GenericIPAddressField 会自动校验格式。
    node_type : str
        节点类型：server（服务器）或 client（客户端）。
    latitude / longitude : Decimal
        WGS-84 坐标系下的经纬度，精度 6 位小数，约 0.1 米级精度。
    is_active : bool
        软删除标记。设为 False 时，该节点及其关联路由不会出现在 API 响应中。
    created_at / updated_at : datetime
        自动维护的时间戳字段。
    """

    class NodeType(models.TextChoices):
        """节点类型枚举。"""
        SERVER = "server", "Server"
        CLIENT = "client", "Client"

    node_id = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(db_index=True)
    node_type = models.CharField(max_length=16, choices=NodeType.choices, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 默认按 node_id 字母顺序排列，便于前端稳定展示。
        ordering = ["node_id"]

    def __str__(self) -> str:
        return f"{self.node_id} ({self.ip_address})"


class NetworkRoute(models.Model):
    """
    网络路由（有向边）模型。

    表示从 source_node 到 destination_node 的一条有向连接。
    通过 related_name 可在节点实例上反向查询：
    - node.outgoing_roles.all()  → 该节点出发的所有路由
    - node.incoming_routes.all() → 到达该节点的所有路由

    字段说明
    --------
    source_node : NetworkNode
        路由起点（外键）。
    destination_node : NetworkNode
        路由终点（外键）。
    is_active : bool
        软删除标记。

    约束说明
    --------
    unique_network_route
        同一对节点之间只能存在一条有向路由（避免重复边）。
    route_source_not_equal_destination
        禁止自环路由（source_node != destination_node）。
    """

    source_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="outgoing_routes",
    )
    destination_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="incoming_routes",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_node__node_id", "destination_node__node_id"]
        constraints = [
            # 同一对节点之间只能有一条有向路由。
            models.UniqueConstraint(
                fields=["source_node", "destination_node"],
                name="unique_network_route",
            ),
            # 禁止自环：起点不能等于终点。
            models.CheckConstraint(
                condition=~models.Q(source_node=models.F("destination_node")),
                name="route_source_not_equal_destination",
            ),
        ]

    def clean(self):
        """
        模型级业务校验。

        禁止 client -> client 的路由，只允许：
        - server -> client
        - client -> server
        - server -> server
        """
        super().clean()
        source_type = self.source_node.node_type
        destination_type = self.destination_node.node_type
        if source_type == NetworkNode.NodeType.CLIENT and destination_type == NetworkNode.NodeType.CLIENT:
            from django.core.exceptions import ValidationError

            raise ValidationError("client -> client routes are not allowed")

    def __str__(self) -> str:
        return f"{self.source_node.node_id} -> {self.destination_node.node_id}"
