"""EventBus：collector 内存队列 + Channels group 批量广播（doc §5.4）。

- enqueue() 只入队，broadcast tick 统一 drain，避免逐条 group_send
- packets 事件单独缓冲，广播时打包成 {"type":"packets","data":{last_seq,events}}
"""

import json
from collections import deque

from core.utils.timeutil import now_ts

GROUP = "network"
MAX_ENVELOPE_QUEUE = 5000
MAX_PACKET_BATCH = 200


class EventBus:
    def __init__(self) -> None:
        self._queue: deque[dict] = deque()
        self._packets: deque[dict] = deque(maxlen=MAX_ENVELOPE_QUEUE)
        self.dropped_envelopes = 0
        self.dropped_packets = 0

    def enqueue(self, type_: str, data: dict) -> None:
        if len(self._queue) >= MAX_ENVELOPE_QUEUE:
            self.dropped_envelopes += 1
        self._queue.append({"type": type_, "timestamp": now_ts(), "data": data})

    def enqueue_packet(self, packet: dict) -> None:
        if len(self._packets) >= self._packets.maxlen:
            self.dropped_packets += 1
        self._packets.append(packet)

    def pending_packets(self) -> list[dict]:
        out = list(self._packets)
        self._packets.clear()
        return out

    def pending_envelopes(self) -> list[dict]:
        out = list(self._queue)
        self._queue.clear()
        return out

    async def broadcast_batch(self) -> int:
        """drain 队列并广播：packets 优先合并，其余逐条。返回发送的消息数。"""
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return 0
        sent = 0

        packets = self.pending_packets()
        for start in range(0, len(packets), MAX_PACKET_BATCH):
            batch = packets[start : start + MAX_PACKET_BATCH]
            envelope = {
                "type": "packets",
                "timestamp": now_ts(),
                "data": {
                    "last_seq": max((p.get("seq") or 0) for p in batch) if batch else 0,
                    "events": batch,
                },
            }
            await self._send(layer, envelope)
            sent += 1

        for envelope in self.pending_envelopes():
            await self._send(layer, envelope)
            sent += 1
        return sent

    async def _send(self, layer, envelope: dict) -> None:
        payload = json.dumps(envelope, ensure_ascii=False)
        await layer.group_send(GROUP, {"type": "broadcast.envelope", "payload": payload})

    async def send_immediate(self, type_: str, data: dict) -> None:
        """状态迁移/告警立即下发（不入队，保证及时性）。"""
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        await self._send(layer, {"type": type_, "timestamp": now_ts(), "data": data})
