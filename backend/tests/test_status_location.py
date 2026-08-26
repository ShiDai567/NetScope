"""SERVER_LOCATION 核心服务器定位测试。"""

import fakeredis
import pytest

from core.geo.provider import GeoInfo
from core.geo.service import GeoService
from core.redis_store import RedisStore
from network.services.status_service import StatusService


class _Store:
    def geo_get(self, ip):
        return None

    def geo_set(self, ip, info, ttl):
        pass


@pytest.fixture
def store():
    return RedisStore(client=fakeredis.FakeStrictRedis(decode_responses=True))


def _geo_with(mapping):
    class P:
        name = "test"

        def lookup(self, ip):
            return mapping.get(ip)

    return GeoService(_Store(), [P()])


def _svc(store, geo, lat=None, lng=None, location=None, on_geo_change=None):
    return StatusService(store, None, geo, server_lat=lat, server_lng=lng,
                         server_location=location, on_geo_change=on_geo_change)


def test_server_location_ip_direct(store):
    """SERVER_LOCATION 直接填公网 IP → GeoIP 定位。"""
    geo = _geo_with({"8.8.8.8": GeoInfo("美国", "US", "CA", "LA", 37.4, -122.1)})
    svc = _svc(store, geo, location="8.8.8.8")
    svc.update_gateway_from_wan("1.2.3.4")
    gw = store.get_gateway()
    assert gw["lat"] == 37.4 and gw["lng"] == -122.1
    assert gw["wan_ip"] == "8.8.8.8"


def test_server_location_domain_resolved(store, monkeypatch):
    """SERVER_LOCATION 填域名 → DNS 解析 → GeoIP 定位。"""
    geo = _geo_with({"60.1.2.3": GeoInfo("中国", "CN", "河南", "郑州", 34.7, 113.6)})
    monkeypatch.setattr(
        "network.services.status_service.socket.getaddrinfo",
        lambda host, *a, **kw: [(None, None, None, "", ("60.1.2.3", 0))],
    )
    svc = _svc(store, geo, location="mcsm.elsworld.cn")
    svc.update_gateway_from_wan("1.2.3.4")
    gw = store.get_gateway()
    assert gw["lat"] == 34.7 and gw["wan_ip"] == "60.1.2.3"


def test_priority_lat_lng_over_location(store):
    """SERVER_LAT/LNG 显式坐标优先于 SERVER_LOCATION。"""
    geo = _geo_with({"8.8.8.8": GeoInfo("美国", "US", "CA", "LA", 37.4, -122.1)})
    svc = _svc(store, geo, lat=31.2, lng=121.4, location="8.8.8.8")
    svc.update_gateway_from_wan(None)
    gw = store.get_gateway()
    assert gw["lat"] == 31.2 and gw["lng"] == 121.4


def test_fallback_to_wan_ip(store):
    """无 SERVER_LOCATION 时回退 WAN IP 定位。"""
    geo = _geo_with({"1.2.3.4": GeoInfo("中国", "CN", "浙江", "温州", 34.0, 113.0)})
    svc = _svc(store, geo)
    svc.update_gateway_from_wan("1.2.3.4")
    gw = store.get_gateway()
    assert gw["lat"] == 34.0 and gw["wan_ip"] == "1.2.3.4"


def test_private_ip_location_ignored(store):
    """私网 IP 作为 SERVER_LOCATION 无效 → 回退 WAN 定位。"""
    geo = _geo_with({"1.2.3.4": GeoInfo("中国", "CN", "浙江", "温州", 34.0, 113.0)})
    svc = _svc(store, geo, location="10.0.1.2")
    svc.update_gateway_from_wan("1.2.3.4")
    gw = store.get_gateway()
    assert gw["lat"] == 34.0 and gw["wan_ip"] == "1.2.3.4"


# ---------------------------------------------------------------- geo_epoch 联动


def test_geo_change_bumps_epoch_and_clears_packets(store):
    """核心位置变更：纪元递增 + 事件缓冲清空 + 回调触发。"""
    geo = _geo_with({"8.8.8.8": GeoInfo("美国", "US", "CA", "LA", 37.4, -122.1)})
    callbacks = []
    svc = _svc(store, geo, location="8.8.8.8", on_geo_change=lambda *a: callbacks.append(a))
    store.set_mode("ikuai")

    # 旧位置 + 旧事件
    store.set_gateway(31.2, 121.4, "old")
    store.publish_packets(
        [{"id": "old1", "seq": 100, "direction": "outbound"}], buffer_max=100
    )
    assert store.get_mode()["geo_epoch"] == 0

    svc.update_gateway_from_wan(None)
    gw = store.get_gateway()
    assert gw["lat"] == 37.4  # 新位置生效
    assert store.get_mode()["geo_epoch"] == 1
    events, _ = store.read_packets(None, 100)
    assert events == []  # 旧事件已清空
    assert callbacks and callbacks[0][2] == 1  # on_geo_change(lat, lng, epoch)


def test_same_location_no_epoch_bump(store):
    """位置未变化：不触发纪元（避免每轮 WAN 轮询都清数据）。"""
    geo = _geo_with({"1.2.3.4": GeoInfo("中国", "CN", "浙江", "温州", 34.0, 113.0)})
    svc = _svc(store, geo, location="1.2.3.4")
    store.set_mode("ikuai")
    svc.update_gateway_from_wan("1.2.3.4")
    assert store.get_mode()["geo_epoch"] == 0  # 初次定位不算变更

    store.publish_packets(
        [{"id": "p1", "seq": 1, "direction": "outbound"}], buffer_max=100
    )
    svc.update_gateway_from_wan("1.2.3.4")  # 同位置再来一轮
    assert store.get_mode()["geo_epoch"] == 0
    events, _ = store.read_packets(None, 100)
    assert len(events) == 1  # 事件未被误删
