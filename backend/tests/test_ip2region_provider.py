"""ip2region Provider 测试（依赖 data/ip2region_v4.xdb 数据文件）。"""

from pathlib import Path

import pytest

from core.geo.ip2region_provider import Ip2RegionProvider

XDB = Path(__file__).parent.parent / "data" / "ip2region_v4.xdb"

pytestmark = pytest.mark.skipif(not XDB.exists(), reason="缺少 ip2region 数据文件")


@pytest.fixture(scope="module")
def provider():
    return Ip2RegionProvider(str(XDB))


def test_china_ip_city_level(provider):
    """中国 IP → 城市/省级归属 + 坐标。"""
    info = provider.lookup("218.71.58.104")  # 温州电信
    assert info is not None
    assert info.country == "中国"
    assert info.city in ("温州市", "温州")
    assert abs(info.lat - 28.0) < 0.6
    assert abs(info.lng - 120.6) < 0.6
    assert info.source == "ip2region"


def test_shanghai_tencent(provider):
    """之前堆在国家中心的微信 IP → 上海市。"""
    info = provider.lookup("101.227.131.211")
    assert info is not None
    assert info.city == "上海市"
    assert abs(info.lat - 31.23) < 0.5


def test_international_returns_none_for_fallback(provider):
    """国际 IP 无中国坐标 → None（交给 MaxMind 兜底，不截断链）。"""
    assert provider.lookup("8.8.8.8") is None


def test_invalid_ip(provider):
    assert provider.lookup("not-an-ip") is None
    assert provider.lookup("") is None
    assert provider.lookup("999.1.1.1") is None


def test_provider_chain_with_ip2region_first():
    """装配顺序：ip2region 命中中国，MaxMind 只处理国际。"""
    from core.geo.service import GeoService

    class _Store:
        def geo_get(self, ip):
            return None

        def geo_set(self, ip, info, ttl):
            pass

    class FakeIntl:
        name = "fake-intl"

        def lookup(self, ip):
            # 只给国际 IP 提供结果
            if ip == "8.8.8.8":
                from core.geo.provider import GeoInfo

                return GeoInfo("United States", "US", "CA", "", 37.4, -122.1, "fake")
            return None

    svc = GeoService(_Store(), [Ip2RegionProvider(str(XDB)), FakeIntl()])
    cn = svc.lookup("101.227.131.211")
    assert cn.city == "上海市"
    intl = svc.lookup("8.8.8.8")
    assert intl.country == "United States"
