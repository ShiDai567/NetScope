"""网络工具：私网判断（§23）、连接标识、地址解析。"""

import hashlib
import ipaddress
from urllib.parse import urlparse


def valid_ip(value) -> str | None:
    """归一化合法 IP 字符串，非法返回 None。"""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw or raw == "--":
        return None
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return None
    return str(ip)


def is_private_ip(value) -> bool:
    """私网/回环/链路本地等不可公网定位地址。解析失败视为私网（保守）。"""
    ip = valid_ip(value)
    if ip is None:
        return True
    addr = ipaddress.ip_address(ip)
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def is_public_ip(value) -> bool:
    ip = valid_ip(value)
    if ip is None:
        return False
    return not is_private_ip(ip)


def ip_to_int(value) -> int:
    """IP 转整数用于稳定排序（非法回退 0）。"""
    ip = valid_ip(value)
    if ip is None:
        return 0
    return int(ipaddress.ip_address(ip))


def conn_key(local_ip: str, local_port: int, remote_ip: str, remote_port: int, protocol: str) -> str:
    """连接稳定标识：sha1(local:port-remote:port-proto)[:24]。"""
    raw = f"{local_ip}:{int(local_port)}-{remote_ip}:{int(remote_port)}-{str(protocol).lower()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:24]


def host_of(url: str) -> str | None:
    """从 URL 提取主机名（用于从 IKUAI_ROUTER_URL 推导网关内网 IP）。"""
    try:
        host = urlparse(str(url)).hostname
    except ValueError:
        return None
    return host or None


def valid_port(value, default: int = 0) -> int:
    """端口清洗：0~65535，非法回退 default。"""
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    if 0 <= port <= 65535:
        return port
    return default
