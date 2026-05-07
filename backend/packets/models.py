"""
packets/models.py
=================
数据包事件模型。

定义 PacketEvent 表，用于存储模拟的网络数据包传输事件。
每个事件记录一次从源节点到目标节点的数据包传输，包含协议、状态、
负载大小和时间戳等信息。

外键依赖
--------
source_node / destination_node → topology.NetworkNode
    数据包的源节点和目标节点，通过外键关联到拓扑模块的节点表。
"""

import uuid

from django.db import models
from django.utils import timezone

from topology.models import NetworkNode


class PacketEvent(models.Model):
    """
    网络数据包事件模型。

    字段说明
    --------
    packet_id : str
        业务层唯一标识。若为空，save() 方法会自动生成形如 pkt_a3f7b2c8d1e4 的 UUID 短码。
    source_node : NetworkNode
        数据包发送方（外键，related_name='source_packets'）。
    destination_node : NetworkNode
        数据包接收方（外键，related_name='destination_packets'）。
    protocol : str
        传输层协议：TCP、UDP 或 ICMP。
    status : str
        传输结果：success（成功）、delayed（延迟）、dropped（丢包）。
    payload_size : int
        数据包负载大小，单位字节。随机范围 64 ~ 1563。
    event_timestamp : datetime
        事件发生时间，默认当前时间，带数据库索引以支持时间范围查询。
    created_at : datetime
        记录创建时间，自动维护。

    索引设计
    --------
    - (event_timestamp, status) ：便于按时间段统计各状态包数量。
    - (source_node, destination_node, event_timestamp) ：便于查询特定节点对之间的历史传输记录。
    """

    class Protocol(models.TextChoices):
        """支持的传输层协议枚举。"""
        TCP = "TCP", "TCP"
        UDP = "UDP", "UDP"
        ICMP = "ICMP", "ICMP"

    class Status(models.TextChoices):
        """数据包传输状态枚举。"""
        SUCCESS = "success", "Success"
        DELAYED = "delayed", "Delayed"
        DROPPED = "dropped", "Dropped"

    packet_id = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    source_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="source_packets",
    )
    destination_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="destination_packets",
    )
    protocol = models.CharField(max_length=16, choices=Protocol.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    payload_size = models.PositiveIntegerField()
    event_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 按时间倒序排列，最新事件排在最前。
        ordering = ["-event_timestamp", "-id"]
        indexes = [
            # 复合索引：支持按时间+状态聚合查询。
            models.Index(fields=["event_timestamp", "status"]),
            # 复合索引：支持节点对的历史记录查询。
            models.Index(fields=["source_node", "destination_node", "event_timestamp"]),
        ]

    def save(self, *args, **kwargs):
        """
        重写 save 方法，在首次保存时自动生成 packet_id。

        使用 uuid.uuid4().hex[:12] 生成 12 位十六进制随机字符串，
        前缀 pkt_ 便于肉眼识别，总长度可控，且冲突概率极低。
        """
        if not self.packet_id:
            self.packet_id = f"pkt_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.packet_id} ({self.protocol})"
