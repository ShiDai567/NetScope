"""IP 地理位置与内外网判断工具。

- 内网 IP 判定遵循 RFC1918 / 链路本地 / 回环等常见私有段
- 公网 IP 定位优先查内置常用服务地址表，再查内存缓存（在线查询结果），
  未命中的地址按确定性哈希兜底（仅作渲染占位，同一 IP 落点一致）。
- 在线查询走多服务商容灾链：ipwho.is → api.ip.sb，后台线程串行执行，
  避免阻塞实时流量处理，并遵守各服务商免费额度限速。
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

logger = logging.getLogger("netscope.geo")

Coord = Tuple[float, float]  # (lat, lng)

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("0.0.0.0/8"),
]


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return False
    if addr.version != 4:
        return True
    return any(addr in net for net in _PRIVATE_NETWORKS)


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return False
    return addr.version == 4 and not is_private_ip(ip)


# ---------------------------------------------------------------------------
# 静态已知表（常用服务 IP，避免重复查询）
# ---------------------------------------------------------------------------
KNOWN_GEO: dict[str, Tuple[float, float, str]] = {
    # DNS
    "1.1.1.1": (37.7749, -122.4194, "Cloudflare DNS"),
    "1.0.0.1": (37.7749, -122.4194, "Cloudflare DNS"),
    "8.8.8.8": (37.386, -122.0838, "Google DNS"),
    "8.8.4.4": (37.386, -122.0838, "Google DNS"),
    "223.5.5.5": (30.2936, 120.1614, "阿里 DNS"),
    "223.6.6.6": (30.2936, 120.1614, "阿里 DNS"),
    "119.29.29.29": (22.5431, 114.0579, "腾讯 DNSPod"),
    "114.114.114.114": (32.0617, 118.7778, "114 DNS"),
    "114.114.115.115": (32.0617, 118.7778, "114 DNS"),
    "180.76.76.76": (39.9042, 116.4074, "百度 DNS"),
    # Cloudflare 段常见地址
    "162.159.61.8": (37.7749, -122.4194, "Cloudflare"),
    "162.159.62.9": (37.7749, -122.4194, "Cloudflare"),
    "104.16.85.20": (37.7749, -122.4194, "Cloudflare CDN"),
    # 海外服务
    "140.82.112.3": (37.7749, -122.4194, "GitHub"),
    "140.82.113.3": (37.7749, -122.4194, "GitHub"),
    "140.82.116.4": (37.7749, -122.4194, "GitHub"),
    "185.199.108.153": (37.7749, -122.4194, "GitHub Pages"),
    "17.253.144.10": (37.323, -122.0322, "Apple"),
    "17.57.145.169": (37.323, -122.0322, "Apple"),
    "13.107.42.14": (47.6424, -122.13, "Microsoft"),
    "20.190.160.16": (47.6424, -122.13, "Microsoft"),
    "52.84.150.34": (47.6062, -122.3321, "AWS CloudFront"),
    "54.230.103.78": (35.6762, 139.6503, "AWS Tokyo"),
    "108.138.64.51": (35.6762, 139.6503, "AWS Tokyo"),
    "91.108.56.130": (52.5200, 13.4050, "Telegram"),
    "104.244.42.129": (37.7749, -122.4194, "X/Twitter"),
    "31.13.66.35": (37.4848, -122.1481, "Meta"),
    "142.250.72.14": (37.386, -122.0838, "Google"),
    "142.250.189.206": (37.386, -122.0838, "Google"),
    "151.101.1.69": (37.7749, -122.4194, "Fastly CDN"),
    # 国内服务
    "110.242.68.3": (39.9042, 116.4074, "百度"),
    "220.181.38.148": (39.9042, 116.4074, "百度"),
    "39.156.66.10": (39.9042, 116.4074, "百度"),
    "203.119.238.180": (39.9042, 116.4074, "北京联通"),
    "101.226.4.6": (31.2304, 121.4737, "上海电信"),
    "183.192.65.101": (31.2304, 121.4737, "上海移动"),
    "113.96.109.91": (22.5431, 114.0579, "深圳电信"),
    "14.215.177.38": (23.1291, 113.2644, "广州电信"),
    "101.89.178.14": (31.2304, 121.4737, "爱奇艺 CDN"),
    "118.26.32.158": (39.9042, 116.4074, "优酷 CDN"),
    "59.36.96.63": (22.5431, 114.0579, "腾讯"),
    "183.47.126.35": (22.5431, 114.0579, "腾讯"),
    "58.216.109.14": (32.0617, 118.7778, "网易"),
    "123.58.180.7": (30.2936, 120.1614, "网易"),
    "117.169.21.238": (30.2936, 120.1614, "阿里云"),
    "47.246.22.233": (30.2936, 120.1614, "阿里云"),
    "106.11.68.13": (30.2936, 120.1614, "阿里云"),
    "112.25.60.30": (31.2304, 121.4737, "B 站 CDN"),
    "119.3.238.64": (31.2304, 121.4737, "华为云"),
    "180.101.50.242": (32.0617, 118.7778, "南京电信"),
}

# 未命中内置表时的兜底区域（中国范围），哈希保持确定性
_FALLBACK_REGIONS: list[Coord] = [
    (39.9042, 116.4074),  # 北京
    (31.2304, 121.4737),  # 上海
    (22.5431, 114.0579),  # 深圳
    (23.1291, 113.2644),  # 广州
    (30.2936, 120.1614),  # 杭州
    (32.0617, 118.7778),  # 南京
    (30.5728, 104.0668),  # 成都
    (29.5630, 106.5516),  # 重庆
    (34.3416, 108.9398),  # 西安
    (30.5928, 114.3055),  # 武汉
]

# ---------------------------------------------------------------------------
# 在线 GeoIP 查询与缓存（多服务商容灾）
# ---------------------------------------------------------------------------
# 缓存结构: ip -> (lat, lng, label, timestamp)
_ip_geo_cache: dict[str, Tuple[float, float, str, float]] = {}
_cache_lock = threading.Lock()

# 单线程 executor，串行查询以遵守免费额度：
# ipwho.is ~10k 次/月、api.ip.sb 宽松；每次查询后间隔 1.1s 兜底限速
_lookup_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ipgeo")
_LOOKUP_MIN_INTERVAL = 1.1

_GEO_TIMEOUT = 5.0
_GEO_UA = "NetScope/1.0"


def _http_get_json(url: str, attempts: int = 2) -> Optional[dict]:
    """GET JSON，带瞬时故障重试（出口网络偶发 TLS 握手中断）。"""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _GEO_UA})
            with urllib.request.urlopen(req, timeout=_GEO_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            last_exc = exc
            if i + 1 < attempts:
                time.sleep(0.8)
    logger.debug("geo lookup failed: %s (%s)", url, last_exc)
    return None


def _label_from_parts(*parts: Optional[str]) -> str:
    return " ".join(p for p in parts if p)


def _fetch_ipwhois(ip: str) -> Tuple[float, float, str] | None:
    """ipwho.is：免费无 Key，返回 latitude/longitude。"""
    data = _http_get_json(f"https://ipwho.is/{ip}")
    if not data or not data.get("success") or data.get("latitude") is None:
        return None
    lat, lon = data.get("latitude"), data.get("longitude")
    label = _label_from_parts(
        data.get("country"), data.get("region"), data.get("city")
    )
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return float(lat), float(lon), label or ip


def _fetch_ipsb(ip: str) -> Tuple[float, float, str] | None:
    """api.ip.sb：备用源，返回 latitude/longitude。"""
    data = _http_get_json(f"https://api.ip.sb/geoip/{ip}")
    if not data or data.get("latitude") is None:
        return None
    lat, lon = data.get("latitude"), data.get("longitude")
    label = _label_from_parts(
        data.get("country"), data.get("region"), data.get("city")
    )
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return float(lat), float(lon), label or ip


_GEO_PROVIDERS = (_fetch_ipwhois, _fetch_ipsb)


def _fetch_geo(ip: str) -> Tuple[float, float, str] | None:
    for provider in _GEO_PROVIDERS:
        result = provider(ip)
        if result is not None:
            return result
    return None


def _fetch_and_cache(ip: str) -> None:
    """后台任务：多服务商查询并写入缓存。"""
    result = _fetch_geo(ip)
    if result:
        with _cache_lock:
            _ip_geo_cache[ip] = (*result, time.time())
    # 限速：每次查询间隔至少 1.1s
    time.sleep(_LOOKUP_MIN_INTERVAL)


def _schedule_lookup(ip: str) -> None:
    """将 IP 提交到后台查询队列。"""
    # 避免重复提交：若已在缓存或已知表，不提交
    ip = str(ip).strip()
    if ip in KNOWN_GEO:
        return
    with _cache_lock:
        if ip in _ip_geo_cache:
            return
    _lookup_executor.submit(_fetch_and_cache, ip)


def known_geo_label(ip: str) -> Optional[str]:
    """只查本地表 / 缓存，不触发网络请求。返回位置标签或 None。"""
    ip = str(ip).strip()
    known = KNOWN_GEO.get(ip)
    if known:
        return known[2]
    with _cache_lock:
        cached = _ip_geo_cache.get(ip)
    if cached:
        return cached[2]
    return None


def locate_public_ip(ip: str) -> Tuple[float, float, str]:
    """返回公网 IP 的 (lat, lng, label)。

    查找顺序：
    1. 内置静态表 KNOWN_GEO
    2. 内存缓存（ipwho.is / api.ip.sb 查询结果）
    3. 触发后台异步查询（立即返回兜底坐标，后续命中缓存返回真实坐标）
    4. 确定性哈希兜底（中国范围内，仅作渲染占位）
    """
    ip = str(ip).strip()

    # 1. 静态已知表
    known = KNOWN_GEO.get(ip)
    if known:
        return known

    # 2. 内存缓存
    with _cache_lock:
        cached = _ip_geo_cache.get(ip)
    if cached:
        return cached[:3]

    # 3. 触发后台查询（不阻塞）
    _schedule_lookup(ip)

    # 4. 兜底：确定性哈希落点
    digest = hashlib.md5(ip.encode("utf-8")).digest()
    base = _FALLBACK_REGIONS[digest[0] % len(_FALLBACK_REGIONS)]
    jitter_lat = ((digest[1] % 100) - 50) / 40.0
    jitter_lng = ((digest[2] % 100) - 50) / 40.0
    return base[0] + jitter_lat, base[1] + jitter_lng, ip


def prewarm_cache(ips: list[str]) -> None:
    """批量预热缓存：将一组 IP 提交到后台查询队列。"""
    for ip in ips:
        if is_public_ip(ip):
            _schedule_lookup(ip)


def get_cache_stats() -> dict[str, int]:
    """返回缓存统计（调试用）。"""
    with _cache_lock:
        return {
            "cached": len(_ip_geo_cache),
            "pending": _lookup_executor._work_queue.qsize() if hasattr(_lookup_executor, "_work_queue") else 0,
        }


# ---------------------------------------------------------------------------
# 内网设备环形布局
# ---------------------------------------------------------------------------
def internal_ring_position(index: int, center: Coord, radius_deg: float = 2.2) -> Coord:
    """内网设备围绕网关坐标的环形布局（经纬度小偏移），避免节点重叠。"""
    import math

    angle = (2 * math.pi * index) / max(1, 12) + math.pi / 8
    ring = 1 + (index // 12) * 0.55
    lat = center[0] + math.sin(angle) * radius_deg * ring
    lng = center[1] + math.cos(angle) * radius_deg * ring * 1.35
    return round(lat, 4), round(lng, 4)
