"""iKuai conn 行 → 标准 Packet 的容错测试（doc §5.2、§61）。"""

import random

from network.adapters.direction import resolve_direction
from network.adapters.ikuaipacket import adapt_packet
from tests.conftest import LISTEN_PORTS

WAN_IP = "203.0.113.7"


def _adapt(row, terminal="10.0.1.2", **kw):
    resolved = resolve_direction(row, terminal, WAN_IP, LISTEN_PORTS)
    if resolved is None or resolved.direction == "external":
        return None
    params = dict(
        conn_key="a" * 24,
        seq=42,
        now=1787756000.0,
        born=1787755990.0,
        status=row.get("status") if isinstance(row.get("status"), str) else None,
        status_since=None,
        flag=None,
        app_name=row.get("app_name") if isinstance(row.get("app_name"), str) else None,
        protocol=row.get("protocol") or "",
        interface=row.get("interface") if isinstance(row.get("interface"), str) else None,
        total_up=row.get("total_up") or 0,
        total_down=row.get("total_down") or 0,
        domain=row.get("domain") if isinstance(row.get("domain"), str) else None,
        geo_src=None,
        geo_dst=None,
        lan_coords=None,
    )
    params.update(kw)
    return adapt_packet(resolved, **params)


def test_real_rows_never_raise(ikuai_rows):
    """真实样本（含脏行）逐条归一，永不抛异常。"""
    count = 0
    for row in ikuai_rows:
        pkt = _adapt(row)
        if pkt is not None:
            count += 1
            assert pkt["direction"] in ("outbound", "inbound", "internal")
            assert isinstance(pkt["seq"], int)
            assert pkt["protocol"] == pkt["protocol"].lower()
            assert pkt["total_up"] >= 0 and pkt["total_down"] >= 0
            for side in ("source", "destination"):
                endpoint = pkt[side]
                assert set(endpoint) >= {"ip", "port", "domain", "lat", "lng"}
    assert count > 0


def test_dirty_values_normalized():
    """'--'/空串/None → null；不崩溃。"""
    row = {
        "protocol": "TCP",
        "status": "--",
        "dst_addr": "114.114.114.114",
        "src_port": 5000,
        "dst_port": 53,
        "forward_addr": "10.0.1.2",
        "app_name": "",
        "interface": "",
        "total_up": "xx",
        "total_down": None,
        "domain": "--",
    }
    pkt = _adapt(row)
    assert pkt is not None
    assert pkt["status"] is None
    assert pkt["app_name"] == "未知应用"
    assert pkt["interface"] is None
    assert pkt["total_up"] == 0
    assert pkt["destination"]["domain"] is None
    assert pkt["protocol"] == "tcp"


def test_inbound_endpoint_swap_and_nat():
    row = {
        "protocol": "tcp",
        "status": "已连接",
        "dst_addr": "203.119.238.180",
        "src_port": 445,
        "dst_port": 57584,
        "forward_addr": "10.0.1.2",
        "app_name": "SMB",
        "interface": "wan1",
        "total_up": 100,
        "total_down": 4320,
        "domain": "--",
    }
    pkt = _adapt(row)
    assert pkt["direction"] == "inbound"
    assert pkt["source"]["ip"] == "203.119.238.180"
    assert pkt["source"]["port"] == 57584
    assert pkt["destination"]["ip"] == "10.0.1.2"
    assert pkt["destination"]["port"] == 445
    assert pkt["nat_info"]["forward_addr"] == "10.0.1.2"
    assert pkt["nat_info"]["src_port"] == 57584
    assert pkt["nat_info"]["dst_port"] == 445
    assert pkt["nat_info"]["original_dst"] == f"{WAN_IP}:445"


def test_outbound_nat_forward_addr():
    row = {
        "protocol": "udp",
        "status": None,
        "dst_addr": "114.114.114.114",
        "src_port": 60811,
        "dst_port": 53,
        "forward_addr": "192.168.2.100",
        "app_name": "DNS",
        "interface": "wan1",
        "total_up": 81,
        "total_down": 0,
        "domain": "--",
    }
    pkt = _adapt(row)
    assert pkt["direction"] == "outbound"
    assert pkt["source"]["ip"] == "192.168.2.100"
    assert pkt["destination"]["ip"] == "114.114.114.114"
    assert pkt["nat_info"]["forward_addr"] == "192.168.2.100"


def test_lan_coords_applied_to_private_endpoint():
    row = {
        "protocol": "udp",
        "status": "--",
        "dst_addr": "192.168.2.1",
        "src_port": 53112,
        "dst_port": 53,
        "forward_addr": "10.0.1.10",
        "app_name": "DNS",
        "interface": "lan1",
        "total_up": 80,
        "total_down": 200,
        "domain": "--",
    }
    pkt = _adapt(row, lan_coords={"10.0.1.10": (32.1, 112.1), "192.168.2.1": (32.2, 112.2)})
    assert pkt["direction"] == "internal"
    assert pkt["source"]["lat"] == 32.1
    assert pkt["destination"]["lat"] == 32.2


def test_geo_fields_propagated():
    row = {
        "protocol": "tcp",
        "status": "已连接",
        "dst_addr": "8.8.8.8",
        "src_port": 50000,
        "dst_port": 443,
        "forward_addr": "10.0.1.2",
        "app_name": "HTTPS",
        "interface": "wan1",
        "total_up": 1,
        "total_down": 2,
        "domain": "example.com",
    }
    pkt = _adapt(
        row,
        geo_dst={
            "country": "United States",
            "code": "US",
            "city": "Mountain View",
            "lat": 37.4,
            "lng": -122.1,
        },
    )
    assert pkt["destination"]["country"] == "United States"
    assert pkt["destination"]["code"] == "US"
    assert pkt["destination"]["lat"] == 37.4
    assert pkt["destination"]["domain"] == "example.com"


def test_fuzz_never_raises():
    """随机脏数据模糊测试：任何输入不允许抛异常。"""
    rng = random.Random(2026)
    junk_pool = [None, "", "--", "null", 0, -1, 1e9, "not-an-ip", [], {}, {"a": 1}, 3.14, "443"]
    for _ in range(300):
        row = {
            "protocol": rng.choice(junk_pool),
            "status": rng.choice(junk_pool),
            "dst_addr": rng.choice(junk_pool),
            "src_port": rng.choice(junk_pool),
            "dst_port": rng.choice(junk_pool),
            "forward_addr": rng.choice(junk_pool),
            "app_name": rng.choice(junk_pool),
            "interface": rng.choice(junk_pool),
            "total_up": rng.choice(junk_pool),
            "total_down": rng.choice(junk_pool),
            "domain": rng.choice(junk_pool),
        }
        _adapt(row)
