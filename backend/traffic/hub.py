"""TrafficHub：全局流量状态中枢。

- 管理数据源（模拟引擎 / iKuai 轮询器）的生命周期
- 统一事件出口：为每个数据包事件分配递增 seq，写入环形事件日志
- 聚合统计、设备列表、节点列表
- 线程安全
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Optional

from django.conf import settings

from .ikuai import IKuaiPoller
from .simulation import GATEWAY_IP, SimulationEngine
from .stats import StatsTracker

EVENT_LOG_SIZE = 12000


class TrafficHub:
    def __init__(self) -> None:
        self.gateway = (settings.GATEWAY_LAT, settings.GATEWAY_LNG)
        self._lock = threading.RLock()
        self._started = False
        self._started_at = time.time()
        self._mode = "simulation"
        self._engine: Optional[SimulationEngine] = None
        self._poller: Optional[IKuaiPoller] = None
        self._events: deque[dict[str, Any]] = deque(maxlen=EVENT_LOG_SIZE)
        self._seq = 0
        self._stats = StatsTracker()
        self._devices: list[dict[str, Any]] = []
        self._active_index: dict[str, float] = {}
        self._terminal_index: dict[str, float] = {}
        self._ikuai_info: dict[str, Any] = {}
        self._ikuai_error: Optional[str] = None

    # ------------------------------------------------------------------
    def ensure_started(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._start_simulation_locked()

    def _start_simulation_locked(self) -> None:
        if self._engine and self._engine.is_alive():
            return
        self._engine = SimulationEngine(
            emit=self._emit,
            gateway=self.gateway,
            device_snapshot=self._set_devices,
        )
        self._engine.start()
        self._mode = "simulation"

    # ------------------------------------------------------------------
    def _emit(self, packet: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            event = dict(packet)
            event["seq"] = self._seq
            self._events.append(event)
            now = time.time()
            pid = event["id"]
            if event.get("status") == "关闭连接" or event.get("flag") in {"failed", "lost"}:
                # 终态：从活跃索引移除，记录终结时间用于统计
                self._active_index.pop(pid, None)
                self._terminal_index.setdefault(pid, now)
            else:
                self._active_index[pid] = now
            self._stats.ingest(event)

    def _set_devices(self, devices: list[dict[str, Any]]) -> None:
        with self._lock:
            self._devices = devices

    # ------------------------------------------------------------------
    def events_since(self, seq: int) -> dict[str, Any]:
        with self._lock:
            events = [e for e in self._events if e["seq"] > seq]
            return {"server_time": round(time.time(), 3), "last_seq": self._seq, "events": events}

    def history(self, minutes: float) -> dict[str, Any]:
        cutoff = time.time() - minutes * 60
        with self._lock:
            events = [e for e in self._events if e.get("timestamp", 0) >= cutoff]
            return {"server_time": round(time.time(), 3), "last_seq": self._seq, "events": events}

    # ------------------------------------------------------------------
    def stats_snapshot(self) -> dict[str, Any]:
        with self._lock:
            active = self._count_active_locked()
            snapshot = self._stats.snapshot(active)
            snapshot["mode"] = self._mode
            snapshot["uptime"] = round(time.time() - self._started_at, 1)
            return snapshot

    def _count_active_locked(self) -> int:
        now = time.time()
        # 12 秒内有事件且未终结的连接视为活跃
        self._active_index = {
            pid: ts for pid, ts in self._active_index.items() if now - ts <= 12
        }
        if len(self._terminal_index) > 4000:
            cutoff = now - 600
            self._terminal_index = {
                pid: ts for pid, ts in self._terminal_index.items() if ts >= cutoff
            }
        return len(self._active_index)

    def devices(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(d) for d in self._devices]

    def nodes(self) -> list[dict[str, Any]]:
        with self._lock:
            nodes = [
                {
                    "ip": GATEWAY_IP,
                    "name": "iKuai 主路由",
                    "domain": None,
                    "lat": self.gateway[0],
                    "lng": self.gateway[1],
                    "type": "gateway",
                }
            ]
            if self._engine is not None and self._mode == "simulation":
                nodes += self._engine.public_nodes()
        return nodes

    # ------------------------------------------------------------------
    def connect_ikuai(
        self, router_url: str, username: str, password: str
    ) -> dict[str, Any]:
        self.ensure_started()
        poller = IKuaiPoller(
            router_url=router_url,
            username=username,
            password=password,
            emit=self._emit,
            device_snapshot=self._set_devices,
            gateway=self.gateway,
            on_error=self._on_ikuai_error,
        )
        login_info = poller.test_connection()  # 失败会抛 IKuaiError
        with self._lock:
            if self._poller is not None:
                self._poller.stop()
            if self._engine is not None:
                self._engine.stop()
                self._engine = None
            self._poller = poller
            self._mode = "ikuai"
            self._ikuai_error = None
            self._ikuai_info = {
                "router_url": router_url,
                "username": username,
                "connected_at": round(time.time(), 1),
                "login": login_info,
            }
        poller.start()
        return {"mode": self._mode, "ikuai": self._ikuai_info}

    def disconnect_ikuai(self) -> dict[str, Any]:
        with self._lock:
            if self._poller is not None:
                self._poller.stop()
                self._poller = None
            self._ikuai_info = {}
            self._ikuai_error = None
            self._start_simulation_locked()
        return {"mode": self._mode}

    def _on_ikuai_error(self, message: str) -> None:
        with self._lock:
            self._ikuai_error = message

    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "uptime": round(time.time() - self._started_at, 1),
                "gateway": {"lat": self.gateway[0], "lng": self.gateway[1]},
                "ikuai": {
                    **self._ikuai_info,
                    "error": self._ikuai_error,
                    "last_poll_at": getattr(self._poller, "last_poll_at", None),
                },
            }


hub = TrafficHub()
