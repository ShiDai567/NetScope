"""终端列表行 → 设备字典（doc §20.1 终端字段对照）。"""

from core.utils.network import valid_ip


def _s(value) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw in ("", "--", "null", "None"):
        return None
    return raw


def _n(value) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def adapt_terminal(row: dict, gateway_ip: str | None) -> dict | None:
    """monitor_lanip 终端行 → 设备基础字段（速率由 DeviceService 差分计算）。"""
    ip = valid_ip(row.get("ip_addr") or row.get("ip") or row.get("ip_addr_str"))
    if ip is None:
        return None
    return {
        "ip": ip,
        "mac": _s(row.get("mac")) or None,
        "hostname": _s(row.get("comment")) or None,
        "vendor": None,
        "interface": _s(row.get("interface")) or None,
        "is_gateway": ip == gateway_ip if gateway_ip else False,
        "connections": int(_n(row.get("connect_num"))),
        "up_rate": 0.0,
        "down_rate": 0.0,
        "upload_total": _n(row.get("upload")),
        "download_total": _n(row.get("download")),
        "ring_index": None,
        "lat": None,
        "lng": None,
    }
