"""内置流量模拟引擎。

当未接入真实 iKuai 路由器时，由该引擎生成符合 AGENTS.md 数据结构的
连接事件流，覆盖：

- 三种方向（outbound / inbound / internal）
- 三种协议（tcp / udp / icmp）
- TCP 状态机：等待连接 -> 请求连接 -> 已连接 -> 关闭连接（含失败分支）
- UDP / ICMP 无状态流（status 为 None，部分丢包 / 高延迟标记）
- NAT 信息（forward_addr / original_dst 端口映射）
"""
from __future__ import annotations

import math
import random
import threading
import time
from typing import Any, Callable, Optional

from .geo import internal_ring_position, locate_public_ip
from .packets import (
    TCP_STATUS_CLOSED,
    TCP_STATUS_ESTABLISHED,
    TCP_STATUS_REQUESTING,
    TCP_STATUS_WAITING,
    build_packet,
)

# ---------------------------------------------------------------------------
# 静态世界模型
# ---------------------------------------------------------------------------

GATEWAY_IP = "10.0.1.1"

# (ip, mac, 名称, 厂商, 类型权重) 类型权重影响被选中的概率
LAN_DEVICES: list[tuple[str, str, str, str, float]] = [
    ("10.0.1.2", "60:be:b4:05:f3:67", "iStoreOS 旁路由", "iStoreOS", 3.0),
    ("10.0.1.10", "3c:22:fb:8a:41:9c", "林晚晴的 MacBook Pro", "Apple", 2.4),
    ("10.0.1.11", "a6:4f:c2:11:0d:58", "周叔的 iPhone 15 Pro", "Apple", 1.6),
    ("10.0.1.12", "8c:be:be:24:76:30", "小米 14 Ultra", "Xiaomi", 1.5),
    ("10.0.1.20", "00:11:32:9c:e1:07", "群晖 NAS DS923+", "Synology", 2.2),
    ("10.0.1.21", "5c:64:8e:02:bd:66", "极空间 Z4 Pro", "ZSpace", 1.1),
    ("10.0.1.30", "64:9e:31:3f:20:b4", "米家多模网关", "Xiaomi", 1.0),
    ("10.0.1.31", "70:2a:d5:88:c3:19", "石头扫地机器人", "Roborock", 0.6),
    ("10.0.1.40", "d0:7f:a0:45:12:88", "极米 RS 投影仪", "XGIMI", 0.9),
    ("10.0.1.50", "40:4d:7f:c9:3e:71", "工作室台式机", "HUAWEI", 2.0),
    ("192.168.2.100", "74:ac:b9:60:05:2d", "书房二级路由", "Qihoo360", 0.8),
    ("192.168.2.158", "c0:56:e3:1b:7a:94", "海康监控 NVR", "Hikvision", 0.9),
]

# (ip, domain, 应用名, lat, lng, 协议偏好, 端口偏好)
PUBLIC_SERVERS: list[tuple[str, str, str, float, float, str, int]] = [
    ("1.1.1.1", "one.one.one.one", "Cloudflare", 37.7749, -122.4194, "udp", 53),
    ("162.159.61.8", "dns.cloudflare.com", "Cloudflare", 37.7749, -122.4194, "tcp", 443),
    ("8.8.8.8", "dns.google", "DNS", 37.386, -122.0838, "udp", 53),
    ("223.5.5.5", "dns.alidns.com", "阿里系列", 30.2936, 120.1614, "udp", 53),
    ("119.29.29.29", "doh.pub", "腾讯私有协议", 22.5431, 114.0579, "tcp", 443),
    ("114.114.114.114", "public1.114dns.com", "DNS", 32.0617, 118.7778, "udp", 53),
    ("140.82.112.3", "github.com", "SSL", 37.7749, -122.4194, "tcp", 443),
    ("17.253.144.10", "apple.com", "SSL", 37.323, -122.0322, "tcp", 443),
    ("13.107.42.14", "microsoft.com", "HTTPS", 47.6424, -122.13, "tcp", 443),
    ("54.230.103.78", "cloudfront.net", "AWS", 35.6762, 139.6503, "tcp", 443),
    ("91.108.56.130", "telegram.org", "SSL", 52.52, 13.405, "tcp", 443),
    ("142.250.72.14", "google.com", "HTTPS", 37.386, -122.0838, "tcp", 443),
    ("110.242.68.3", "baidu.com", "网页浏览", 39.9042, 116.4074, "tcp", 443),
    ("101.89.178.14", "iqiyi.com", "视频流媒体", 31.2304, 121.4737, "tcp", 443),
    ("112.25.60.30", "bilibili.com", "视频流媒体", 31.2304, 121.4737, "tcp", 443),
    ("59.36.96.63", "qq.com", "腾讯私有协议", 22.5431, 114.0579, "tcp", 443),
    ("47.246.22.233", "aliyun.com", "阿里系列", 30.2936, 120.1614, "tcp", 443),
    ("58.216.109.14", "163.com", "网页浏览", 32.0617, 118.7778, "tcp", 80),
]

