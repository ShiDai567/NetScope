"""iKuai conn 行 → 标准 Packet（doc §5.2，前端 adaptPacket 的直接输入）。

字段级容错：任何脏值不抛异常，归一失败返回 None 由调用方丢弃计数。
"""

from network.adapters.direction import Resolved


def _s(value) -> str | None:
    """字符串清洗："--" / "" / "null" / None → None。"""
    if value is None:
        return None
    raw = str(value).strip()
    if raw in ("", "--", "null", "None"):
        return None
    return raw


def _n(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        if raw in ("", "--"):
            return None
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _proto(value) -> str:
    raw = _s(value)
    if raw is None:
        return "unknown"
    return raw.lower()


def _count(value) -> float:
    """字节数清洗：脏值归零，负数归零。"""
    num = _n(value)
    if num is None or num < 0:
        return 0.0
    return num


def adapt_packet(
    resolved: Resolved,
    *,
    conn_key: str,
    seq: int,
    now: float,
    born: float,
    status: str | None,
    status_since: float | None,
    flag: str | None,
    app_name: str | None,
    protocol: str,
    interface: str | None,
    total_up: float,
    total_down: float,
    domain: str | None,
    geo_src: dict | None,
    geo_dst: dict | None,
    lan_coords: dict[str, tuple[float, float]] | None = None,
) -> dict:
    """组装 §5.2 契约的标准 Packet dict。

    端点坐标规则：
      - 公网端：GeoService 结果（可 None）
      - 私网端：lan_coords 提供的伪坐标（可 None）
    """
    lan_coords = lan_coords or {}
    domain = _s(domain)

    def _endpoint(ip: str, port: int, is_local: bool) -> dict:
        geo = (geo_src if is_local else geo_dst) or {}
        lat = geo.get("lat")
        lng = geo.get("lng")
        if ip in lan_coords:
            lat, lng = lan_coords[ip]
        return {
            "ip": ip,
            "port": port,
            "domain": domain if is_local is False else None,
            "country": geo.get("country"),
            "city": geo.get("city"),
            "code": geo.get("code"),
            "lat": lat,
            "lng": lng,
        }

    if resolved.direction == "inbound":
        source = _endpoint(resolved.remote_ip, resolved.remote_port, is_local=False)
        destination = _endpoint(resolved.local_ip, resolved.local_port, is_local=True)
        nat_forward = resolved.local_ip
        nat_src_port = resolved.remote_port
        nat_dst_port = resolved.local_port
        nat_present = True
    else:
        source = _endpoint(resolved.local_ip, resolved.local_port, is_local=True)
        destination = _endpoint(resolved.remote_ip, resolved.remote_port, is_local=False)
        nat_forward = resolved.nat_forward_addr
        nat_src_port = resolved.local_port
        nat_dst_port = resolved.remote_port
        nat_present = nat_forward is not None

    nat_info = None
    if nat_present or resolved.original_dst:
        nat_info = {
            "forward_addr": nat_forward,
            "src_port": nat_src_port if nat_present else None,
            "dst_port": nat_dst_port if nat_present else None,
            "original_dst": resolved.original_dst,
        }

    upload = _count(total_up)
    download = _count(total_down)

    return {
        "id": f"{conn_key[:12]}-{seq}",
        "seq": seq,
        "timestamp": round(now, 3),
        "born": round(born, 3),
        "direction": resolved.direction,
        "app_name": app_name or "未知应用",
        "protocol": _proto(protocol),
        "status": _s(status),
        "source": source,
        "destination": destination,
        "nat_info": nat_info,
        "total_up": int(upload),
        "total_down": int(download),
        "interface": _s(interface),
        "flag": flag,
        "latency_ms": None,
        "status_since": round(status_since, 3) if status_since is not None else None,
    }
