"""GeoProvider 抽象与 GeoInfo 数据类型（doc §7）。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoInfo:
    country: str
    code: str | None
    region: str
    city: str
    lat: float | None
    lng: float | None
    source: str = "unknown"

    def location_text(self) -> str:
        """IP 归属地文本：国家·区域·城市（去空去重）。"""
        parts: list[str] = []
        for piece in (self.country, self.region, self.city):
            if piece and piece not in parts:
                parts.append(piece)
        return "·".join(parts)

    def as_dict(self) -> dict:
        return {
            "country": self.country,
            "code": self.code,
            "region": self.region,
            "city": self.city,
            "lat": self.lat,
            "lng": self.lng,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeoInfo":
        def _f(value) -> float | None:
            try:
                return float(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                return None

        return cls(
            country=str(data.get("country") or "Unknown"),
            code=data.get("code") or None,
            region=str(data.get("region") or ""),
            city=str(data.get("city") or ""),
            lat=_f(data.get("lat")),
            lng=_f(data.get("lng")),
            source=str(data.get("source") or "cache"),
        )


class GeoProvider:
    """定位提供者接口：lookup(ip) 返回 GeoInfo 或 None（未命中）。"""

    name = "base"

    def lookup(self, ip: str) -> GeoInfo | None:  # pragma: no cover - 接口
        raise NotImplementedError
