"""核心逻辑测试：方向判断 / 数据包结构 / 模拟引擎 / API。"""
import time
import unittest

from django.test import Client, SimpleTestCase

from .geo import internal_ring_position, is_private_ip, locate_public_ip
from .packets import (
    DIRECTION_INBOUND,
    DIRECTION_INTERNAL,
    DIRECTION_OUTBOUND,
    build_packet,
    judge_direction,
    normalize_status,
)
from .simulation import SimulationEngine

GATEWAY = (39.9042, 116.4074)


class IpHelpersTest(SimpleTestCase):
    def test_private_ranges(self):
        for ip in ["10.0.1.2", "192.168.2.1", "172.16.5.4", "127.0.0.1"]:
            self.assertTrue(is_private_ip(ip), ip)
        for ip in ["8.8.8.8", "162.159.61.8", "203.119.238.180"]:
            self.assertFalse(is_private_ip(ip), ip)

    def test_locate_public_ip_deterministic(self):
        a = locate_public_ip("203.0.113.99")
        b = locate_public_ip("203.0.113.99")
        self.assertEqual(a, b)
        lat, lng, _ = locate_public_ip("1.1.1.1")
        self.assertAlmostEqual(lat, 37.7749)

    def test_ring_positions_unique(self):
        positions = {internal_ring_position(i, GATEWAY) for i in range(12)}
        self.assertEqual(len(positions), 12)


class DirectionTest(SimpleTestCase):
    def test_outbound(self):
        # dst 公网 + forward 内网
        self.assertEqual(
            judge_direction("162.159.61.8", "10.0.1.2"), DIRECTION_OUTBOUND
        )

    def test_inbound(self):
        # dst 内网 + forward 公网
        self.assertEqual(
            judge_direction("10.0.1.2", "203.119.238.180"), DIRECTION_INBOUND
        )

    def test_internal(self):
        # 双内网
        self.assertEqual(
            judge_direction("192.168.2.1", "10.0.1.10"), DIRECTION_INTERNAL
        )


class StatusNormalizeTest(SimpleTestCase):
    def test_udp_has_no_status(self):
        self.assertIsNone(normalize_status("udp", "--"))
        self.assertIsNone(normalize_status("udp", None))
        self.assertIsNone(normalize_status("icmp", "已连接"))

    def test_tcp_status_passthrough(self):
        self.assertEqual(normalize_status("tcp", "等待"), "等待连接")
        self.assertEqual(normalize_status("tcp", "请求连接"), "请求连接")
        self.assertEqual(normalize_status("tcp", "已连接"), "已连接")
        self.assertEqual(normalize_status("tcp", "关闭连接"), "关闭连接")


class BuildPacketTest(SimpleTestCase):
    def test_outbound_packet_shape(self):
        pkt = build_packet(
            packet_id="pkt_001",
            timestamp=1712450000.0,
            device_ip="10.0.1.2",
            protocol="tcp",
            status="请求连接",
            dst_addr="162.159.61.8",
            forward_addr="10.0.1.2",
            src_port=40786,
            dst_port=443,
            app_name="Cloudflare",
            total_up=60,
            total_down=0,
            gateway=GATEWAY,
            domain="dns.cloudflare.com",
        )
        self.assertEqual(pkt["direction"], "outbound")
        self.assertEqual(pkt["source"]["ip"], "10.0.1.2")
        self.assertEqual(pkt["destination"]["ip"], "162.159.61.8")
        self.assertEqual(pkt["destination"]["domain"], "dns.cloudflare.com")
        self.assertEqual(pkt["nat_info"]["forward_addr"], "10.0.1.2")
        self.assertEqual(pkt["status"], "请求连接")

    def test_inbound_packet_with_original_dst(self):
        pkt = build_packet(
            packet_id="pkt_003",
            timestamp=1712450000.0,
            device_ip="10.0.1.2",
            protocol="tcp",
            status="已连接",
            dst_addr="10.0.1.2",
            forward_addr="203.119.238.180",
            src_port=57584,
            dst_port=445,
            app_name="SMB",
            total_up=2225,
            total_down=2156,
            gateway=GATEWAY,
            original_dst="192.168.2.158",
        )
        self.assertEqual(pkt["direction"], "inbound")
        self.assertEqual(pkt["source"]["ip"], "203.119.238.180")
        self.assertEqual(pkt["destination"]["ip"], "10.0.1.2")
        self.assertEqual(pkt["nat_info"]["original_dst"], "192.168.2.158")

    def test_internal_packet(self):
        pkt = build_packet(
            packet_id="pkt_002",
            timestamp=1712450000.0,
            device_ip="10.0.1.10",
            protocol="udp",
            status="--",
            dst_addr="192.168.2.1",
            forward_addr="10.0.1.1",
            src_port=38338,
            dst_port=53,
            app_name="DNS",
            total_up=63,
            total_down=0,
            gateway=GATEWAY,
        )
        self.assertEqual(pkt["direction"], "internal")
        self.assertIsNone(pkt["status"])
        self.assertEqual(pkt["source"]["ip"], "10.0.1.1")
        self.assertEqual(pkt["destination"]["ip"], "192.168.2.1")