# (ip, 城市, lat, lng) 公网客户端（端口转发来源）
PUBLIC_CLIENTS: list[tuple[str, str, float, float]] = [
    ("103.86.44.17", "东京", 35.6762, 139.6503),
    ("77.234.41.206", "法兰克福", 50.1109, 8.6821),
    ("189.38.90.11", "圣保罗", -23.5505, -46.6333),
    ("23.129.64.210", "洛杉矶", 34.0522, -118.2437),
    ("51.140.180.66", "伦敦", 51.5074, -0.1278),
    ("139.180.208.77", "新加坡", 1.3521, 103.8198),
    ("203.119.238.180", "北京", 39.9042, 116.4074),
    ("103.117.100.55", "首尔", 37.5665, 126.978),
    ("85.195.88.140", "苏黎世", 47.3769, 8.5417),
    ("45.148.10.91", "阿姆斯特丹", 52.3676, 4.9041),
]

# 内网服务（internal 目标）: (ip, 端口, 应用, 协议)
INTERNAL_SERVICES: list[tuple[str, int, str, str]] = [
    (GATEWAY_IP, 53, "DNS", "udp"),
    ("192.168.2.1", 53, "DNS", "udp"),
    ("10.0.1.20", 445, "SMB", "tcp"),
    ("10.0.1.20", 5000, "群晖 DSM", "tcp"),
    ("10.0.1.21", 5055, "极影视", "tcp"),
    (GATEWAY_IP, 6301, "网页浏览", "tcp"),
    ("10.0.1.50", 22, "SSH", "tcp"),
    ("10.0.1.40", 7000, "投屏", "udp"),
    ("192.168.2.158", 8000, "监控回放", "tcp"),
]

# 入站端口映射（inbound）: (内网目标, 端口, 应用)
INBOUND_SERVICES: list[tuple[str, int, str]] = [
    ("10.0.1.2", 445, "SMB"),
    ("10.0.1.20", 5000, "群晖 DSM"),
    ("10.0.1.50", 3389, "远程桌面"),
    ("10.0.1.2", 8080, "端口转发 Web"),
    ("10.0.1.20", 22, "SSH"),
]

