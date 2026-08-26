"""数据包方向判断与标准化构建。

严格遵循 AGENTS.md 的判断规则：

1. 向外发包（内网设备 -> 公网）: dst_addr 是公网 IP, forward_addr 是内网 IP
2. 外部接受（公网 -> 内网设备）: dst_addr 是内网 IP, forward_addr 是公网 IP
3. 内网通信（内网 <-> 内网）: dst_addr 和 forward_addr 都是内网 IP

Source/Destination 映射：
- 向外发包: source=内网设备, destination=公网服务器
- 外部接受: source=公网客户端, destination=内网设备
- 内网通信: source=内网设备A, destination=内网设备B
"""
from __future__ import annotations

import time
from typing import Any, Optional

from .geo import is_private_ip, is_public_ip, locate_public_ip

TCP_STATUS_WAITING = "等待连接"
TCP_STATUS_REQUESTING = "请求连接"
TCP_STATUS_ESTABLISHED = "已连接"
TCP_STATUS_CLOSED = "关闭连接"
UDP_STATUS = "--"

TCP_STATUSES = {
    TCP_STATUS_WAITING,
    "等待",  # iKuai 原始数据里存在 "等待" 写法，统一归一
    TCP_STATUS_REQUESTING,
    TCP_STATUS_ESTABLISHED,
    TCP_STATUS_CLOSED,
}

DIRECTION_OUTBOUND = "outbound"
DIRECTION_INBOUND = "inbound"
DIRECTION_INTERNAL = "internal"


def normalize_status(protocol: str, raw_status: Optional[str]) -> Optional[str]:
    """UDP 无连接状态（None / "--"），TCP 状态归一到四种之一。"""
    proto = (protocol or "").lower()
    if proto != "tcp":
        return None
    status = (raw_status or "").strip()
    if status in {"", "--", "null", "None"}:
        return None
    if status == "等待":
        return TCP_STATUS_WAITING
    return status


def judge_direction(dst_addr: str, forward_addr: str) -> str:
    """按 AGENTS.md 规则判断方向。"""
    dst_private = is_private_ip(dst_addr)
    fwd_private = is_private_ip(forward_addr)
    if not dst_private and fwd_private:
        return DIRECTION_OUTBOUND
    if dst_private and not fwd_private:
        return DIRECTION_INBOUND
    return DIRECTION_INTERNAL


def _endpoint(
    ip: str,
    port: int,
    gateway: tuple[float, float],
    lan_positions: Optional[dict[str, tuple[float, float]]] = None,
    domain: Optional[str] = None,
) -> dict[str, Any]:
    if is_private_ip(ip):
        lat, lng = (lan_positions or {}).get(ip, gateway)
    else:
        lat, lng, _label = locate_public_ip(ip)
    return {
        "ip": ip,
        "port": int(port or 0),
        "domain": domain if domain and domain != "--" else None,
        "lat": lat,
        "lng": lng,
    }


def build_packet(
    *,
    packet_id: str,
    timestamp: float,
    device_ip: str,
    protocol: str,
    status: Optional[str],
    dst_addr: str,
    forward_addr: str,
    src_port: int,
    dst_port: int,
    app_name: Optional[str],
    total_up: int,
    total_down: int,
    gateway: tuple[float, float],
    domain: Optional[str] = None,
    original_dst: Optional[str] = None,
    interface: Optional[str] = None,
    lan_positions: Optional[dict[str, tuple[float, float]]] = None,
) -> dict[str, Any]:
    """把一条 iKuai 连接记录转换为 AGENTS.md 标准 JSON。"""
    proto = (protocol or "tcp").lower()
    direction = judge_direction(dst_addr, forward_addr)

    if direction == DIRECTION_OUTBOUND:
        source_ip = device_ip if is_private_ip(device_ip) else forward_addr
        destination_ip = dst_addr
        source_port, destination_port = src_port, dst_port
        dst_domain = domain
        src_domain = None
    elif direction == DIRECTION_INBOUND:
        source_ip = forward_addr
        destination_ip = dst_addr
        source_port, destination_port = src_port, dst_port
        dst_domain = None
        src_domain = domain if domain and domain != "--" else None
    else:
        source_ip = forward_addr if is_private_ip(forward_addr) else device_ip
        destination_ip = dst_addr
        source_port, destination_port = src_port, dst_port
        dst_domain = None
        src_domain = None

    packet: dict[str, Any] = {
        "id": packet_id,
        "timestamp": round(timestamp, 3),
        "direction": direction,
        "app_name": app_name or "未知协议",
        "protocol": proto,
        "status": normalize_status(proto, status),
        "source": _endpoint(
            source_ip, source_port, gateway, lan_positions, src_domain
        ),
        "destination": _endpoint(
            destination_ip, destination_port, gateway, lan_positions, dst_domain
        ),
        "nat_info": {
            "forward_addr": forward_addr,
            "src_port": int(src_port or 0),
            "dst_port": int(dst_port or 0),
        },
        "total_up": int(total_up or 0),
        "total_down": int(total_down or 0),
    }
    if original_dst and original_dst != "--":
        packet["nat_info"]["original_dst"] = original_dst
    if interface and interface != "--":
        packet["interface"] = interface
    return packet
