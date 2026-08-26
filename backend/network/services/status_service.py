"""StatusService：模式、网关定位、iKuai 健康、公网节点表。"""

import socket

from core.log import get_logger
from core.utils.network import is_public_ip, valid_ip
from core.utils.timeutil import now_ts

log = get_logger("network.services.status")


class StatusService:
    def __init__(
        self,
        store,
        bus,
        geo_service,
        server_lat=None,
        server_lng=None,
        server_location: str | None = None,
        on_geo_change=None,
    ) -> None:
        self._store = store
        self._bus = bus
        self._geo = geo_service
        self._server_lat = server_lat
        self._server_lng = server_lng
        self._server_location = server_location
        self._on_geo_change = on_geo_change
        self._started = False
        self._gateway_center_cache: tuple[float, float] | None = None

    # ------------------------------------------------------------ 模式

    def ensure_started(self, mode: str) -> None:
        if self._started:
            return
        self._store.set_mode(mode)
        self._started = True
        log.info("collector.mode", mode=mode)

    def mode_info(self) -> dict:
        return self._store.get_mode()

    def uptime(self) -> int:
        info = self._store.get_mode()
        return max(0, int(now_ts() - info.get("started_at", now_ts())))

    # ------------------------------------------------------------ 核心服务器定位

    def update_gateway_from_wan(self, wan_ip: str | None) -> None:
        """核心服务器定位（doc §7.3 优先级）：
        SERVER_LAT/LNG 显式坐标 > SERVER_LOCATION 域名/IP 解析+GeoIP > WAN IP GeoIP。

        位置发生变化时 bump geo_epoch 并清空事件缓冲——
        旧事件的私网端伪坐标围绕旧中心生成，全部作废（前端联动清理）。
        """
        if self._server_lat is not None and self._server_lng is not None:
            self._apply(self._server_lat, self._server_lng, wan_ip)
            return
        if self._server_location:
            location_ip = self._resolve_location(self._server_location)
            if location_ip:
                info = self._geo.lookup(location_ip)
                if info and info.lat is not None and info.lng is not None:
                    self._apply(info.lat, info.lng, wan_ip, location_ip)
                    return
                log.warning("server_location.geo_miss", location=self._server_location)
        if wan_ip:
            info = self._geo.lookup(wan_ip)
            if info and info.lat is not None and info.lng is not None:
                self._apply(info.lat, info.lng, wan_ip)
                return
        self._apply(None, None, wan_ip)

    def _resolve_location(self, location: str) -> str | None:
        """SERVER_LOCATION → 公网 IP：IP 直传用之；域名 DNS 解析取首个公网 A 记录。"""
        ip = valid_ip(location)
        if ip:
            return ip if is_public_ip(ip) else None
        try:
            infos = socket.getaddrinfo(location, None, socket.AF_INET)
        except OSError as exc:
            log.warning("server_location.dns_failed", location=location, error=str(exc))
            return None
        for info in infos:
            candidate = info[4][0]
            if is_public_ip(candidate):
                return candidate
        return None

    def _apply(
        self,
        lat: float | None,
        lng: float | None,
        wan_ip: str | None,
        location_ip: str | None = None,
    ) -> None:
        prev = self._store.get_gateway()
        prev_pos = (prev.get("lat"), prev.get("lng"))
        new_pos = (lat, lng)
        moved = (
            new_pos != prev_pos
            and lat is not None
            and lng is not None
            and prev_pos != (None, None)
        )

        label = location_ip or wan_ip
        self._store.set_gateway(lat, lng, label)
        if lat is not None and lng is not None:
            self._gateway_center_cache = (lat, lng)
        else:
            self._gateway_center_cache = None

        if location_ip:
            log.info(
                "server_location.resolved",
                location=self._server_location,
                ip=location_ip,
                lat=round(lat, 4) if lat is not None else None,
                lng=round(lng, 4) if lng is not None else None,
            )
        if moved:
            self._handle_geo_change(lat, lng)

    def _handle_geo_change(self, lat: float, lng: float) -> None:
        """核心位置变更联动：纪元递增 + 清事件缓冲 + 回调（设备重排/前端广播）。"""
        try:
            epoch = self._store.bump_geo_epoch()
            cleared = self._store.clear_packets()
            log.info(
                "geo.epoch_bumped",
                epoch=epoch,
                cleared_packets=cleared,
                lat=round(lat, 4),
                lng=round(lng, 4),
            )
        except Exception as exc:
            log.warning("geo.epoch_bump_failed", error=str(exc))
            return
        if self._on_geo_change:
            try:
                self._on_geo_change(lat, lng, epoch)
            except Exception as exc:
                log.warning("geo.change_callback_failed", error=str(exc))

    def gateway_center(self) -> tuple[float, float] | None:
        if self._gateway_center_cache:
            return self._gateway_center_cache
        gw = self._store.get_gateway()
        if gw["lat"] is not None and gw["lng"] is not None:
            self._gateway_center_cache = (gw["lat"], gw["lng"])
            return self._gateway_center_cache
        return None

    # ------------------------------------------------------------ iKuai 健康

    def record_poll_ok(self, router_url: str | None, connected_at: float | None,
                       last_poll_at: float | None) -> None:
        self._store.set_ikuai_health(
            router_url=router_url,
            error=None,
            connected_at=connected_at,
            last_poll_at=last_poll_at,
        )

    def record_error(self, router_url: str | None, error: str | None,
                     last_poll_at: float | None, connected_at: float | None) -> None:
        self._store.set_ikuai_health(
            router_url=router_url,
            error=error,
            last_poll_at=last_poll_at,
            connected_at=connected_at,
        )

    async def notify_state_change(self, connected: bool, error: str | None) -> None:
        """SessionManager 状态迁移 → status 事件 + SystemEvent 留痕（DB 由 runtime 写）。"""
        state = "ikuai_connected" if connected else "ikuai_disconnected"
        await self._bus.send_immediate(
            "status",
            {"state": state, "error": error, "t": now_ts()},
        )

    # ------------------------------------------------------------ 公网节点

    def rebuild_nodes(self, peers: list[dict]) -> None:
        """top peers → 节点表（type: server=出站目标 / client=入站来源）。

        name 使用 IP 归属地文本（中文），域名保留在 domain 字段。
        """
        nodes = []
        for peer in peers:
            info = self._geo.lookup(peer["ip"])
            if info is None or info.lat is None or info.lng is None:
                continue
            node_type = "server" if peer.get("direction") != "inbound" else "client"
            nodes.append(
                {
                    "ip": peer["ip"],
                    "name": info.location_text() or peer["ip"],
                    "domain": peer.get("domain"),
                    "lat": info.lat,
                    "lng": info.lng,
                    "type": node_type,
                }
            )
        if nodes:
            self._store.put_nodes(nodes)