APP_BYTE_RATES: dict[str, tuple[int, int]] = {
    # 每秒 上行/下行 字节速率范围
    "DNS": (40, 400),
    "视频流媒体": (40_000, 600_000),
    "SMB": (20_000, 400_000),
    "远程桌面": (30_000, 250_000),
    "监控回放": (10_000, 300_000),
    "投屏": (20_000, 500_000),
    "BT数据下载": (150_000, 900_000),
}
DEFAULT_RATE = (1_000, 30_000)


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        (lng2 - lng1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class SimConnection:
    """单条模拟连接（一个数据包流的完整生命周期）。"""

    __slots__ = (
        "id",
        "direction",
        "protocol",
        "app_name",
        "device_ip",
        "dst_addr",
        "forward_addr",
        "src_port",
        "dst_port",
        "domain",
        "original_dst",
        "interface",
        "status",
        "flag",
        "total_up",
        "total_down",
        "born",
        "status_since",
        "close_at",
        "remove_at",
        "next_emit_at",
        "rate_up",
        "rate_down",
        "latency_ms",
        "fail_at_halfway",
    )

    def __init__(self, packet_id: str, now: float, rng: random.Random):
        self.id = packet_id
        self.direction: Optional[str] = None
        self.protocol: Optional[str] = None
        self.app_name: Optional[str] = None
        self.device_ip: Optional[str] = None
        self.dst_addr: Optional[str] = None
        self.forward_addr: Optional[str] = None
        self.src_port: int = 0
        self.dst_port: int = 0
        self.domain: Optional[str] = None
        self.original_dst: Optional[str] = None
        self.interface: Optional[str] = None
        self.status: Optional[str] = None
        self.flag: Optional[str] = None
        self.total_up = 0
        self.total_down = 0
        self.born = now
        self.status_since = now
        self.close_at: Optional[float] = None
        self.remove_at: Optional[float] = None
        self.next_emit_at = now
        self.rate_up: float = 0.0
        self.rate_down: float = 0.0
        self.latency_ms: float = 0.0
        self.fail_at_halfway = False


class SimulationEngine(threading.Thread):
    """后台线程：维护连接生命周期并向外发射标准化数据包事件。"""

    TICK = 0.5
    MAX_ACTIVE = 90

    def __init__(
        self,
        emit: Callable[[dict[str, Any]], None],
        gateway: tuple[float, float],
        device_snapshot: Callable[[list[dict[str, Any]], None], None] | None = None,
    ):
        super().__init__(name="netscope-simulation", daemon=True)
        self._emit = emit
        self._device_snapshot = device_snapshot
        self.gateway = gateway
        self._stop_event = threading.Event()
        self._rng = random.Random()
        self._seq = 0
        self._connections: dict[str, SimConnection] = {}
        self._lan_positions: dict[str, tuple[float, float]] = {}
        self._devices: list[dict[str, Any]] = []
        self._init_devices()

    # ------------------------------------------------------------------
    def _init_devices(self) -> None:
        devices = [
            {
                "ip": GATEWAY_IP,
                "mac": "60:be:b4:00:00:01",
                "hostname": "iKuai 主路由",
                "vendor": "iKuai",
                "interface": "lan1",
                "is_gateway": True,
            }
        ]
        for idx, (ip, mac, name, vendor, _w) in enumerate(LAN_DEVICES):
            devices.append(
                {
                    "ip": ip,
                    "mac": mac,
                    "hostname": name,
                    "vendor": vendor,
                    "interface": "lan1",
                    "is_gateway": False,
                    "ring_index": idx,
                }
            )
        for d in devices:
            if d.get("is_gateway"):
                self._lan_positions[d["ip"]] = self.gateway
            else:
                self._lan_positions[d["ip"]] = internal_ring_position(
                    d["ring_index"], self.gateway
                )
        self._devices = devices

    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:  # pragma: no cover - 线程循环
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception:
                # 模拟引擎任何异常都不应让后台线程死掉
                import traceback

                traceback.print_exc()
            self._stop_event.wait(self.TICK)

    # ------------------------------------------------------------------
    def tick(self) -> None:
        now = time.time()
        self._maybe_spawn(now)
        for conn in list(self._connections.values()):
            self._advance(conn, now)
        self._connections = {
            cid: c
            for cid, c in self._connections.items()
            if c.remove_at is None or now < c.remove_at
        }
        self._push_device_snapshot(now)

    # ------------------------------------------------------------------
    def _maybe_spawn(self, now: float) -> None:
        active = len(self._connections)
        if active >= self.MAX_ACTIVE:
            return
        # 每 tick 平均 0.65 个新连接
        expected = 0.65 if active < 60 else 0.3
        count = 0
        if self._rng.random() < expected:
            count = 1
            if self._rng.random() < expected * 0.45:
                count = 2
        for _ in range(count):
            self._spawn(now)

    def _spawn(self, now: float) -> None:
        rng = self._rng
        roll = rng.random()
        if roll < 0.58:
            direction = "outbound"
        elif roll < 0.83:
            direction = "internal"
        else:
            direction = "inbound"

        self._seq += 1
        conn = SimConnection(f"pkt_{self._seq:06d}", now, rng)
        conn.direction = direction

        device = self._pick_device()
        device_ip = device["ip"]

        if direction == "outbound":
            server = PUBLIC_SERVERS[rng.randrange(len(PUBLIC_SERVERS))]
            ip, domain, app, _lat, _lng, proto, port = server
            protocol = proto
            if rng.random() < 0.08:
                protocol, port, app = "icmp", 0, "Ping"
            conn.device_ip = device_ip
            conn.dst_addr = ip
            conn.forward_addr = device_ip
            conn.src_port = rng.randrange(1024, 65000)
            conn.dst_port = port
            conn.domain = domain
            conn.app_name = app
            conn.interface = "wan1"
            conn.protocol = protocol
        elif direction == "internal":
            svc = INTERNAL_SERVICES[rng.randrange(len(INTERNAL_SERVICES))]
            target_ip, port, app, proto = svc
            if svc[0] == device_ip:
                device = self._pick_device(exclude=svc[0])
                device_ip = device["ip"]
            conn.device_ip = device_ip
            conn.dst_addr = target_ip
            # DNS 查询经由网关转发；其余内网通信 forward_addr 即源设备
            conn.forward_addr = GATEWAY_IP if app == "DNS" else device_ip
            conn.src_port = rng.randrange(1024, 65000)
            conn.dst_port = port
            conn.domain = None
            conn.app_name = app
            conn.interface = "lan1"
            conn.protocol = proto
        else:  # inbound 端口转发
            client = PUBLIC_CLIENTS[rng.randrange(len(PUBLIC_CLIENTS))]
            target_ip, port, app = INBOUND_SERVICES[rng.randrange(len(INBOUND_SERVICES))]
            conn.device_ip = target_ip
            conn.dst_addr = target_ip
            conn.forward_addr = client[0]
            conn.src_port = rng.randrange(1024, 65000)
            conn.dst_port = port
            conn.domain = None
            conn.app_name = app
            conn.interface = "wan1"
            conn.protocol = "tcp"
            # 30% 的端口映射带有 original_dst（历史 NAT 目标）
            if rng.random() < 0.3:
                conn.original_dst = "192.168.2.158"
            else:
                conn.original_dst = None

        # 状态机初始
        if conn.protocol == "tcp":
            conn.status = TCP_STATUS_WAITING
            conn.close_at = now + rng.uniform(0.5, 1.6)
        else:
            conn.status = None  # UDP/ICMP 无连接状态
            life = rng.uniform(3.0, 16.0)
            conn.close_at = now + life
            if rng.random() < 0.05:
                conn.flag = "lost"
            elif rng.random() < 0.12:
                conn.flag = "high_latency"
            up_rate, down_rate = APP_BYTE_RATES.get(
                conn.app_name, DEFAULT_RATE
            )
            conn.rate_up = rng.uniform(0.4, 1.0) * up_rate
            conn.rate_down = rng.uniform(0.4, 1.0) * down_rate
            # 首个 UDP 数据报立即有载荷
            conn.total_up = int(rng.uniform(40, 200))
            conn.total_down = 0

        conn.latency_ms = self._base_latency(conn) * rng.uniform(0.85, 1.3)
        self._connections[conn.id] = conn
        self._emit_packet(conn, now, force=True)

    def _pick_device(self, exclude: Optional[str] = None) -> dict[str, Any]:
        pool = [d for d in self._devices if not d.get("is_gateway") and d["ip"] != exclude]
        weights = [w for (_ip, _m, _n, _v, w) in LAN_DEVICES if _ip in {d["ip"] for d in pool}]
        return self._rng.choices(pool, weights=weights or None, k=1)[0]

    def _base_latency(self, conn: SimConnection) -> float:
        if conn.direction == "internal":
            return self._rng.uniform(0.5, 4.0)
        dst = locate_public_ip(conn.dst_addr)[:2] if conn.direction == "outbound" else locate_public_ip(conn.forward_addr)[:2]
        km = _haversine_km(self.gateway, dst)
        return max(3.0, km / 55.0)

    # ------------------------------------------------------------------
    def _advance(self, conn: SimConnection, now: float) -> None:
        rng = self._rng
        if conn.protocol == "tcp":
            self._advance_tcp(conn, now)
        else:
            self._advance_udp(conn, now)

        # 已连接状态下按 tick 累积流量，并定期发射更新事件
        if conn.remove_at is None and conn.status in (TCP_STATUS_ESTABLISHED, None):
            if conn.protocol != "tcp" or conn.status == TCP_STATUS_ESTABLISHED:
                conn.total_up += int(conn.rate_up * self.TICK * rng.uniform(0.6, 1.4))
                conn.total_down += int(
                    conn.rate_down * self.TICK * rng.uniform(0.6, 1.4)
                )
                if now >= conn.next_emit_at:
                    self._emit_packet(conn, now)
                    conn.next_emit_at = now + rng.uniform(1.2, 2.2)

    def _advance_tcp(self, conn: SimConnection, now: float) -> None:
        rng = self._rng
        if conn.status == TCP_STATUS_WAITING and now >= (conn.close_at or now):
            conn.status = TCP_STATUS_REQUESTING
            conn.status_since = now
            conn.close_at = now + rng.uniform(0.3, 1.1)
            self._emit_packet(conn, now, force=True)
        elif conn.status == TCP_STATUS_REQUESTING and now >= (conn.close_at or now):
            if rng.random() < 0.05:
                # 连接失败：红色爆炸 / 半路消失
                conn.flag = "failed"
                conn.remove_at = now + 2.0
                conn.status_since = now
                self._emit_packet(conn, now, force=True)
            else:
                conn.status = TCP_STATUS_ESTABLISHED
                conn.status_since = now
                life = rng.uniform(5.0, 26.0)
                conn.close_at = now + life
                up_rate, down_rate = APP_BYTE_RATES.get(conn.app_name, DEFAULT_RATE)
                conn.rate_up = rng.uniform(0.4, 1.2) * up_rate
                conn.rate_down = rng.uniform(0.4, 1.2) * down_rate
                if rng.random() < 0.08:
                    conn.flag = "high_latency"
                self._emit_packet(conn, now, force=True)
        elif conn.status == TCP_STATUS_ESTABLISHED:
            # 高延迟标记可能自愈
            if conn.flag == "high_latency" and rng.random() < 0.04:
                conn.flag = None
                self._emit_packet(conn, now, force=True)
            elif conn.flag is None and rng.random() < 0.006:
                conn.flag = "high_latency"
                self._emit_packet(conn, now, force=True)
            if now >= (conn.close_at or now + 1):
                conn.status = TCP_STATUS_CLOSED
                conn.status_since = now
                conn.remove_at = now + 2.5
                self._emit_packet(conn, now, force=True)

    def _advance_udp(self, conn: SimConnection, now: float) -> None:
        if conn.remove_at is not None:
            return
        # 丢包标记在生命周期中段触发
        if conn.flag == "lost" and not conn.fail_at_halfway:
            if now >= conn.born + ((conn.close_at or now) - conn.born) * 0.5:
                conn.fail_at_halfway = True
                conn.remove_at = now + 1.6
                self._emit_packet(conn, now, force=True)
                return
        if now >= (conn.close_at or now + 1):
            conn.remove_at = now + 1.2  # UDP 静默消失，给一个淡出窗口

    # ------------------------------------------------------------------
    def _emit_packet(
        self, conn: SimConnection, now: float, force: bool = False
    ) -> None:
        packet = build_packet(
            packet_id=conn.id,
            timestamp=now,
            device_ip=conn.device_ip,
            protocol=conn.protocol,
            status=conn.status,
            dst_addr=conn.dst_addr,
            forward_addr=conn.forward_addr,
            src_port=conn.src_port,
            dst_port=conn.dst_port,
            app_name=conn.app_name,
            total_up=conn.total_up,
            total_down=conn.total_down,
            gateway=self.gateway,
            domain=conn.domain,
            original_dst=conn.original_dst,
            interface=conn.interface,
            flag=conn.flag,
            lan_positions=self._lan_positions,
        )
        packet["born"] = round(conn.born, 3)
        packet["latency_ms"] = round(
            conn.latency_ms * (3.2 if conn.flag == "high_latency" else 1.0), 1
        )
        packet["status_since"] = round(conn.status_since, 3)
        self._emit(packet)

    # ------------------------------------------------------------------
    def _push_device_snapshot(self, now: float) -> None:
        if not self._device_snapshot:
            return
        counts: dict[str, int] = {}
        rates: dict[str, list[float]] = {}
        for c in self._connections.values():
            if c.remove_at is not None:
                continue
            for ip in (c.device_ip, c.dst_addr, c.forward_addr):
                if ip in self._lan_positions:
                    counts[ip] = counts.get(ip, 0) + 1
            ip = c.device_ip
            if ip in self._lan_positions:
                r = rates.setdefault(ip, [0.0, 0.0])
                r[0] += c.rate_up
                r[1] += c.rate_down
        snapshot = []
        for d in self._devices:
            item = dict(d)
            item["lat"], item["lng"] = self._lan_positions[d["ip"]]
            item["connections"] = counts.get(d["ip"], 0)
            r = rates.get(d["ip"], [0.0, 0.0])
            item["up_rate"] = round(r[0], 1)
            item["down_rate"] = round(r[1], 1)
            snapshot.append(item)
        self._device_snapshot(snapshot)

    # ------------------------------------------------------------------
    def public_nodes(self) -> list[dict[str, Any]]:
        nodes = [
            {
                "ip": ip,
                "name": app,
                "domain": domain,
                "lat": lat,
                "lng": lng,
                "type": "server",
            }
            for (ip, domain, app, lat, lng, _p, _port) in PUBLIC_SERVERS
        ]
        nodes += [
            {"ip": ip, "name": city, "domain": None, "lat": lat, "lng": lng, "type": "client"}
            for (ip, city, lat, lng) in PUBLIC_CLIENTS
        ]
        return nodes
