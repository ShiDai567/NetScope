"""PacketService：seq 分配、事件发布、totals 计数。"""

from core.log import get_logger
from core.utils.network import is_public_ip
from network.adapters.ikuaipacket import adapt_packet
from network.services.resolved_view import _resolved_from_state

log = get_logger("network.services.packet")


class PacketService:
    def __init__(self, store, bus, counters) -> None:
        self._store = store
        self._bus = bus
        self._counters = counters

    def build_packet(
        self, state, key: str, now: float, kind: str, flag: str | None, lan_coords: dict | None = None
    ) -> dict:
        """由 ConnectionService 调用：分配 seq/id，组装契约 Packet。"""
        seq = self._store.next_seq()
        packet = adapt_packet(
            _resolved_from_state(state, kind),
            conn_key=key,
            seq=seq,
            now=now,
            born=state.born,
            status=state.status,
            status_since=state.status_since,
            flag=flag,
            app_name=state.application,
            protocol=state.protocol,
            interface=state.interface,
            total_up=state.total_up,
            total_down=state.total_down,
            domain=state.domain,
            geo_src=state.geo_src.as_dict() if state.geo_src else None,
            geo_dst=state.geo_dst.as_dict() if state.geo_dst else None,
            lan_coords=lan_coords,
        )
        return packet

    def publish(self, packets: list[dict]) -> None:
        """批量：Redis 发布 + 维度计数 + totals + 广播入队。"""
        if not packets:
            return
        self._store.publish_packets(packets)
        totals = {"total": len(packets)}
        closed = 0
        failed = 0
        for packet in packets:
            peer_country = None
            geo = None
            if packet["direction"] == "inbound":
                geo = packet.get("source") or {}
            else:
                geo = packet.get("destination") or {}
            if geo:
                country = geo.get("country")
                code = geo.get("code")
                if country and is_public_ip(geo.get("ip")):
                    peer_country = f"{code}|{country}" if code else f"|{country}"
            self._counters.add_event(packet, peer_country=peer_country)
            if packet.get("flag") == "failed":
                failed += 1
        closed = sum(1 for p in packets if p.get("status") == "关闭连接")
        totals["failed"] = failed
        totals["closed"] = closed
        self._store.incr_totals(**totals)
        for packet in packets:
            self._bus.enqueue_packet(packet)
