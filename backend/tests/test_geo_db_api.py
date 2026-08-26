"""GeoService（DB 主源 + hiofd API 兜底）与 HiofdProvider 测试。"""

from django.test import TestCase as DbTestCase

from core.geo.hiofd_provider import HiofdProvider
from core.geo.manual_overrides import ManualOverrides
from core.geo.provider import GeoInfo
from core.geo.service import GeoService


class _FakeStore:
    """旧 Redis store 接口占位（新 GeoService 不再依赖）。"""


def _provider_with(mapping):
    class P:
        name = "fake"

        def lookup(self, ip):
            return mapping.get(ip)

    return P()


# ---------------------------------------------------------------- 私网短路


def test_private_ip_short_circuit():
    svc = GeoService()
    assert svc.lookup("10.0.1.2") is None
    assert svc.lookup("192.168.1.1") is None
    assert svc.lookup("not-an-ip") is None


# ---------------------------------------------------------------- DB 主源（需数据库）


class DbGeoTests(DbTestCase):
    def test_db_hit_no_provider_call(self):
        """DB 命中 → 直接返回，不触发外部 provider。"""
        from network.models import GeoLookup

        GeoLookup.objects.create(
            ip_prefix="1.2.3.4", country="中国", region="浙江省",
            city="温州市", lat=28.0, lng=120.6, source="hiofd",
        )
        calls = []

        class P:
            name = "spy"

            def lookup(self, ip):
                calls.append(ip)
                return None

        svc = GeoService(providers=[P()])
        info = svc.lookup("1.2.3.4")
        assert info is not None
        assert info.city == "温州市"
        assert info.lat == 28.0
        assert calls == []  # 未触发外部查询

    def test_db_miss_then_provider_writeback(self):
        """DB 未命中 → provider 查询 → 写回 DB（二次查询走 DB）。"""
        from network.models import GeoLookup

        svc = GeoService(providers=[_provider_with(
            {"8.8.8.8": GeoInfo("美国", "US", "California", "Mountain View", 37.4, -122.1, "hiofd")}
        )])
        assert GeoLookup.objects.filter(ip_prefix="8.8.8.8").count() == 0

        info = svc.lookup("8.8.8.8")
        assert info is not None and info.city == "Mountain View"

        row = GeoLookup.objects.get(ip_prefix="8.8.8.8")
        assert row.country == "美国"
        assert row.lat == 37.4
        assert row.source == "hiofd"

        # 换一个实例（LRU 不在）：纯 DB 命中
        svc2 = GeoService(providers=[_provider_with({})])
        again = svc2.lookup("8.8.8.8")
        assert again is not None
        assert again.city == "Mountain View"

    def test_provider_miss_negative_cache(self):
        """API 无结果 → 负缓存，短期不重复外部查询。"""
        calls = []

        class P:
            name = "spy"

            def lookup(self, ip):
                calls.append(ip)
                return None

        svc = GeoService(providers=[P()])
        assert svc.lookup("5.6.7.8") is None
        assert svc.lookup("5.6.7.8") is None
        assert calls == ["5.6.7.8"]  # 只查了一次

    def test_manual_overrides_priority(self):
        from network.models import GeoLookup

        GeoLookup.objects.create(
            ip_prefix="9.9.9.9", country="DB值", city="X", lat=1.0, lng=2.0, source="hiofd",
        )
        # DB 优先于 manual（DB 是主源，手工覆盖仅对未入库 IP 生效）
        manual = ManualOverrides()
        manual.register({"9.9.9.9": {"country": "Manual值", "lat": 3.0, "lng": 4.0}})
        svc = GeoService(providers=[manual])
        info = svc.lookup("9.9.9.9")
        assert info.country == "DB值"


# ---------------------------------------------------------------- HiofdProvider（文本协议解析）


class TestHiofdProvider:
    def test_parse_text_success(self):
        """页面结果文本 '中国 · 上海 · 上海|121.472644|31.231706' → GeoInfo。"""
        p = HiofdProvider()
        info = p._parse_text("1.2.3.4", "中国 · 上海 · 上海|121.472644|31.231706")  # noqa: SLF001
        assert info is not None
        assert info.country == "中国"
        assert info.region == "上海"
        assert info.city == "上海"
        assert info.lat == 31.231706
        assert info.lng == 121.472644
        assert info.source == "hiofd"

    def test_parse_text_country_only(self):
        p = HiofdProvider()
        info = p._parse_text("1.1.1.1", "澳大利亚|-27.468|153.028")  # noqa: SLF001
        assert info.country == "澳大利亚"
        assert info.city == ""

    def test_parse_text_timeout_and_bad(self):
        p = HiofdProvider()
        assert p._parse_text("1.1.1.1", "TIMEOUT") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "NO_DOM") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "-|-|-") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "中国|abc|def") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "garbage") is None  # noqa: SLF001
