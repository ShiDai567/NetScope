"""方向判定黄金用例（doc §6.3）。"""

from network.adapters.direction import resolve_direction
from tests.conftest import LISTEN_PORTS

WAN_IP = "203.0.113.7"


def test_d1_internal():
    row = {
        "dst_addr": "192.168.2.1",
        "src_port": 53112,
        "dst_port": 53,
        "forward_addr": "10.0.1.10",
        "protocol": "udp",
    }
    r = resolve_direction(row, "10.0.1.10", WAN_IP, LISTEN_PORTS)
    assert r.direction == "internal"
    assert r.local_ip == "10.0.1.10"
    assert r.remote_ip == "192.168.2.1"


def test_d2_outbound():
    row = {
        "dst_addr": "114.114.114.114",
        "src_port": 60811,
        "dst_port": 53,
        "forward_addr": "192.168.2.100",
        "protocol": "udp",
    }
    r = resolve_direction(row, "10.0.1.2", WAN_IP, LISTEN_PORTS)
    assert r.direction == "outbound"
    assert r.local_ip == "192.168.2.100"
    assert r.remote_ip == "114.114.114.114"
    assert r.original_dst is None


def test_d3_inbound_listen_port():
    """本地端口命中 LISTEN_PORTS → inbound + original_dst。"""
    row = {
        "dst_addr": "203.119.238.180",
        "src_port": 445,
        "dst_port": 57584,
        "forward_addr": "10.0.1.2",
        "protocol": "tcp",
    }
    r = resolve_direction(row, "10.0.1.2", WAN_IP, LISTEN_PORTS)
    assert r.direction == "inbound"
    assert r.original_dst == f"{WAN_IP}:445"


def test_d3_requires_wan_ip_for_original_dst():
    row = {
        "dst_addr": "203.119.238.180",
        "src_port": 443,
        "dst_port": 50000,
        "forward_addr": "10.0.1.2",
        "protocol": "tcp",
    }
    r = resolve_direction(row, "10.0.1.2", None, LISTEN_PORTS)
    assert r.direction == "inbound"
    assert r.original_dst is None


def test_d4_external_dropped():
    """forward_addr 与 terminal 均为公网（罕见透传）→ external。

    注意：203.0.113.x/192.0.2.x 属文档保留段，ipaddress 会判为保留（私网语义），
    故此处使用真实公网段地址验证 D4。
    """
    row = {
        "dst_addr": "8.8.8.8",
        "src_port": 5000,
        "dst_port": 53,
        "forward_addr": "1.1.1.1",
        "protocol": "udp",
    }
    r = resolve_direction(row, "60.1.2.3", None, LISTEN_PORTS)
    assert r.direction == "external"


def test_d5_invalid_ip():
    row = {
        "dst_addr": "not-an-ip",
        "src_port": 1234,
        "dst_port": 80,
        "forward_addr": "10.0.1.2",
        "protocol": "tcp",
    }
    assert resolve_direction(row, "10.0.1.2", WAN_IP, LISTEN_PORTS) is None


def test_d5_invalid_port():
    row = {
        "dst_addr": "8.8.8.8",
        "src_port": "abc",
        "dst_port": 80,
        "forward_addr": "10.0.1.2",
        "protocol": "tcp",
    }
    assert resolve_direction(row, "10.0.1.2", WAN_IP, LISTEN_PORTS) is None


def test_forward_addr_public_falls_back_to_terminal():
    """forward_addr 为公网时不作为本地端，回退到 terminal_ip。"""
    row = {
        "dst_addr": "8.8.8.8",
        "src_port": 40000,
        "dst_port": 53,
        "forward_addr": "1.1.1.1",
        "protocol": "udp",
    }
    # terminal 公网 & remote 公网 → external（forward_addr 公网被忽略）
    r = resolve_direction(row, "60.1.2.3", None, LISTEN_PORTS)
    assert r.direction == "external"


def test_listen_port_miss_is_outbound():
    """本地端口不在 LISTEN_PORTS 的公网连接 → outbound。"""
    row = {
        "dst_addr": "162.159.61.8",
        "src_port": 40786,
        "dst_port": 443,
        "forward_addr": "10.0.1.2",
        "protocol": "tcp",
    }
    r = resolve_direction(row, "10.0.1.2", WAN_IP, LISTEN_PORTS)
    assert r.direction == "outbound"


def test_no_forward_addr_uses_terminal():
    row = {"dst_addr": "1.2.3.4", "src_port": 50000, "dst_port": 443, "forward_addr": "--", "protocol": "tcp"}
    r = resolve_direction(row, "10.0.1.9", WAN_IP, LISTEN_PORTS)
    assert r.direction == "outbound"
    assert r.local_ip == "10.0.1.9"
