"""滚动窗口维度计数（doc §8.2）。

双粒度桶：5s（覆盖 5/30s 窗口）+ 60s（覆盖 60~3600s 窗口）。
双结构：
  _pending —— 待写 Redis 的增量，flush 后清空（供 web 端 v2 排名读取）
  _history —— 滚动窗口累计，仅按时间淘汰（供 collector 统计快照读取）
"""

import threading
from collections import defaultdict

from core.utils.timeutil import bucket_ts

DIRECTIONS = "directions"
PROTOCOLS = "protocols"
APPLICATIONS = "applications"
PORTS = "ports"
COUNTRIES = "countries"
IPS_SRC = "ips_src"
IPS_DST = "ips_dst"

DIMS = (DIRECTIONS, PROTOCOLS, APPLICATIONS, PORTS, COUNTRIES, IPS_SRC, IPS_DST)
GRANULARITIES = (5, 60)


class RollingCounters:
    def __init__(self, horizon: float = 3700.0) -> None:
        self._lock = threading.Lock()
        self._horizon = horizon
        # _pending[(gran, dim)][bucket] = {field: [n, b]}
        self._pending: dict[tuple[int, str], dict[int, dict[str, list[int]]]] = defaultdict(dict)
        # _history 与 _pending 同构，但只在时间淘汰时清理
        self._history: dict[tuple[int, str], dict[int, dict[str, list[int]]]] = defaultdict(dict)

    # ------------------------------------------------------------ 写入

    def add_event(self, packet: dict, peer_country: str | None = None) -> None:
        """一次事件进全部维度（doc §8.2）。internal 不进 countries/ips 维度。"""
        now = packet.get("timestamp") or 0
        direction = packet.get("direction") or "unknown"
        total_bytes = int(packet.get("total_up") or 0) + int(packet.get("total_down") or 0)

        src = packet.get("source") or {}
        dst = packet.get("destination") or {}
        protocol = packet.get("protocol") or "unknown"
        app = packet.get("app_name") or "未知应用"
        dst_port = int(dst.get("port") or 0)
        src_ip = src.get("ip") or "?"
        dst_ip = dst.get("ip") or "?"

        with self._lock:
            self._bump(DIRECTIONS, now, direction, 1, total_bytes)
            self._bump(PROTOCOLS, now, protocol, 1, total_bytes)
            self._bump(APPLICATIONS, now, app, 1, total_bytes)
            if dst_port > 0:
                self._bump(PORTS, now, dst_port, 1, total_bytes)
            if direction != "internal":
                if peer_country:
                    self._bump(COUNTRIES, now, peer_country, 1, total_bytes)
                self._bump(IPS_SRC, now, src_ip, 1, total_bytes)
                self._bump(IPS_DST, now, dst_ip, 1, total_bytes)
            self._prune(now)

    def _bump(self, dim: str, now: float, field, n: int, b: int) -> None:
        field = str(field)
        for gran in GRANULARITIES:
            bucket = bucket_ts(now, gran)
            for store in (self._pending, self._history):
                slot = store[(gran, dim)].setdefault(bucket, {})
                agg = slot.setdefault(field, [0, 0])
                agg[0] += n
                agg[1] += b

    def _prune(self, now: float) -> None:
        horizon_bucket_5 = bucket_ts(now - self._horizon, 5)
        horizon_bucket_60 = bucket_ts(now - self._horizon, 60)
        for store in (self._pending, self._history):
            for (gran, _dim), buckets in store.items():
                horizon = horizon_bucket_5 if gran == 5 else horizon_bucket_60
                stale = [b for b in buckets if b < horizon]
                for b in stale:
                    buckets.pop(b, None)

    # ------------------------------------------------------------ 读取

    def flush_ops(self) -> list[tuple[str, int, int, str, int, int]]:
        """取走 pending 增量（写 Redis）：[(dim, gran, bucket, field, n, b)]。"""
        ops: list[tuple[str, int, int, str, int, int]] = []
        with self._lock:
            for (gran, dim), buckets in list(self._pending.items()):
                for bucket, fields in list(buckets.items()):
                    for field, (n, b) in fields.items():
                        ops.append((dim, gran, bucket, field, n, b))
                buckets.clear()
        return ops

    def window_top(self, dim: str, window: int, now: float, limit: int = 20) -> list[tuple[str, int, int]]:
        """history 合并窗口内数据，返回 [(field, count, bytes)] 按 count 降序。"""
        gran = 5 if window <= 30 else 60
        buckets = self._history.get((gran, dim), {})
        start_bucket = bucket_ts(now - window, gran)
        merged: dict[str, list[int]] = {}
        with self._lock:
            for bucket, fields in list(buckets.items()):
                if bucket < start_bucket:
                    continue
                for field, (n, b) in fields.items():
                    agg = merged.setdefault(field, [0, 0])
                    agg[0] += n
                    agg[1] += b
        ranked = sorted(merged.items(), key=lambda kv: kv[1][0], reverse=True)
        return [(field, n, b) for field, (n, b) in ranked[:limit]]

    def window_sum(self, dim: str, window: int, now: float, field: str | None = None) -> int:
        """窗口内某维度（可选指定 field）的 count 总和。"""
        gran = 5 if window <= 30 else 60
        buckets = self._history.get((gran, dim), {})
        start_bucket = bucket_ts(now - window, gran)
        total = 0
        with self._lock:
            for bucket, fields in list(buckets.items()):
                if bucket < start_bucket:
                    continue
                for f, (n, _b) in fields.items():
                    if field is None or f == field:
                        total += n
        return total
