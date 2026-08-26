"""数据模型（doc §9）。实时热数据在 Redis，这里只存冷数据。"""

from django.db import models


class GeoLookup(models.Model):
    """Geo 二级持久缓存（doc §9.3.3）。"""

    ip_prefix = models.CharField(max_length=64, unique=True, db_index=True)
    country = models.CharField(max_length=64, blank=True, default="")
    code = models.CharField(max_length=8, blank=True, default="")
    region = models.CharField(max_length=64, blank=True, default="")
    city = models.CharField(max_length=64, blank=True, default="")
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=16, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "network_geolookup"
        verbose_name = "Geo 缓存"
        verbose_name_plural = "Geo 缓存"

    def __str__(self) -> str:
        return f"{self.ip_prefix} → {self.country}/{self.city}"


class FlowRecord(models.Model):
    """连接审计（可选开启，连接关闭时落一条，doc §9.3.2）。"""

    flow_key = models.CharField(max_length=24, db_index=True)
    first_seen = models.DateTimeField(db_index=True)
    last_seen = models.DateTimeField(db_index=True)
    direction = models.CharField(max_length=8)
    protocol = models.CharField(max_length=16, blank=True, default="")
    application = models.CharField(max_length=64, blank=True, default="")
    src_ip = models.GenericIPAddressField(null=True, blank=True)
    src_port = models.IntegerField(default=0)
    dst_ip = models.GenericIPAddressField(null=True, blank=True)
    dst_port = models.IntegerField(default=0)
    domain = models.CharField(max_length=255, blank=True, default="")
    nat_forward_addr = models.CharField(max_length=64, blank=True, default="")
    bytes_up = models.BigIntegerField(default=0)
    bytes_down = models.BigIntegerField(default=0)
    pkts = models.IntegerField(default=1)
    src_country = models.CharField(max_length=64, blank=True, default="")
    src_city = models.CharField(max_length=64, blank=True, default="")
    dst_country = models.CharField(max_length=64, blank=True, default="")
    dst_city = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=32, blank=True, default="")
    interface = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        db_table = "network_flowrecord"
        indexes = [
            models.Index(fields=["direction", "last_seen"]),
            models.Index(fields=["src_ip", "last_seen"]),
        ]
        verbose_name = "连接审计"
        verbose_name_plural = "连接审计"

    def __str__(self) -> str:
        return f"{self.src_ip}:{self.src_port} → {self.dst_ip}:{self.dst_port} ({self.direction})"


class SystemEvent(models.Model):
    """系统事件/告警留痕（doc §9.3.4）。"""

    LEVELS = (("info", "info"), ("warn", "warn"), ("error", "error"))

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    level = models.CharField(max_length=8, choices=LEVELS, default="info")
    code = models.CharField(max_length=32, db_index=True)
    message = models.TextField(blank=True, default="")
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "core_systemevent"
        verbose_name = "系统事件"
        verbose_name_plural = "系统事件"

    def __str__(self) -> str:
        return f"[{self.level}] {self.code}"
