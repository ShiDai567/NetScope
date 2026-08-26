"""国家级 Geo 结果的确定性散布。

问题背景：GeoLite2 对大量中国 IP 仅精确到国家（坐标为国家中心点，
如 CN → 34.77,113.72），大量对端节点堆叠在同一像素，视觉上像
"旧服务器位置仍在收发数据"。

方案：对 city/region 均缺失的国家级结果，以 IP 哈希做确定性微扰
（±0.9° 内），同一 IP 每次得到同一位置，不同 IP 自然散开。
不伪造城市名——归属国家真实，散布仅为可读性，服务端 name 仍标注真实精度。
"""

import hashlib

_SPREAD_DEG = 0.9


def spread_factor(ip: str) -> tuple[float, float]:
    """IP → [-1,1)² 确定性散布因子。"""
    digest = hashlib.sha1(ip.encode()).digest()
    fx = int.from_bytes(digest[0:4], "big") / 0xFFFFFFFF  # [0,1]
    fy = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    return (fx * 2 - 1) * _SPREAD_DEG, (fy * 2 - 1) * _SPREAD_DEG


def apply_country_spread(ip: str, lat: float, lng: float) -> tuple[float, float]:
    """国家级坐标散布：city 与 region 均未知时调用。"""
    dx, dy = spread_factor(ip)
    return round(lat + dy, 6), round(lng + dx, 6)
