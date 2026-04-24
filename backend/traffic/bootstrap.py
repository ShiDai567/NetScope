from .models import NetworkNode, NetworkRoute


DEFAULT_NODES = [
    {
        "node_id": "srv_us",
        "name": "Server (Silicon Valley)",
        "ip_address": "8.8.8.8",
        "node_type": NetworkNode.NodeType.SERVER,
        "latitude": "27.994111",
        "longitude": "120.699341",
    },
    {
        "node_id": "cli_cn",
        "name": "Client (Beijing)",
        "ip_address": "192.168.1.10",
        "node_type": NetworkNode.NodeType.CLIENT,
        "latitude": "39.900000",
        "longitude": "116.400000",
    },
    {
        "node_id": "cli_eu",
        "name": "Client (London)",
        "ip_address": "192.168.1.20",
        "node_type": NetworkNode.NodeType.CLIENT,
        "latitude": "51.500000",
        "longitude": "-0.120000",
    },
    {
        "node_id": "cli_br",
        "name": "Client (Sao Paulo)",
        "ip_address": "192.168.1.30",
        "node_type": NetworkNode.NodeType.CLIENT,
        "latitude": "-23.550000",
        "longitude": "-46.630000",
    },
]


def seed_default_network_data():
    nodes = {}
    for payload in DEFAULT_NODES:
        node, _ = NetworkNode.objects.update_or_create(
            node_id=payload["node_id"],
            defaults={
                **payload,
                "is_active": True,
            },
        )
        nodes[node.node_id] = node

    servers = [node for node in nodes.values() if node.node_type == NetworkNode.NodeType.SERVER]
    clients = [node for node in nodes.values() if node.node_type == NetworkNode.NodeType.CLIENT]

    for server in servers:
        for client in clients:
            NetworkRoute.objects.get_or_create(source_node=server, destination_node=client)
            NetworkRoute.objects.get_or_create(source_node=client, destination_node=server)

    for index, server in enumerate(servers):
        for peer in servers[index + 1 :]:
            NetworkRoute.objects.get_or_create(source_node=server, destination_node=peer)
            NetworkRoute.objects.get_or_create(source_node=peer, destination_node=server)
