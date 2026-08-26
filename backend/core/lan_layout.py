"""LAN 场景伪坐标：设备围绕网关的确定性环形布局。

伪坐标仅用于地图投影展示，无任何地理含义（doc §7.3）。
"""

import math

from core.utils.network import ip_to_int

DEFAULT_CENTER = (32.0, 112.0)

_GOLDEN_ANGLE = math.radians(137.50776)
_RING_CAPACITY = 8
# 环半径以「LAN 视口尺度」设计：前端 LAN 场景 scale=15，视口宽≈360/15=24°。
# 基础环半径 1.35°（≈视口 11%），每 8 台设备外扩一环，最大三环覆盖约 5°。
_RING_BASE_DEG = 1.35


def ring_position(center: tuple[float, float] | None, index: int) -> tuple[float, float]:
    """第 index 个设备在 center 附近的确定性位置（黄金角散布，多环扩容）。

    center = (lat, lng)；返回 (lat, lng)。
    坐标为伪地理坐标，仅用于 LAN 场景地图投影展示，无地理含义（doc §7.3）。
    """
    cy, cx = center or DEFAULT_CENTER
    radius = _RING_BASE_DEG * (1 + index // _RING_CAPACITY)
    angle = index * _GOLDEN_ANGLE
    lat = cy + radius * math.cos(angle)
    lng = cx + radius * math.sin(angle) / max(math.cos(math.radians(cy)), 0.4)
    return round(lat, 6), round(lng, 6)


def assign_positions(devices: list[dict], center: tuple[float, float] | None) -> None:
    """就地写入 ring_index / lat / lng。网关居中（ring_index=-1），其余按 IP 排序。"""
    ordered = sorted(devices, key=lambda d: ip_to_int(d.get("ip")))
    seq = 0
    for dev in ordered:
        if dev.get("is_gateway"):
            dev["ring_index"] = -1
            dev["lat"], dev["lng"] = center or DEFAULT_CENTER
            continue
        dev["ring_index"] = seq
        dev["lat"], dev["lng"] = ring_position(center, seq)
        seq += 1
