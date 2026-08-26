"""ip2region xdb Provider（中国 IP 城市/省级归属，v4 格式）。

文件格式（实测逆向验证）：
  header(256B): version(2) policy(2) created(4) start_index_ptr(4) end_index_ptr(4)
  vector_index(256×256×8): 每 cell = (start_ptr, end_ptr) 指向 index 段
  index entry(14B): start_ip(4) end_ip(4) data_len(2) data_ptr(4)
  data: "国家|区域|城市|ISP|国家码" UTF-8

区域字段为城市名（如"上海市"/"杭州市"），需经中国城市坐标表换算经纬度；
坐标表来自 lan/../city_coords.py（内置常用城市 + 省会兜底）。
"""

import struct
import threading

from core.geo.city_coords import city_coord
from core.geo.provider import GeoInfo, GeoProvider
from core.log import get_logger

log = get_logger("core.geo.ip2region")

_HEADER_LEN = 256
_VI_CELL = 8
_ENTRY_LEN = 14


class Ip2RegionProvider(GeoProvider):
    name = "ip2region"

    def __init__(self, xdb_path: str | None) -> None:
        self._buf = None
        if not xdb_path:
            return
        try:
            with open(xdb_path, "rb") as f:
                self._buf = f.read()
            self._start_ptr = struct.unpack_from("<I", self._buf, 8)[0]
            self._end_ptr = struct.unpack_from("<I", self._buf, 12)[0]
            log.info(
                "ip2region.loaded",
                path=xdb_path,
                size_mb=round(len(self._buf) / 1048576, 1),
            )
        except Exception as exc:
            self._buf = None
            log.warning("ip2region.load_failed", error=str(exc))
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self._buf is not None

    def lookup(self, ip: str) -> GeoInfo | None:
        if not self.available:
            return None
        try:
            parts = ip.split(".")
            if len(parts) != 4:
                return None
            ip_int = struct.unpack(">I", bytes(int(p) for p in parts))[0]
        except (ValueError, struct.error):
            return None

        with self._lock:
            raw = self._binary_search(ip_int)
        if raw is None:
            return None
        return self._parse_region(ip, raw)

    def _binary_search(self, ip_int: int) -> bytes | None:
        buf = self._buf
        il0 = (ip_int >> 24) & 0xFF
        il1 = (ip_int >> 16) & 0xFF
        cell = _HEADER_LEN + (il0 * 256 + il1) * _VI_CELL
        lo, hi = struct.unpack_from("<II", buf, cell)
        if not (self._start_ptr <= lo < hi <= self._end_ptr):
            return None
        while lo <= hi:
            mid = lo + ((hi - lo) // _ENTRY_LEN) * _ENTRY_LEN
            s_ip, e_ip = struct.unpack_from("<II", buf, mid)
            if ip_int < s_ip:
                hi = mid - _ENTRY_LEN
            elif ip_int > e_ip:
                lo = mid + _ENTRY_LEN
            else:
                data_len = struct.unpack_from("<H", buf, mid + 8)[0]
                data_ptr = struct.unpack_from("<I", buf, mid + 10)[0]
                return buf[data_ptr : data_ptr + data_len]
        return None

    def _parse_region(self, ip: str, raw: bytes) -> GeoInfo | None:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        fields = text.split("|")
        if len(fields) < 5:
            return None
        country, region, city, _isp, code = fields[0], fields[1], fields[2], fields[3], fields[4]
        region = region if region and region != "0" else ""
        city = city if city and city != "0" else ""
        # 只负责「有中国城市坐标」的结果；无坐标（国际 IP）返回 None
        # 交由链上的 MaxMind 兜底，避免截断 provider 链
        lat, lng = city_coord(city) or city_coord(region) or (None, None)
        if lat is None:
            return None
        return GeoInfo(
            country=country or "Unknown",
            code=code or None,
            region=region,
            city=city,
            lat=lat,
            lng=lng,
            source="ip2region",
        )
