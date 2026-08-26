"""实时统计聚合器。

从标准化数据包事件流中聚合：
- 连接计数（总数 / 活跃 / 已关闭 / 失败）
- 方向 / 协议 / 应用分布
- 实时带宽（每秒 bucket 序列）
- 丢包率 / 平均延迟
- 区域 x 时间 延迟热力图
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Optional

from .geo import is_private_ip
from .packets import (
    DIRECTION_INBOUND,
    DIRECTION_INTERNAL,
    DIRECTION_OUTBOUND,
    TCP_STATUS_CLOSED,
)

REGIONS = ["内网", "国内", "亚太", "北美", "欧洲", "其他"]
HEATMAP_BUCKETS = 12
HEATMAP_BUCKET_SECONDS = 10
BANDWIDTH_BUCKETS = 120


def classify_region(packet: dict[str, Any]) -> str:
    """按对端位置归类区域。"""
    direction = packet.get("direction")
    peer = (
        packet.get("destination")
        if direction == DIRECTION_OUTBOUND
        else packet.get("source")
    ) or {}
    ip = peer.get("ip") or ""
    if direction == DIRECTION_INTERNAL or is_private_ip(ip):
        return "内网"
    lat, lng = peer.get("lat") or 0.0, peer.get("lng") or 0.0
    if 73 <= lng <= 135 and 18 <= lat <= 53:
        return "国内"
    if 60 <= lng <= 180 and -15 <= lat <= 55:
        return "亚太"
    if -170 <= lng <= -50 and 15 <= lat <= 75:
        return "北美"
    if -15 <= lng <= 60 and 35 <= lat <= 72:
        return "欧洲"
    return "其他"


class StatsTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total = 0
            self.failed = 0
            self.closed = 0
            self.lost = 0
            self.directions = {DIRECTION_OUTBOUND: 0, DIRECTION_INBOUND: 0, DIRECTION_INTERNAL: 0}
            self.protocols = {"tcp": 0, "udp": 0, "icmp": 0}
            self.apps: dict[str, int] = {}
            # 外部权威带宽样本（iKuai 接口实时速率）：(ts, up_bps, down_bps)
            self._ext_bw: Optional[tuple[float, float, float]] = None
            # 系统负载（iKuai monitor_system 最新采样）
            self.system: dict[str, Optional[float]] = {
                "cpu_percent": None,
                "memory_percent": None,
            }
            self._seen_ids: set[str] = set()
            self._terminal_ids: set[str] = set()
            self._counters: dict[str, tuple[int, int, float]] = {}
            self._latencies: deque[tuple[float, float]] = deque(maxlen=600)
            now = time.time()
            self._bw_buckets: deque[list[float]] = deque(
                [[now, 0.0, 0.0]], maxlen=BANDWIDTH_BUCKETS
            )
            self._heat_start = now - (now % HEATMAP_BUCKET_SECONDS)
            self._heat: list[list[list[float]]] = [
                [[] for _ in range(HEATMAP_BUCKETS)] for _ in REGIONS
            ]
            self._heat_times = [
                self._heat_start + i * HEATMAP_BUCKET_SECONDS
                for i in range(HEATMAP_BUCKETS)
            ]

    # ------------------------------------------------------------------
    def ingest_bandwidth(self, up_bps: float, down_bps: float) -> None:
        """外部权威带宽数据（bits/s，来自 iKuai 接口实时速率）。

        样本新鲜期内接管带宽序列与瞬时值，连接差分自动退位，
        避免两套口径混算导致数值失真。
        """
        now = time.time()
        with self._lock:
            self._ext_bw = (now, float(up_bps), float(down_bps))
            bucket = self._bw_buckets[-1]
            if now - bucket[0] >= 1.0:
                bucket = [now, 0.0, 0.0]
                self._bw_buckets.append(bucket)
            bucket[1] = float(up_bps)
            bucket[2] = float(down_bps)

    def set_system(self, cpu_percent: float, memory_percent: float) -> None:
        with self._lock:
            self.system = {
                "cpu_percent": round(float(cpu_percent), 1),
                "memory_percent": round(float(memory_percent), 1),
            }

    def _ext_bw_fresh(self, now: float) -> bool:
        return self._ext_bw is not None and now - self._ext_bw[0] <= 15.0

    def ingest(self, packet: dict[str, Any]) -> None:
        now = time.time()
        pid = packet.get("id") or ""
        with self._lock:
            first_seen = pid not in self._seen_ids
            if first_seen:
                self._seen_ids.add(pid)
                self.total += 1
                direction = packet.get("direction")
                if direction in self.directions:
                    self.directions[direction] += 1
                proto = (packet.get("protocol") or "").lower()
                if proto in self.protocols:
                    self.protocols[proto] += 1
                app = packet.get("app_name") or "未知协议"
                self.apps[app] = self.apps.get(app, 0) + 1

            # 终态计数（同一条连接只记一次）
            flag = packet.get("flag")
            status = packet.get("status")
            if pid not in self._terminal_ids:
                if flag == "failed":
                    self._terminal_ids.add(pid)
                    self.failed += 1
                elif flag == "lost":
                    self._terminal_ids.add(pid)
                    self.lost += 1
                elif status == TCP_STATUS_CLOSED:
                    self._terminal_ids.add(pid)
                    self.closed += 1

            # 带宽：按连接累计值的差分计入当前秒 bucket。
            # 首次见到的连接只建立基线——历史累计流量（可能达 GB 级）
            # 不能算作"当前瞬间带宽"，否则会出现虚假 Gbps 尖峰。
            # 权威接口样本新鲜时跳过差分累加，仅维护基线防止口径切换突刺。
            up = int(packet.get("total_up") or 0)
            down = int(packet.get("total_down") or 0)
            prev = self._counters.get(pid)
            if prev is None:
                d_up, d_down = 0, 0
            else:
                d_up, d_down = max(0, up - prev[0]), max(0, down - prev[1])
            self._counters[pid] = (up, down, now)
            if len(self._counters) > 6000:
                cutoff = now - 600
                self._counters = {
                    k: v for k, v in self._counters.items() if v[2] >= cutoff
                }
            if (d_up or d_down) and not self._ext_bw_fresh(now):
                bucket = self._bw_buckets[-1]
                if now - bucket[0] >= 1.0:
                    bucket = [now, 0.0, 0.0]
                    self._bw_buckets.append(bucket)
                bucket[1] += d_up
                bucket[2] += d_down

            # 延迟样本
            latency = packet.get("latency_ms")
            if isinstance(latency, (int, float)) and latency >= 0:
                self._latencies.append((now, float(latency)))
                region_idx = REGIONS.index(classify_region(packet))
                slot = int((now - self._heat_start) // HEATMAP_BUCKET_SECONDS)
                if slot >= HEATMAP_BUCKETS:
                    self._rotate_heatmap(now)
                    slot = HEATMAP_BUCKETS - 1
                self._heat[region_idx][slot].append(float(latency))

    # ------------------------------------------------------------------
    def _rotate_heatmap(self, now: float) -> None:
        new_start = now - (now % HEATMAP_BUCKET_SECONDS) - HEATMAP_BUCKET_SECONDS * (
            HEATMAP_BUCKETS - 1
        )
        self._heat_start = new_start
        self._heat_times = [
            new_start + i * HEATMAP_BUCKET_SECONDS for i in range(HEATMAP_BUCKETS)
        ]
        self._heat = [[[] for _ in range(HEATMAP_BUCKETS)] for _ in REGIONS]

    # ------------------------------------------------------------------
    def snapshot(self, active: int) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            series = [
                [round(b[0], 1), round(b[1] * 8, 1), round(b[2] * 8, 1)]
                for b in self._bw_buckets
            ]
            recent = [v for (t, v) in self._latencies if now - t <= 60]
            avg_latency = round(sum(recent) / len(recent), 1) if recent else 0.0
            terminal = self.failed + self.lost + self.closed
            loss_rate = (
                round((self.failed + self.lost) / max(1, terminal) * 100, 2)
                if terminal
                else 0.0
            )
            heat_data: list[list[float]] = []
            for y, row in enumerate(self._heat):
                for x, cell in enumerate(row):
                    if cell:
                        heat_data.append(
                            [x, y, round(sum(cell) / len(cell), 1)]
                        )
            top_apps = sorted(self.apps.items(), key=lambda kv: -kv[1])[:8]
            if self._ext_bw is not None and self._ext_bw_fresh(now):
                # iKuai 接口实时速率是权威口径
                _, up_now, down_now = self._ext_bw
            else:
                up_now, down_now = series[-1][1], series[-1][2]
            return {
                "total": self.total,
                "active": active,
                "closed": self.closed,
                "failed": self.failed,
                "lost": self.lost,
                "directions": dict(self.directions),
                "protocols": dict(self.protocols),
                "apps": [{"name": n, "count": c} for n, c in top_apps],
                "bandwidth": {
                    "up_bps": round(up_now, 1),
                    "down_bps": round(down_now, 1),
                    "series": series,
                },
                "system": dict(self.system),
                "loss_rate": loss_rate,
                "avg_latency_ms": avg_latency,
                "latency_heatmap": {
                    "x": [round(t, 0) for t in self._heat_times],
                    "y": REGIONS,
                    "data": heat_data,
                },
            }
