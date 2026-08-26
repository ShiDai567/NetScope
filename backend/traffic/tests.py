"""核心逻辑测试：方向判断 / 数据包结构 / 模拟引擎 / API。"""
import time
import unittest

from django.test import Client, SimpleTestCase, override_settings

from .geo import internal_ring_position, is_private_ip, locate_public_ip
from .packets import (
    DIRECTION_INBOUND,
    DIRECTION_INTERNAL,
    DIRECTION_OUTBOUND,
    build_packet,
    judge_direction,
    normalize_status,
)

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


def _make_device(ip: str = "10.0.1.2", **extra) -> dict:
    """构造与 IKuaiPoller._convert_devices 输出同构的设备快照（测试夹具）。"""
    base = {
        "ip": ip,
        "mac": "60:be:b4:05:f3:67",
        "hostname": "iStoreOS",
        "vendor": "Unknown",
        "interface": "lan1",
        "is_gateway": False,
        "lat": GATEWAY[0] + 0.5,
        "lng": GATEWAY[1] + 0.6,
        "connections": 3,
        "up_rate": 1024.0,
        "down_rate": 2048.0,
    }
    base.update(extra)
    return base


@override_settings(IKUAI_URL="", IKUAI_USERNAME="", IKUAI_PASSWORD="", IKUAI_FALLBACK_URL="")
class ApiTest(SimpleTestCase):
    """API 测试离线运行：.env 配置了真实 iKuai 也不访问外部路由器。

    通过 hub 的注入接口直接写入真实结构的数据快照/事件，
    只测 API 契约，不依赖路由器在线。
    """

    def setUp(self):
        self.client = Client()
        from .hub import hub

        # 清理单例状态残留，保证测试确定性
        if hub._poller is not None:
            hub._poller.stop()
            hub._poller = None
        hub.ensure_started()

    def test_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"] == "ok", True)

    def test_packets_incremental(self):
        from .hub import hub

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

        hub._set_devices([_make_device()])
        resp = self.client.get("/api/devices")
        self.assertEqual(resp.status_code, 200)
        devices = resp.json()["devices"]
        self.assertTrue(devices)
        self.assertTrue(any(d["ip"] == "10.0.1.2" for d in devices))

        # nodes 始终包含网关，公网节点来自真实事件流
        hub._emit(
            build_packet(
                packet_id="test_node_probe",
                timestamp=time.time(),
                device_ip="10.0.1.2",
                protocol="tcp",
                status="已连接",
                dst_addr="8.8.4.4",
                forward_addr="10.0.1.2",
                src_port=2000,
                dst_port=53,
                app_name="DNS",
                total_up=10,
                total_down=20,
                gateway=GATEWAY,
            )
        )
        resp = self.client.get("/api/nodes")
        self.assertEqual(resp.status_code, 200)
        nodes = resp.json()["nodes"]
        self.assertTrue(any(n["type"] == "gateway" for n in nodes))
        self.assertTrue(any(n["ip"] == "8.8.4.4" for n in nodes))

    def test_history(self):
        from .hub import hub

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
