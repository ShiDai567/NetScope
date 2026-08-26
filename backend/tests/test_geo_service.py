"""GeoService：缓存链路、私有 IP 短路、覆盖表。"""

from core.geo.manual_overrides import ManualOverrides
from core.geo.provider import GeoInfo
from core.geo.service import GeoService


class _FakeStore:
    def __init__(self):
        self.geo = {}

    def geo_get(self, ip):
        return self.geo.get(ip)

    def geo_set(self, ip, info, ttl):
        self.geo[ip] = info


def _provider_with(mapping):
    class P:
        name = "test"

        def lookup(self, ip):
            return mapping.get(ip)

    return P()


def test_private_ip_short_circuit():
    """私网 IP 永不查询（doc §23）。"""
    store = _FakeStore()
    calls = []

    class P:
        name = "test"

        def lookup(self, ip):
            calls.append(ip)
            return None

    svc = GeoService(store, [P()])
    assert svc.lookup("10.0.1.2") is None
    assert svc.lookup("192.168.1.1") is None
    assert svc.lookup("172.16.0.1") is None
    assert calls == []
    assert store.geo == {}


def test_provider_hit_cached_to_redis():
    store = _FakeStore()
    provider = _provider_with(
        {"8.8.8.8": GeoInfo("United States", "US", "CA", "Mountain View", 37.4, -122.1, "maxmind")}
    )
    svc = GeoService(store, [provider])
    info = svc.lookup("8.8.8.8")
    assert info is not None and info.lat == 37.4
    assert "8.8.8.8" in store.geo
    # 再查：命中 Redis 缓存（provider 不再是唯一来源）
    assert svc.lookup("8.8.8.8").country == "United States"


def test_miss_negative_cache_no_redis_write():
    store = _FakeStore()
    svc = GeoService(store, [_provider_with({})])
    assert svc.lookup("1.2.3.4") is None
    assert store.geo == {}


def test_manual_overrides_priority():
    store = _FakeStore()
    manual = ManualOverrides()
    manual.register({"8.8.8.8": {"country": "Custom", "lat": 1.0, "lng": 2.0}})
    fallback = _provider_with({"8.8.8.8": GeoInfo("United States", "US", "", "", 37.4, -122.1, "maxmind")})
    svc = GeoService(store, [manual, fallback])
    info = svc.lookup("8.8.8.8")
    assert info.country == "Custom" and info.source == "manual"


def test_location_text_dedup():
    """归属地文本：国家·区域·城市，去空去重。"""
    from core.geo.provider import GeoInfo

    assert GeoInfo("中国", "CN", "河南", "郑州", 34.7, 113.7).location_text() == "中国·河南·郑州"
    assert GeoInfo("中国", "CN", "", "", 34.7, 113.7).location_text() == "中国"
    # region 与 country 相同时去重
    assert GeoInfo("Singapore", "SG", "Singapore", "", 1.3, 103.8).location_text() == "Singapore"


def test_redis_cache_dict_roundtrip_types():
    """Redis hash 读回的字符串经 from_dict 归一为 float。"""
    store = _FakeStore()
    store.geo["9.9.9.9"] = {
        "country": "Germany",
        "lat": "51.5",
        "lng": "10.2",
        "code": "DE",
        "city": "",
        "region": "",
        "source": "cache",
    }
    svc = GeoService(store, [])
    info = svc.lookup("9.9.9.9")
    assert info.lat == 51.5 and info.lng == 10.2 and info.code == "DE"


def test_country_only_spread():
    """国家级精度坐标散布：不同 IP 围绕国家中心散开，同 IP 结果稳定。"""

    from core.geo.provider import GeoInfo
    from core.geo.service import GeoService

    class P:
        name = "test"

        def lookup(self, ip):
            return GeoInfo("中国", "CN", "", "", 34.7732, 113.722)

    store = _FakeStore()
    svc = GeoService(store, [P()])
    a1 = svc.lookup("101.227.131.211")
    a2 = svc.lookup("101.227.131.211")
    b = svc.lookup("218.71.58.104")
    c = svc.lookup("223.5.5.5")

    assert (a1.lat, a1.lng) == (a2.lat, a2.lng)  # 同 IP 稳定
    assert a1.lat != b.lat or a1.lng != b.lng  # 不同 IP 散开
    assert b.lat != c.lat or b.lng != c.lng
    # 散布幅度受限
    for info in (a1, b, c):
        assert abs(info.lat - 34.7732) <= 0.91
        assert abs(info.lng - 113.722) <= 0.91
    # 城市级精度不散布
    class PCity:
        name = "test"

        def lookup(self, ip):
            return GeoInfo("中国", "CN", "浙江", "杭州", 30.2, 120.1)

    svc2 = GeoService(_FakeStore(), [PCity()])
    d = svc2.lookup("1.2.3.4")
    assert (d.lat, d.lng) == (30.2, 120.1)
