"""REST 视图（doc §10）。薄壳：只做读取与响应组装，业务在 services。

v1 五接口与前端 client.ts 契约逐字节兼容（§10.2），字段不可变更。
"""

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services import empty_snapshot, read_ranking
from core.api_errors import ApiThrottle, PacketsThrottle
from core.log import get_logger
from core.redis_store import get_store
from core.utils.timeutil import now_ts
from network.serializers import (
    DeviceSchema,
    ModeResponseSchema,
    NodeSchema,
    PacketsResponseSchema,
    StatsSchema,
)

log = get_logger("network.api")

VALID_WINDOWS = frozenset(getattr(settings, "STATS_WINDOWS", (5, 30, 60, 300, 900, 3600)))
DEFAULT_WINDOW = 300


def _window_param(request) -> int:
    raw = request.query_params.get("window")
    if raw is None or not str(raw).strip().isdigit():
        return DEFAULT_WINDOW
    window = int(raw)
    return window if window in VALID_WINDOWS else DEFAULT_WINDOW


class ModeView(APIView):
    """运行模式与网关状态（§10.2.1）。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(responses=ModeResponseSchema)
    def get(self, request):
        store = get_store()
        mode_info = store.get_mode()
        gateway = store.get_gateway()
        ikuai = store.get_ikuai_health()
        return Response(
            {
                "mode": mode_info.get("mode", "unknown"),
                "uptime": max(0, int(now_ts() - mode_info.get("started_at", now_ts()))),
                "geo_epoch": mode_info.get("geo_epoch", 0),
                "gateway": {"lat": gateway["lat"], "lng": gateway["lng"]},
                "ikuai": {
                    "router_url": ikuai.get("router_url"),
                    "error": ikuai.get("error"),
                    "last_poll_at": ikuai.get("last_poll_at"),
                    "connected_at": ikuai.get("connected_at"),
                },
            }
        )


class PacketsView(APIView):
    """增量事件拉取（§10.2.2）：GET /api/packets?since={seq}&limit=500。"""

    throttle_classes = [PacketsThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("since", int, description="客户端已消费的最大 seq"),
            OpenApiParameter("limit", int, description="返回条数上限，默认 500"),
        ],
        responses=PacketsResponseSchema,
    )
    def get(self, request):
        store = get_store()
        since_raw = request.query_params.get("since")
        try:
            since = int(since_raw) if since_raw is not None else None
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "bad_request", "message": "since 必须是整数"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit_raw = request.query_params.get("limit")
        try:
            limit = min(1000, max(1, int(limit_raw))) if limit_raw else 500
        except (TypeError, ValueError):
            limit = 500
        events, last_seq = store.read_packets(since, limit)
        return Response({"server_time": now_ts(), "last_seq": last_seq, "events": events})


class StatsView(APIView):
    """全局统计快照（§10.2.3）：GET /api/stats?window=300。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(
        parameters=[OpenApiParameter("window", int, description="统计窗口（秒）")],
        responses=StatsSchema,
    )
    def get(self, request):
        store = get_store()
        window = _window_param(request)
        snapshot = store.get_stats(window)
        if snapshot is None:
            snapshot = empty_snapshot(window)
            mode_info = store.get_mode()
            snapshot["mode"] = mode_info.get("mode", "unknown")
            snapshot["uptime"] = max(0, int(now_ts() - mode_info.get("started_at", now_ts())))
            snapshot["active"] = store.count_conns()
        return Response(snapshot)


class DevicesView(APIView):
    """内网设备表（§10.2.4）。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(responses=DeviceSchema(many=True))
    def get(self, request):
        from core.utils.network import ip_to_int

        devices = get_store().get_devices()
        devices.sort(key=lambda d: ip_to_int(d.get("ip")))
        return Response({"devices": devices})


class NodesView(APIView):
    """公网热点节点（§10.2.5）。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(responses=NodeSchema(many=True))
    def get(self, request):
        nodes = get_store().get_nodes()
        nodes.sort(key=lambda n: n.get("ip") or "")
        return Response({"nodes": nodes})


class HealthView(APIView):
    """健康检查（§10.2.6）。

    degraded 只由实时链路决定（redis + collector 心跳）；
    db 不可用只上报状态（历史曲线停更，实时不受影响，doc §15.1）。
    """

    throttle_classes = []

    def get(self, request):
        store = get_store()
        redis_ok = store.ping()
        db_ok = True
        try:
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            db_ok = False

        age = store.collector_age()
        degraded = (not redis_ok) or (age is None or age > 30)
        body = {
            "status": "ok" if not degraded else "degraded",
            "redis": redis_ok,
            "db": db_ok,
            "collector_age_s": age,
        }
        return Response(body, status=200 if not degraded else 503)


