"""连接服务：生命周期（new/update/closed）与差分速率。"""

import time

from core.geo.service import GeoService
from network.services.connection_service import ConnectionService
from tests.conftest import LISTEN_PORTS


class _FakeStore:
    def __init__(self):
        self.conns = {}
        self.packets = []

    def upsert_conn(self, key, mapping, ts):
        self.conns[key] = mapping

    def drop_conns(self, keys):
        for k in keys:
            self.conns.pop(k, None)

    def touch_conns(self, keys, ts):
        pass

    def count_conns(self):
        return len(self.conns)

    def incr_totals(self, **deltas):
        pass


class _FakePackets:
    def __init__(self):
        self.emitted = []

    def build_packet(self, state, key, now, kind, flag, lan_coords=None):
        pkt = {
            "seq": len(self.emitted) + 1,
            "direction": state.direction,
            "kind": kind,
            "flag": flag,
            "status": state.status,
            "total_up": state.total_up,
            "total_down": state.total_down,
        }
        self.emitted.append(pkt)
        return pkt


def _make_service(sweep_interval=5.0, update_every=3, close_gap_sweeps=2):
    store = _FakeStore()
    packets = _FakePackets()
    geo = GeoService(_FakeStoreGeo(), [])
    svc = ConnectionService(
        store,
        packets,
        geo,
        LISTEN_PORTS,
        wan_ip_provider=lambda: "203.0.113.7",
        lan_coords_provider=lambda: {},
        update_every=update_every,
        close_gap_sweeps=close_gap_sweeps,
        sweep_interval=sweep_interval,
    )
    return svc, packets


class _FakeStoreGeo:
    def geo_get(self, ip):
        return None

    def geo_set(self, ip, info, ttl):
        pass


def _dns_row(up=100, down=50, status="已连接"):
    return {
        "protocol": "udp",
        "status": status,
        "dst_addr": "114.114.114.114",
        "src_port": 60811,
        "dst_port": 53,
        "forward_addr": "192.168.2.100",
        "app_name": "DNS",
        "interface": "wan1",
        "total_up": up,
        "total_down": down,
        "domain": "--",
    }


def test_new_connection_emits_new_event():
    svc, packets = _make_service()
    result = svc.process_rows([_dns_row()], "10.0.1.2")
    assert len(result.new_packets) == 1
    assert result.new_packets[0]["kind"] == "new"
    assert svc.active_count() == 1


def test_update_rate_delta():
    svc, packets = _make_service()
    svc.process_rows([_dns_row(up=100, down=50)], "10.0.1.2")
    time.sleep(0.01)
    svc.process_rows([_dns_row(up=200, down=100)], "10.0.1.2")
    # 仍是同一连接（同 key），速率差分成功
    assert svc.active_count() == 1
    state = next(iter(svc.active.values()))
    assert state.total_up == 200
    assert state.up_bps > 0


def test_counter_rollback_ignored():
    """计数回卷（路由器重启）时差分归零不产生负速率。"""
    svc, _ = _make_service()
    svc.process_rows([_dns_row(up=10000, down=5000)], "10.0.1.2")
    svc.process_rows([_dns_row(up=50, down=20)], "10.0.1.2")
    state = next(iter(svc.active.values()))
    assert state.up_bps >= 0 and state.down_bps >= 0


def test_stale_connection_closed():
    svc, packets = _make_service(sweep_interval=0.05, close_gap_sweeps=2)
    svc.process_rows([_dns_row()], "10.0.1.2")
    assert svc.active_count() == 1
    time.sleep(0.3)
    closed = svc.close_stale()
    assert svc.active_count() == 0
    assert len(closed) == 1
    assert closed[0]["kind"] == "closed"


def test_closed_short_lived_flagged_failed():
    """出生<5s 且状态=关闭连接 → flag=failed（doc §5.2）。"""
    svc, packets = _make_service(sweep_interval=0.05)
    svc.process_rows([_dns_row(status="关闭连接")], "10.0.1.2")
    time.sleep(0.1)
    closed = svc.close_stale()
    assert closed and closed[0]["flag"] == "failed"


def test_dirty_rows_dropped_not_raised():
    svc, packets = _make_service()
    result = svc.process_rows(
        [
            {
                "protocol": "tcp",
                "dst_addr": "not-an-ip",
                "src_port": 1,
                "dst_port": 2,
                "forward_addr": "10.0.1.2",
            },
            "not-a-dict",
            None,
            _dns_row(),
        ],
        "10.0.1.2",
    )
    assert result.dropped_invalid == 3
    assert len(result.new_packets) == 1
    assert svc.active_count() == 1


def test_external_rows_dropped():
    row = {
        "protocol": "tcp",
        "status": "已连接",
        "dst_addr": "8.8.8.8",
        "src_port": 5000,
        "dst_port": 53,
        "forward_addr": "1.1.1.1",
        "app_name": "X",
        "interface": "wan1",
        "total_up": 1,
        "total_down": 1,
        "domain": "--",
    }
    svc, _ = _make_service()
    result = svc.process_rows([row], "60.1.2.3")
    assert result.dropped_external == 1
    assert svc.active_count() == 0
