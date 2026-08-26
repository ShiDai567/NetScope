"""prune_history：历史数据清理（doc §18.3，cron 每日调用）。"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.log import get_logger

log = get_logger("network.commands.prune")


class Command(BaseCommand):
    help = "清理过期历史数据（TrafficSnapshot / FlowRecord / SystemEvent / GeoLookup）"

    def handle(self, *args, **options) -> None:
        now = timezone.now()
        results = {}

        from analytics.models import TrafficSnapshot

        snapshot_days = getattr(settings, "SNAPSHOT_RETENTION_DAYS", 30)
        deleted, _ = TrafficSnapshot.objects.filter(ts__lt=now - timedelta(days=snapshot_days)).delete()
        results["traffic_snapshot"] = deleted

        from network.models import FlowRecord, GeoLookup, SystemEvent

        flow_days = getattr(settings, "FLOW_RECORD_RETENTION_DAYS", 7)
        deleted, _ = FlowRecord.objects.filter(last_seen__lt=now - timedelta(days=flow_days)).delete()
        results["flow_record"] = deleted

        deleted, _ = SystemEvent.objects.filter(ts__lt=now - timedelta(days=30)).delete()
        results["system_event"] = deleted

        deleted, _ = GeoLookup.objects.filter(updated_at__lt=now - timedelta(days=90)).delete()
        results["geo_lookup"] = deleted

        for name, count in results.items():
            self.stdout.write(f"{name}: 删除 {count} 条")
        log.info("prune.done", **results)
