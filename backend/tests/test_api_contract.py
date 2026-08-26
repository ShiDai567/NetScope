"""API 契约测试：响应结构必须与前端 client.ts 逐字段对齐（doc §10.2）。"""

import pytest
from rest_framework.test import APIClient

from core.redis_store import RedisStore, set_store

_NO_THROTTLE = {
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}


@pytest.fixture
def fake_store():
    import fakeredis

    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = RedisStore(client=client)
    set_store(store)
    yield store
    set_store(None)


@pytest.fixture
def api_client(fake_store):
    client = APIClient()
    return client


def _seed_packets(fake_store, count=3):
    packets = []
    for i in range(1, count + 1):
        packets.append(
            {
                "id": f"pkt{i}",
                "seq": i,
                "timestamp": 1787756000.0 + i,
                "born": 1787756000.0,
                "direction": "outbound",
                "app_name": "DNS",
                "protocol": "udp",
                "status": "已连接",
                "source": {"ip": "10.0.1.2", "port": 5000, "domain": None, "lat": None, "lng": None},
                "destination": {"ip": "8.8.8.8", "port": 53, "domain": None, "lat": 37.4, "lng": -122.1},
                "nat_info": None,
                "total_up": 100,
                "total_down": 200,
                "interface": "wan1",
                "flag": None,
                "latency_ms": None,
                "status_since": None,
            }
        )
    fake_store.publish_packets(packets, buffer_max=100)
    return packets


def test_health(api_client, fake_store):
    fake_store.heartbeat()
    resp = api_client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"status", "redis", "db", "collector_age_s"}


def test_mode_contract(api_client, fake_store):
    fake_store.set_mode("ikuai")
    fake_store.set_gateway(31.2, 121.4, "1.2.3.4")
    fake_store.set_ikuai_health(
        router_url="http://10.1.1.1", error=None, connected_at=100.0, last_poll_at=200.0
    )
    resp = api_client.get("/api/mode")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"mode", "uptime", "geo_epoch", "gateway", "ikuai"}
    assert body["mode"] == "ikuai"
    assert isinstance(body["geo_epoch"], int)
    assert set(body["gateway"]) == {"lat", "lng"}
    assert set(body["ikuai"]) == {"router_url", "error", "last_poll_at", "connected_at"}


def test_packets_contract(api_client, fake_store):
    _seed_packets(fake_store, 3)
    resp = api_client.get("/api/packets?since=1&limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"server_time", "last_seq", "events"}
    assert body["last_seq"] == 3
    assert [e["seq"] for e in body["events"]] == [2, 3]
    event = body["events"][0]
    for field in (
        "id",
        "seq",
        "timestamp",
        "born",
        "direction",
        "app_name",
        "protocol",
        "status",
        "source",
        "destination",
        "nat_info",
        "total_up",
        "total_down",
        "interface",
        "flag",
        "latency_ms",
        "status_since",
    ):
        assert field in event, f"缺少契约字段 {field}"
    for side in ("source", "destination"):
        assert set(event[side]) >= {"ip", "port", "domain", "lat", "lng"}


def test_packets_since_none_returns_first_page(api_client, fake_store):
    _seed_packets(fake_store, 5)
    resp = api_client.get("/api/packets")
    body = resp.json()
    assert body["last_seq"] == 5
    assert len(body["events"]) == 5


def test_packets_bad_since(api_client, fake_store):
    resp = api_client.get("/api/packets?since=abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


def test_stats_contract(api_client, fake_store):
    fake_store.set_mode("ikuai")
    snapshot = {
        "total": 10,
        "active": 3,
        "closed": 7,
        "failed": 1,
        "lost": 0,
        "directions": {"outbound": 8, "inbound": 1, "internal": 1},
        "protocols": {"tcp": 9, "udp": 1},
        "apps": [{"name": "DNS", "count": 5}],
        "bandwidth": {"up_bps": 1.0, "down_bps": 2.0, "series": [[100, 1, 2]]},
        "loss_rate": 0.0,
        "avg_latency_ms": 0.0,
        "system": {"cpu_percent": 10.0, "memory_percent": 50.0},
        "latency_heatmap": {"x": [], "y": [], "data": []},
        "mode": "ikuai",
        "uptime": 100,
        "window": 300,
    }
    fake_store.set_stats(300, snapshot)
    resp = api_client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "total",
        "active",
        "closed",
        "failed",
        "lost",
        "directions",
        "protocols",
        "apps",
        "bandwidth",
        "loss_rate",
        "avg_latency_ms",
        "system",
        "latency_heatmap",
        "mode",
        "uptime",
        "window",
    ):
        assert field in body, f"stats 缺少 {field}"
    assert set(body["directions"]) == {"outbound", "inbound", "internal"}
    assert body["apps"][0]["name"] == "DNS"


def test_stats_invalid_window_falls_back(api_client, fake_store):
    fake_store.set_mode("ikuai")
    resp = api_client.get("/api/stats?window=999999")
    assert resp.status_code == 200
    assert resp.json()["window"] == 300


def test_devices_contract(api_client, fake_store):
    fake_store.put_devices(
        [
            {
                "ip": "10.0.1.2",
                "mac": "aa",
                "hostname": "h",
                "vendor": None,
                "interface": "lan1",
                "is_gateway": False,
                "ring_index": 0,
                "lat": 32.0,
                "lng": 112.0,
                "connections": 5,
                "up_rate": 1.0,
                "down_rate": 2.0,
            }
        ]
    )
    resp = api_client.get("/api/devices")
    body = resp.json()
    assert set(body) == {"devices"}
    dev = body["devices"][0]
    for field in (
        "ip",
        "mac",
        "hostname",
        "vendor",
        "interface",
        "is_gateway",
        "ring_index",
        "lat",
        "lng",
        "connections",
        "up_rate",
        "down_rate",
    ):
        assert field in dev


def test_nodes_contract(api_client, fake_store):
    fake_store.put_nodes(
        [
            {
                "ip": "8.8.8.8",
                "name": "dns",
                "domain": "dns.google",
                "lat": 37.4,
                "lng": -122.1,
                "type": "server",
            }
        ]
    )
    resp = api_client.get("/api/nodes")
    body = resp.json()
    assert set(body) == {"nodes"}
    node = body["nodes"][0]
    for field in ("ip", "name", "domain", "lat", "lng", "type"):
        assert field in node
    assert isinstance(node["lat"], float)


def test_ranking_endpoint(api_client, fake_store):
    from core.utils.timeutil import now_ts

    ops = [
        ("protocols", 5, int(now_ts()) // 5 * 5, "tcp", 10, 1000),
        ("protocols", 5, int(now_ts()) // 5 * 5, "udp", 5, 500),
    ]
    fake_store.flush_counter_ops(ops)
    resp = api_client.get("/api/network/protocols?window=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"][0]["key"] == "tcp"
    assert body["items"][0]["count"] == 10
    assert body["items"][0]["bytes"] == 1000


def test_404_error_envelope(api_client, fake_store):
    resp = api_client.get("/api/not-exist")
    assert resp.status_code == 404
    assert "error" in resp.json()
