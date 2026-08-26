"""NetworkStatisticsService：组装 /api/stats 契约快照（doc §10.2.3）。

collector 侧每秒构建各窗口快照写入 Redis；web 侧直接读取。
v2 排名接口由 read_ranking() 从 Redis 计数桶合并。
"""

from analytics.aggregators import (
    APPLICATIONS,
    COUNTRIES,
    DIRECTIONS,
    IPS_DST,
    IPS_SRC,
    PORTS,
    PROTOCOLS,
    RollingCounters,
)
from analytics.bandwidth import BandwidthTracker


def empty_snapshot(window: int) -> dict:
    """零值快照（collector 未启动/数据不足时的降级形态）。"""
    return {
        "total": 0,
        "active": 0,
        "closed": 0,
        "failed": 0,
        "lost": 0,
        "directions": {"outbound": 0, "inbound": 0, "internal": 0},
        "protocols": {},
        "apps": [],
        "bandwidth": {"up_bps": 0.0, "down_bps": 0.0, "series": []},
        "loss_rate": 0.0,
        "avg_latency_ms": 0.0,
        "system": {"cpu_percent": None, "memory_percent": None},
        "latency_heatmap": {"x": [], "y": [], "data": []},
        "mode": "unknown",
        "uptime": 0,
        "window": window,
    }


class NetworkStatisticsService:
    def __init__(
        self,
        counters: RollingCounters,
        bandwidth: BandwidthTracker,
        store,
        mode_provider,
        conn_counter,
    ) -> None:
        self._counters = counters
        self._bw = bandwidth
        self._store = store
        self._mode_provider = mode_provider
        self._conn_counter = conn_counter

    def build(self, window: int, now: float) -> dict:
        totals = self._store.get_totals()
        up_bps, down_bps = self._bw.latest()
        mode_info = self._mode_provider()
        sys_metrics = self._store.get_sys_metrics()

        directions = {k: 0 for k in ("outbound", "inbound", "internal")}
        for direction, count, _b in self._counters.window_top(DIRECTIONS, window, now, limit=10):
            if direction in directions:
                directions[direction] = count

        protocols = {
            proto: count for proto, count, _b in self._counters.window_top(PROTOCOLS, window, now, limit=30)
        }

        apps = [
            {"name": name, "count": count}
            for name, count, _b in self._counters.window_top(APPLICATIONS, window, now, limit=20)
        ]

        return {
            "total": totals.get("total", 0),
            "active": self._conn_counter(),
            "closed": totals.get("closed", 0),
            "failed": totals.get("failed", 0),
            "lost": totals.get("lost", 0),
            "directions": directions,
            "protocols": protocols,
            "apps": apps,
            "bandwidth": {
                "up_bps": round(up_bps, 2),
                "down_bps": round(down_bps, 2),
                "series": self._bw.series(window, now),
            },
            "loss_rate": 0.0,
            "avg_latency_ms": 0.0,
            "system": sys_metrics,
            "latency_heatmap": {"x": [], "y": [], "data": []},
            "mode": mode_info.get("mode", "unknown"),
            "uptime": max(0, int(now - mode_info.get("started_at", now))),
            "window": window,
        }


# ---------------------------------------------------------------- v2 读取（web 侧）


def read_ranking(store, dim: str, window: int, now: float, limit: int = 20) -> list[dict]:
    """从 Redis 计数桶合并窗口内排名（doc §10.3）。"""
    if hasattr(store.r, "hgetall"):
        merged = store.read_dim_window_hashes(dim, window, now)
    else:  # fakeredis 等不支持 pipeline hgetall 的情况
        merged = store.read_dim_window(dim, window, now)
    ranked = sorted(merged.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    items = []
    for field, (count, byte_count) in ranked:
        item: dict = {"key": field, "count": int(count), "bytes": int(byte_count)}
        if dim == COUNTRIES and "|" in field:
            code, _, name = field.partition("|")
            item["code"], item["country"] = (code or None), name
        elif dim == PORTS:
            try:
                item["port"] = int(field)
            except ValueError:
                continue
        items.append(item)
    return items


def read_window_totals(store, window: int, now: float) -> dict[str, int]:
    """窗口内方向计数（/api/network/overview 备用）。"""
    totals = {}
    for dim in (DIRECTIONS, PROTOCOLS, IPS_SRC, IPS_DST):
        merged = (
            store.read_dim_window_hashes(dim, window, now)
            if hasattr(store.r, "hgetall")
            else store.read_dim_window(dim, window, now)
        )
        totals[dim] = {field: int(values[0]) for field, values in merged.items()}
    return totals
