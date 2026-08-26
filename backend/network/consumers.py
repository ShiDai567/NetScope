"""NetworkConsumer：/ws/network/ 实时通道（doc §11）。

连接即下发 hello + snapshot，随后透传 collector 的批量广播。
consumer 只做订阅转发，零业务逻辑、零 DB 访问。
"""

import asyncio

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from core.log import get_logger
from core.redis_store import get_store
from core.utils.timeutil import now_ts

log = get_logger("network.ws")

_SNAPSHOT_WINDOW = 300


class NetworkConsumer(AsyncJsonWebsocketConsumer):
    groups = ["network"]

    async def connect(self) -> None:
        await self.accept()
        await self.channel_layer.group_add("network", self.channel_name)
        try:
            await self._send_hello()
        except Exception as exc:
            log.warning("ws.hello_failed", error=str(exc))

    async def disconnect(self, code) -> None:
        await self.channel_layer.group_discard("network", self.channel_name)

    async def receive_json(self, content, **kwargs) -> None:
        msg_type = content.get("type") if isinstance(content, dict) else None
        if msg_type == "ping":
            await self.send_json({"type": "pong", "timestamp": now_ts(), "data": {}})
            return
        # 未知类型静默忽略（协议向前兼容）

    # ------------------------------------------------------------ collector 广播透传

    async def broadcast_envelope(self, message) -> None:
        payload = message.get("payload")
        if payload:
            await self.send(text_data=payload)

    # ------------------------------------------------------------ 握手

    async def _send_hello(self) -> None:
        store = get_store()
        mode_info, last_seq = await asyncio.to_thread(self._read_mode, store)
        await self.send_json(
            {
                "type": "hello",
                "timestamp": now_ts(),
                "data": {
                    "server_time": now_ts(),
                    "seq": last_seq,
                    "mode": mode_info.get("mode", "unknown"),
                    "uptime": max(0, int(now_ts() - mode_info.get("started_at", now_ts()))),
                },
            }
        )
        snapshot = await asyncio.to_thread(store.get_stats, _SNAPSHOT_WINDOW)
        await self.send_json(
            {
                "type": "snapshot",
                "timestamp": now_ts(),
                "data": snapshot
                or {
                    "total": 0,
                    "active": 0,
                    "closed": 0,
                    "failed": 0,
                    "lost": 0,
                    "directions": {},
                    "protocols": {},
                    "apps": [],
                    "bandwidth": {"up_bps": 0.0, "down_bps": 0.0, "series": []},
                    "loss_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "system": {"cpu_percent": None, "memory_percent": None},
                    "latency_heatmap": {"x": [], "y": [], "data": []},
                    "mode": mode_info.get("mode", "unknown"),
                    "uptime": max(0, int(now_ts() - mode_info.get("started_at", now_ts()))),
                    "window": _SNAPSHOT_WINDOW,
                },
            }
        )

    @staticmethod
    def _read_mode(store) -> tuple[dict, int]:
        return store.get_mode(), store.last_seq()
