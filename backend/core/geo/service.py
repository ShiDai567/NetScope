"""GeoService：缓存编排（进程 LRU → Redis TTL → 手工覆盖/MaxMind）。

私有 IP 短路返回 None（doc §7.2 / §23），绝不进入公网定位。
"""

import threading
import time
from collections import OrderedDict

from core.geo.provider import GeoInfo, GeoProvider
from core.geo.spread import apply_country_spread
from core.log import get_logger
from core.utils.network import is_private_ip

log = get_logger("core.geo.service")

_MISS = object()


class _Lru:
    def __init__(self, size: int, ttl: float) -> None:
        self._size = size
        self._ttl = ttl
        self._data: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def get(self, key: str):
        item = self._data.get(key)
        if item is None:
            return None
        ts, value = item
        if time.monotonic() - ts > self._ttl:
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        if len(self._data) > self._size:
            self._data.popitem(last=False)


class GeoService:
    """ip → GeoInfo。线程安全（采集线程 + web 线程共用）。

    国家级精度（无城市/区域）的坐标做确定性散布，避免对端节点
    全部堆叠在国家中心点。
    """

    def __init__(
        self,
        store,
        providers: list[GeoProvider],
        cache_ttl: int = 604800,
        lru_size: int = 4096,
        lru_ttl: float = 300.0,
    ) -> None:
        self._store = store
        self._providers = providers
        self._lru = _Lru(lru_size, lru_ttl)
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()

    def _spread_if_country_only(self, ip: str, info: GeoInfo) -> GeoInfo:
        if info.lat is None or info.lng is None:
            return info
        if info.city or info.region:
            return info
        lat, lng = apply_country_spread(ip, info.lat, info.lng)
        return GeoInfo(
            country=info.country,
            code=info.code,
            region=info.region,
            city=info.city,
            lat=lat,
            lng=lng,
            source=info.source,
        )

    def lookup(self, ip: str) -> GeoInfo | None:
        if not ip or is_private_ip(ip):
            return None

        cached = self._lru.get(ip)
        if cached is not None:
            return cached if cached is not _MISS else None

        info = None
        try:
            raw = self._store.geo_get(ip)
        except Exception:
            raw = None
        if raw:
            info = GeoInfo.from_dict(raw)
            self._lru.put(ip, info)
            return info

        for provider in self._providers:
            try:
                info = provider.lookup(ip)
            except Exception as exc:
                log.warning("geo.provider_error", provider=provider.name, error=str(exc))
                continue
            if info is not None:
                break
        if info is not None:
            info = self._spread_if_country_only(ip, info)
            self._lru.put(ip, info)
            try:
                self._store.geo_set(ip, info.as_dict(), self._cache_ttl)
            except Exception:
                pass
        else:
            self._lru.put(ip, _MISS)
        return info

    def warmup(self, entries: dict) -> None:
        """启动时从持久表预载（network_geolookup），减少冷启动回源。"""
        for ip, info in entries.items():
            self._lru.put(ip, GeoInfo.from_dict(info))

    def pending_persist(self) -> list[tuple[str, GeoInfo]]:
        """返回本次新查到需落库的条目（由调用方清空缓存桶后批量写）。"""
        items = []
        for ip, (_, value) in list(self._lru._data.items()):  # noqa: SLF001
            if isinstance(value, GeoInfo) and value.source in ("maxmind", "manual"):
                items.append((ip, value))
        return items