# ---------------------------------------------------------------- v2 扩展（§10.3）


class RankingView(APIView):
    """维度排名：countries / protocols / applications / ports / ips。"""

    throttle_classes = [ApiThrottle]
    dim = "protocols"

    @extend_schema(
        parameters=[
            OpenApiParameter("window", int),
            OpenApiParameter("limit", int),
            OpenApiParameter("role", str, description="ips 维度：source|dest"),
        ]
    )
    def get(self, request):
        store = get_store()
        window = _window_param(request)
        limit_raw = request.query_params.get("limit")
        try:
            limit = min(100, max(1, int(limit_raw))) if limit_raw else 20
        except (TypeError, ValueError):
            limit = 20
        dim = self.dim
        if dim == "ips":
            role = request.query_params.get("role", "source")
            dim = "ips_src" if role != "dest" else "ips_dst"
        items = read_ranking(store, dim, window, now_ts(), limit)
        return Response({"window": window, "items": items, "total": len(items)})


class ConnectionsView(APIView):
    """活跃连接表（§10.3）。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("limit", int),
            OpenApiParameter("direction", str),
        ]
    )
    def get(self, request):
        store = get_store()
        limit_raw = request.query_params.get("limit")
        try:
            limit = min(500, max(1, int(limit_raw))) if limit_raw else 200
        except (TypeError, ValueError):
            limit = 200
        direction = request.query_params.get("direction")
        items = []
        for data in store.list_conns(limit * (2 if direction else 1)):
            if direction and data.get("direction") != direction:
                continue
            items.append(_conn_view(data))
            if len(items) >= limit:
                break
        return Response({"count": len(items), "items": items})


def _conn_view(data: dict) -> dict:
    return {
        "key": data.get("flow_key", ""),
        "direction": data.get("direction"),
        "application": data.get("application"),
        "protocol": data.get("protocol"),
        "status": data.get("status") or None,
        "interface": data.get("interface") or None,
        "source": {"ip": data.get("src_ip"), "port": int(data.get("src_port") or 0)},
        "destination": {"ip": data.get("dst_ip"), "port": int(data.get("dst_port") or 0)},
        "domain": data.get("domain") or None,
        "bytes": {
            "up": int(data.get("bytes_up") or 0),
            "down": int(data.get("bytes_down") or 0),
        },
        "rates": {
            "up_bps": float(data.get("up_bps") or 0),
            "down_bps": float(data.get("down_bps") or 0),
        },
        "first_seen": float(data.get("first_seen") or 0),
        "last_seen": float(data.get("last_seen") or 0),
    }


class EventsView(APIView):
    """系统事件历史（§10.3）。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("limit", int),
            OpenApiParameter("level", str, description="info|warn|error"),
        ]
    )
    def get(self, request):
        from network.models import SystemEvent

        limit_raw = request.query_params.get("limit")
        try:
            limit = min(200, max(1, int(limit_raw))) if limit_raw else 50
        except (TypeError, ValueError):
            limit = 50
        level = request.query_params.get("level")
        qs = SystemEvent.objects.all().order_by("-ts")
        if level in ("info", "warn", "error"):
            qs = qs.filter(level=level)
        items = [
            {
                "ts": event.ts.timestamp(),
                "level": event.level,
                "code": event.code,
                "message": event.message,
                "context": event.context,
            }
            for event in qs[:limit]
        ]
        return Response({"items": items, "total": len(items)})


class HistoryView(APIView):
    """历史 rollup 曲线（§10.3）：GET /api/network/history/?metric=bps&minutes=60。"""

    throttle_classes = [ApiThrottle]

    @extend_schema(
        parameters=[
            OpenApiParameter("minutes", int, description="最近 N 分钟，默认 60"),
            OpenApiParameter("bucket", int, description="采样粒度（秒），默认 60"),
        ]
    )
    def get(self, request):
        from django.utils import timezone as dj_tz

        from analytics.models import TrafficSnapshot

        minutes_raw = request.query_params.get("minutes")
        try:
            minutes = min(1440, max(5, int(minutes_raw))) if minutes_raw else 60
        except (TypeError, ValueError):
            minutes = 60
        since = dj_tz.datetime.fromtimestamp(now_ts() - minutes * 60, tz=dj_tz.utc)
        snapshots = TrafficSnapshot.objects.filter(ts__gte=since, bucket_s=60).order_by("-ts")[: 60 * 24]
        items = [
            {
                "t": snap.ts.timestamp(),
                "up_bps": snap.up_bps,
                "down_bps": snap.down_bps,
                "up_bytes": snap.up_bytes,
                "down_bytes": snap.down_bytes,
            }
            for snap in reversed(snapshots)
        ]
        return Response({"items": items, "total": len(items)})
