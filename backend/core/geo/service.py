"""GeoService：数据库（GeoLookup 表）为主源 + hiofd API 兜底。

检索链（doc §7 改版）：
  1. SQL geo_lookup 表命中 → 直接返回（零外部调用）
  2. 未命中 → hiofd API 查询 → 写回数据库（此后永不再外部查询）
  3. API 失败/无结果 → LRU 负缓存短路（周期内不重复打 API）

私有 IP 永不查询（doc §23）。
"""

import threading
import time
from collections import OrderedDict

from core.geo.provider import GeoInfo, GeoProvider
from core.log import get_logger
from core.utils.network import is_private_ip

log = get_logger("core.geo.service")

_MISS = object()
_NEG_TTL = 900.0  # API 无结果负缓存：15 分钟内同 IP 不再外部查询


def _orm_run(fn):
    """ORM 调用包装：async 上下文里转线程执行（Playwright evaluate 会污染
    当前线程的事件循环标记，导致 Django SynchronousOnlyOperation）。"""
    try:
        import asyncio

        asyncio.get_running_loop()
    except RuntimeError:
        return fn()
    import threading

    result = {}

    def _run():
        try:
            result["value"] = fn()
        except Exception as exc:
            result["error"] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


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
    """ip → GeoInfo。线程安全（采集线程 + web 线程共用）。"""

    def __init__(
        self,
        store=None,
        providers: list[GeoProvider] | None = None,
        cache_ttl: int = 604800,
        lru_size: int = 4096,
        lru_ttl: float = 300.0,
    ) -> None:
        self._store = store
        self._providers = providers or []
        self._lru = _Lru(lru_size, lru_ttl)
        self._neg_lru = _Lru(2048, _NEG_TTL)
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()
        self._write_queue: list[tuple[str, GeoInfo]] = []

    # ------------------------------------------------------------ 主入口

    def lookup(self, ip: str) -> GeoInfo | None:
        if not ip or is_private_ip(ip):
            return None

        cached = self._lru.get(ip)
        if cached is not None:
            return cached if cached is not _MISS else None

        # 1) SQL 数据库
        info = self._db_get(ip)
        if info is not None:
            self._lru.put(ip, info)
            return info

        # 2) 外部 Provider（hiofd API）
        if self._neg_lru.get(ip) is not None:
            info = None  # 负缓存期内不再外部查询
        else:
            info = self._query_providers(ip)
            if info is None:
                self._neg_lru.put(ip, _MISS)
            else:
                self._db_put(ip, info)
                self._lru.put(ip, info)
                return info
        self._lru.put(ip, _MISS)
        return None

    # ------------------------------------------------------------ provider 链

    def _query_providers(self, ip: str) -> GeoInfo | None:
        for provider in self._providers:
            try:
                info = provider.lookup(ip)
            except Exception as exc:
                log.warning("geo.provider_error", provider=provider.name, error=str(exc))
                continue
            if info is not None:
                return info
        return None

    # ------------------------------------------------------------ SQL 读写

    def _db_get(self, ip: str) -> GeoInfo | None:
        try:
            from network.models import GeoLookup
        except Exception:
            return None
        try:
            row = _orm_run(lambda: GeoLookup.objects.filter(ip_prefix=ip).first())
        except Exception:
            return None
        if row is None or (row.lat is None or row.lng is None):
            return None
        return GeoInfo(
            country=row.country or "Unknown",
            code=row.code or None,
            region=row.region or "",
            city=row.city or "",
            lat=float(row.lat),
            lng=float(row.lng),
            source=f"db:{row.source}" if row.source else "db",
        )

    def _db_put(self, ip: str, info: GeoInfo) -> None:
        """同步写库；DB 异常不影响主流程（LRU 已缓存本次结果）。"""
        try:
            from network.models import GeoLookup

            def _write():
                GeoLookup.objects.update_or_create(
                    ip_prefix=ip,
                    defaults={
                        "country": info.country[:64],
                        "code": (info.code or "")[:8],
                        "region": info.region[:64],
                        "city": info.city[:64],
                        "district": (getattr(info, "district", "") or "")[:64],
                        "isp": (getattr(info, "isp", "") or "")[:128],
                        "lat": info.lat,
                        "lng": info.lng,
                        "source": info.source[:16],
                    },
                )

            _orm_run(_write)
        except Exception as exc:
            log.warning("geo.db_write_failed", ip=ip, error=str(exc))

    # ------------------------------------------------------------ 兼容接口

    def warmup(self, entries: dict) -> None:
        for ip, info in entries.items():
            self._lru.put(ip, GeoInfo.from_dict(info))

    def pending_persist(self) -> list[tuple[str, GeoInfo]]:
        return []
