"""聚合器与带宽测试。"""

from analytics.aggregators import (
    APPLICATIONS,
    DIRECTIONS,
    PORTS,
    PROTOCOLS,
    RollingCounters,
)
from analytics.bandwidth import BandwidthTracker


def _pkt(
    direction="outbound",
    proto="tcp",
    app="DNS",
    port=443,
    ts=1000.0,
    up=100,
    down=50,
    dst_ip="8.8.8.8",
    src_ip="10.0.1.2",
    country=None,
):
    return {
        "direction": direction,
        "protocol": proto,
        "app_name": app,
        "timestamp": ts,
        "total_up": up,
        "total_down": down,
        "source": {"ip": src_ip, "port": 5000},
        "destination": {"ip": dst_ip, "port": port},
    }


def test_counter_dimensions():
    c = RollingCounters()
    c.add_event(_pkt(), peer_country="CN|China")
    c.add_event(_pkt(proto="udp", port=53), peer_country="CN|China")
    c.add_event(_pkt(direction="internal", dst_ip="192.168.2.1", country=None))

    now = 1005.0
    directions = dict((d, n) for d, n, _b in c.window_top(DIRECTIONS, 5, now))
    assert directions == {"outbound": 2, "internal": 1}

    protocols = dict((p, n) for p, n, _b in c.window_top(PROTOCOLS, 5, now))
    assert protocols == {"tcp": 2, "udp": 1}

    apps = dict((a, n) for a, n, _b in c.window_top(APPLICATIONS, 5, now))
    assert apps == {"DNS": 3}

    ports = dict((p, n) for p, n, _b in c.window_top(PORTS, 5, now))
    assert ports == {"443": 2, "53": 1}


def test_counter_flush_ops_roundtrip():
    c = RollingCounters()
    c.add_event(_pkt(), peer_country="CN|China")
    ops = c.flush_ops()
    assert ops
    dims = {op[0] for op in ops}
    assert "directions" in dims and "protocols" in dims
    # flush 后 pending 清空，history 保留（统计快照不受影响）
    assert c.flush_ops() == []
    assert c.window_sum(DIRECTIONS, 5, 1005.0, "outbound") == 1


def test_counter_window_expiry():
    c = RollingCounters()
    c.add_event(_pkt(ts=1000.0))
    # 60s 窗口下 10s 前的事件已出窗
    assert c.window_sum(DIRECTIONS, 10, 1070.0) == 0
    # 仍在 60s 窗口内
    assert c.window_sum(DIRECTIONS, 60, 1070.0) == 1


def test_bandwidth_ewma_and_series():
    bw = BandwidthTracker(alpha=1.0)
    bw.push(1000.0, 100, 200)
    bw.push(1001.0, 300, 400)
    up, down = bw.latest()
    assert up == 300 and down == 400

    series = bw.series(60, 1061.0, max_points=60)
    # 两点分属相邻秒桶：各成一点
    assert len(series) == 2
    assert series[0] == [1000, 100.0, 200.0]
    assert series[1] == [1001, 300.0, 400.0]


def test_bandwidth_empty_series():
    bw = BandwidthTracker()
    assert bw.series(60, 1000.0) == []
    assert bw.latest() == (0.0, 0.0)