class SimulationEngineTest(SimpleTestCase):
    def test_engine_generates_events_and_lifecycle(self):
        events: list[dict] = []
        devices: list[list[dict]] = []
        engine = SimulationEngine(
            emit=events.append,
            gateway=GATEWAY,
            device_snapshot=devices.append,
        )
        # 手动驱动 80 个 tick（40 秒模拟时间）
        for _ in range(80):
            engine.tick()
            time.sleep(0.001)

        self.assertTrue(events, "模拟引擎没有产生任何事件")
        directions = {e["direction"] for e in events}
        self.assertTrue(directions & {"outbound", "internal"})
        ids = {e["id"] for e in events}
        # 同一连接应有多条事件（状态演进）
        multi = [i for i in ids if sum(1 for e in events if e["id"] == i) > 1]
        self.assertTrue(multi, "连接没有状态演进事件")
        for e in events:
            self.assertIn("source", e)
            self.assertIn("destination", e)
            self.assertIn("nat_info", e)
            self.assertNotIn("seq", e)  # seq 由 hub 分配，引擎不设置
            src = e["source"]
            self.assertTrue({"ip", "port", "lat", "lng"} <= set(src))
        engine.stop()

    def test_devices_snapshot(self):
        engine = SimulationEngine(emit=lambda e: None, gateway=GATEWAY)
        engine.tick()
        devices = engine._devices
        self.assertTrue(any(d.get("is_gateway") for d in devices))
        self.assertTrue(all("mac" in d and "hostname" in d for d in devices))


class ApiTest(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_packets_incremental(self):
        from .hub import hub

        hub.ensure_started()
        resp = self.client.get("/api/packets?since=0")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("events", data)
        self.assertIn("last_seq", data)
        # 增量参数生效
        resp2 = self.client.get(f"/api/packets?since={data['last_seq']}")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["events"], [])

    def test_stats_shape(self):
        from .hub import hub

        hub.ensure_started()
        hub._emit(
            build_packet(
                packet_id="test_stats_1",
                timestamp=time.time(),
                device_ip="10.0.1.2",
                protocol="tcp",
                status="已连接",
                dst_addr="8.8.8.8",
                forward_addr="10.0.1.2",
                src_port=1000,
                dst_port=443,
                app_name="SSL",
                total_up=100,
                total_down=200,
                gateway=GATEWAY,
            )
        )
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in [
            "total",
            "active",
            "closed",
            "directions",
            "protocols",
            "bandwidth",
            "loss_rate",
            "latency_heatmap",
        ]:
            self.assertIn(key, data)

    def test_devices_and_nodes(self):
        from .hub import hub

        hub.ensure_started()
        hub._engine.tick()
        hub._engine._push_device_snapshot(time.time())
        resp = self.client.get("/api/devices")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["devices"])
        resp = self.client.get("/api/nodes")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["nodes"])

    def test_history(self):
        from .hub import hub

        hub.ensure_started()
        resp = self.client.get("/api/history?minutes=5")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("events", resp.json())

    def test_ikuai_connect_validation(self):
        resp = self.client.post(
            "/api/ikuai/connect",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
