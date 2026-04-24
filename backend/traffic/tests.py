from django.test import TestCase

from .models import NetworkNode, PacketEvent


class TrafficApiTests(TestCase):
    fixtures = []

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_packet_endpoint_returns_frontend_shape(self):
        response = self.client.get("/api/packet?count=2")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload), 2)
        self.assertEqual(PacketEvent.objects.count(), 2)
        self.assertIn("source", payload[0])
        self.assertIn("destination", payload[0])
        self.assertIn("payloadSize", payload[0])

    def test_nodes_endpoint_uses_seed_data(self):
        response = self.client.get("/api/nodes")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload), 4)
        self.assertEqual(NetworkNode.objects.count(), 4)
