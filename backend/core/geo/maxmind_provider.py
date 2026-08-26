"""GeoLite2-City 提供者：数据库文件缺失/损坏时自动禁用（优雅降级）。"""

from core.geo.provider import GeoInfo, GeoProvider
from core.log import get_logger

log = get_logger("core.geo.maxmind")


class MaxMindProvider(GeoProvider):
    name = "maxmind"

    def __init__(self, db_path: str | None, locale: str = "zh-CN") -> None:
        self._reader = None
        self._disabled = False
        self._locale = locale
        if not db_path:
            self._disabled = True
            return
        try:
            import geoip2.database  # noqa: F401（延迟导入）
        except ImportError:  # pragma: no cover
            self._disabled = True
            log.warning("maxmind.geoip2_not_installed")
            return
        try:
            self._reader = geoip2.database.Reader(db_path, locales=[locale, "en"])
            log.info("maxmind.loaded", path=db_path, locale=locale)
        except Exception as exc:
            self._disabled = True
            log.warning("maxmind.load_failed", error=str(exc))

    @property
    def available(self) -> bool:
        return self._reader is not None and not self._disabled

    def lookup(self, ip: str) -> GeoInfo | None:
        if not self.available:
            return None
        try:
            rec = self._reader.city(ip)
        except Exception:
            return None
        lat = rec.location.latitude if rec.location else None
        lng = rec.location.longitude if rec.location else None
        if lat is None or lng is None:
            return None
        country = rec.country.name or "Unknown"
        code = rec.country.iso_code
        city = (rec.city.name if rec.city else None) or ""
        region = ""
        if rec.subdivisions:
            region = rec.subdivisions[0].name or ""
        return GeoInfo(
            country=country,
            code=code,
            region=region,
            city=city,
            lat=float(lat),
            lng=float(lng),
            source="maxmind",
        )
