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
    def test_parse_hiofd_full_fields(self):
        """hiofd 源结果六字段 → GeoInfo（含 district/street/isp）。"""
        p = HiofdProvider()
        raw = "中国 · 上海 · 上海|121.472644|31.231706|电信|浦东|张江路"
        info = p._parse_text("1.2.3.4", f"hiofd|{raw}")  # noqa: SLF001
        assert info is not None
        assert info.country == "中国"
        assert info.region == "上海"
        assert info.city == "上海"
        assert info.lat == 31.231706
        assert info.lng == 121.472644
        assert info.isp == "电信"
        assert info.district == "浦东"
        assert info.street == "张江路"
        assert info.source == "hiofd"

    def test_parse_ipapi_fallback(self):
        """ip-api.com 降级源 JSON 解析。"""
        p = HiofdProvider()
        payload = (
            '{"status":"success","country":"加拿大","countryCode":"CA",'
            '"regionName":"Quebec","city":"蒙特利尔","district":"",'
            '"isp":"Videotron","lat":45.6085,"lon":-73.5493}'
        )
        info = p._parse_text("24.48.0.1", f"ipapi|{payload}")  # noqa: SLF001
        assert info is not None
        assert info.country == "加拿大"
        assert info.code == "CA"
        assert info.region == "Quebec"
        assert info.city == "蒙特利尔"
        assert info.isp == "Videotron"
        assert info.source == "ip-api"

    def test_parse_ipapi_failure_status(self):
        p = HiofdProvider()
        assert p._parse_text("1.1.1.1", 'ipapi|{"status":"fail"}') is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "ipapi|not-json") is None  # noqa: SLF001

    def test_parse_text_country_only(self):
        p = HiofdProvider()
        info = p._parse_text("1.1.1.1", "hiofd|澳大利亚|-27.468|153.028|||")  # noqa: SLF001
        assert info.country == "澳大利亚"
        assert info.city == ""
        assert info.isp == "" and info.district == "" and info.street == ""

    def test_parse_text_timeout_and_bad(self):
        p = HiofdProvider()
        assert p._parse_text("1.1.1.1", "") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "hiofd|TIMEOUT") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "hiofd|-|-|-") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "hiofd|中国|abc|def|电信|区|街") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "garbage") is None  # noqa: SLF001
        assert p._parse_text("1.1.1.1", "中国|121|31|电信") is None  # noqa: SLF001  # 无源前缀


class GeoInfoFieldsTests(DbTestCase):
    def test_db_roundtrip_keeps_district_isp_street(self):
        """DB 写回后再读，district/street/isp 不丢。"""
        from network.models import GeoLookup

        svc = GeoService(providers=[_provider_with(
            {"2.2.2.2": GeoInfo("中国", None, "浙江省", "温州市", 28.0, 120.6,
                                "hiofd", district="鹿城区", street="松台街道", isp="电信")}
        )])
        info = svc.lookup("2.2.2.2")
        assert info is not None
        row = GeoLookup.objects.get(ip_prefix="2.2.2.2")
        assert row.district == "鹿城区"
        assert row.street == "松台街道"
        assert row.isp == "电信"
        # 换实例纯 DB 读回，字段完整
        info2 = GeoService().lookup("2.2.2.2")
        assert info2.district == "鹿城区"
        assert info2.isp == "电信"
        assert info2.street == "松台街道"
