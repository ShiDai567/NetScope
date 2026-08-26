"""LAN 布局与设备适配测试。"""

from core.lan_layout import assign_positions, ring_position
from network.adapters.device import adapt_terminal


def test_ring_position_deterministic_and_centered():
    p1 = ring_position((32.0, 112.0), 3)
    p1b = ring_position((32.0, 112.0), 3)
    assert p1 == p1b
    # 距中心处于第一环半径量级（LAN 视口尺度）
    lat, lng = p1
    assert 0.5 < abs(lat - 32.0) < 2.2
    assert 0.5 < abs(lng - 112.0) < 3.5


def test_ring_positions_spread():
    """不同 ring_index 的位置应明显分离（修复重叠问题）。"""
    import math

    pts = [ring_position((32.0, 112.0), i) for i in range(8)]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dist = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
            assert dist > 0.5, f"ring {i} 与 {j} 距离过近: {dist}"


def test_assign_positions_gateway_centered():
    devices = [
        {"ip": "10.0.1.5", "is_gateway": False},
        {"ip": "10.0.1.1", "is_gateway": True},
        {"ip": "10.0.1.3", "is_gateway": False},
    ]
    assign_positions(devices, (32.0, 112.0))
    by_ip = {d["ip"]: d for d in devices}
    gw = by_ip["10.0.1.1"]
    assert gw["ring_index"] == -1
    assert gw["lat"] == 32.0 and gw["lng"] == 112.0
    # 其余设备按 IP 排序获得稳定 ring_index
    assert by_ip["10.0.1.3"]["ring_index"] == 0
    assert by_ip["10.0.1.5"]["ring_index"] == 1
    # 所有坐标都是 float
    for dev in devices:
        assert isinstance(dev["lat"], float)
        assert isinstance(dev["lng"], float)


def test_adapt_terminal_fields(terminal_rows):
    devs = [adapt_terminal(row, gateway_ip="10.0.1.1") for row in terminal_rows]
    devs = [d for d in devs if d]
    assert len(devs) == len(terminal_rows)
    by_ip = {d["ip"]: d for d in devs}
    assert "10.0.1.2" in by_ip
    dev = by_ip["10.0.1.2"]
    assert dev["hostname"] == "iStoreOS"
    assert isinstance(dev["connections"], int)
    assert dev["is_gateway"] is False
    assert dev["up_rate"] == 0.0


def test_adapt_terminal_dirty_row():
    assert adapt_terminal({"ip_addr": "not-an-ip"}, None) is None
    assert adapt_terminal({}, None) is None
    dev = adapt_terminal({"ip_addr": "10.0.1.9", "comment": "--", "connect_num": "3"}, None)
    assert dev["hostname"] is None
    assert dev["connections"] == 3
