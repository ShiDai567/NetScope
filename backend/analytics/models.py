"""TrafficSnapshot：分钟级历史 rollup（doc §9.3.1）。"""

from django.db import models


class TrafficSnapshot(models.Model):
    ts = models.DateTimeField(db_index=True)
    bucket_s = models.IntegerField(default=60)
    up_bytes = models.BigIntegerField(default=0)
    down_bytes = models.BigIntegerField(default=0)
    up_bps = models.FloatField(default=0.0)
    down_bps = models.FloatField(default=0.0)
    pkts_total = models.IntegerField(default=0)
    pkts_outbound = models.IntegerField(default=0)
    pkts_inbound = models.IntegerField(default=0)
    pkts_internal = models.IntegerField(default=0)
    conn_active_max = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_trafficsnapshot"
        constraints = [models.UniqueConstraint(fields=["ts", "bucket_s"], name="uq_snapshot_ts_bucket")]
        verbose_name = "流量快照"
        verbose_name_plural = "流量快照"

    def __str__(self) -> str:
        return f"{self.ts:%Y-%m-%d %H:%M} up={self.up_bytes} down={self.down_bytes}"
