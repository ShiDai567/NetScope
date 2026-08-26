"""Mock 场景剧本（doc §12）。

使用 RFC 5737 文档保留 IP 段（192.0.2.0/24、198.51.100.0/24、203.0.113.0/24）
模拟公网对端，并配套手工 Geo 坐标注入——既保证演示效果又不伪造真实 IP 归属。
"""

PEER_POOL: list[dict] = [
    {
        "ip": "192.0.2.10",
        "domain": "dns.example.net",
        "port": 53,
        "proto": "udp",
        "app": "DNS",
        "country": "Singapore",
        "code": "SG",
        "city": "Singapore",
        "lat": 1.3521,
        "lng": 103.8198,
    },
    {
        "ip": "192.0.2.20",
        "domain": "cdn.example.net",
        "port": 443,
        "proto": "tcp",
        "app": "Cloudflare",
        "country": "United States",
        "code": "US",
        "city": "San Francisco",
        "lat": 37.7749,
        "lng": -122.4194,
    },
    {
        "ip": "192.0.2.30",
        "domain": "cdn-tokyo.example.net",
        "port": 443,
        "proto": "tcp",
        "app": "HTTPS",
        "country": "Japan",
        "code": "JP",
        "city": "Tokyo",
        "lat": 35.6895,
        "lng": 139.6917,
    },
    {
        "ip": "192.0.2.40",
        "domain": "update.example.net",
        "port": 443,
        "proto": "quic",
        "app": "QUIC",
        "country": "Germany",
        "code": "DE",
        "city": "Frankfurt",
        "lat": 50.1109,
        "lng": 8.6821,
    },
    {
        "ip": "192.0.2.50",
        "domain": "api.example.net",
        "port": 443,
        "proto": "tcp",
        "app": "网页浏览",
        "country": "Singapore",
        "code": "SG",
        "city": "Singapore",
        "lat": 1.3521,
        "lng": 103.8198,
    },
    {
        "ip": "192.0.2.60",
        "domain": "mirror.example.net",
        "port": 80,
        "proto": "tcp",
        "app": "HTTP",
        "country": "United States",
        "code": "US",
        "city": "Ashburn",
        "lat": 39.0438,
        "lng": -77.4874,
    },
    {
        "ip": "198.51.100.10",
        "domain": "ntp.example.net",
        "port": 123,
        "proto": "udp",
        "app": "NTP",
        "country": "Japan",
        "code": "JP",
        "city": "Osaka",
        "lat": 34.6937,
        "lng": 135.5023,
    },
    {
        "ip": "198.51.100.20",
        "domain": "dns-over-tls.example.net",
        "port": 853,
        "proto": "tcp",
        "app": "DoH",
        "country": "United States",
        "code": "US",
        "city": "Seattle",
        "lat": 47.6062,
        "lng": -122.3321,
    },
    {
        "ip": "198.51.100.30",
        "domain": "media.example.net",
        "port": 443,
        "proto": "tcp",
        "app": "米家",
        "country": "China",
        "code": "CN",
        "city": "Beijing",
        "lat": 39.9042,
        "lng": 116.4074,
    },
    {
        "ip": "203.0.113.10",
        "domain": "push.example.net",
        "port": 443,
        "proto": "tcp",
        "app": "钉钉",
        "country": "China",
        "code": "CN",
        "city": "Hangzhou",
        "lat": 30.2741,
        "lng": 120.1551,
    },
    {
        "ip": "203.0.113.20",
        "domain": "bt-tracker.example.net",
        "port": 8080,
        "proto": "tcp",
        "app": "BT数据下载",
        "country": "Netherlands",
        "code": "NL",
        "city": "Amsterdam",
        "lat": 52.3676,
        "lng": 4.9041,
    },
    {
        "ip": "203.0.113.30",
        "domain": "game.example.net",
        "port": 27015,
        "proto": "udp",
        "app": "未知协议",
        "country": "Japan",
        "code": "JP",
        "city": "Tokyo",
        "lat": 35.6895,
        "lng": 139.6917,
    },
]

MOCK_GEO_OVERRIDES: dict[str, dict] = {
    peer["ip"]: {
        "country": peer["country"],
        "code": peer["code"],
        "region": peer["country"],
        "city": peer["city"],
        "lat": peer["lat"],
        "lng": peer["lng"],
    }
    for peer in PEER_POOL
}

MOCK_WAN_IP = "203.0.113.7"

MOCK_TERMINALS: list[dict] = [
    {"ip": "10.1.1.1", "mac": "00:11:22:33:44:55", "comment": "iKuai-Router", "interface": "lan1"},
    {"ip": "10.1.1.2", "mac": "60:be:b4:05:f3:67", "comment": "iStoreOS", "interface": "lan1"},
    {"ip": "10.1.1.10", "mac": "AA:BB:CC:00:00:10", "comment": "Workstation", "interface": "lan1"},
    {"ip": "10.1.1.20", "mac": "AA:BB:CC:00:00:20", "comment": "NAS", "interface": "lan1"},
    {"ip": "10.1.1.30", "mac": "AA:BB:CC:00:00:30", "comment": "Phone", "interface": "wlan1"},
    {"ip": "10.1.1.40", "mac": "AA:BB:CC:00:00:40", "comment": "TV", "interface": "wlan1"},
    {"ip": "192.168.2.100", "mac": "60:be:b4:05:f3:68", "comment": "Upstream-NAT", "interface": "lan1"},
    {"ip": "192.168.2.1", "mac": "00:11:22:33:44:66", "comment": "DNS-Relay", "interface": "lan1"},
]

_STATUS_CYCLE = ["请求连接", "已连接", "已连接", "已连接", "等待"]

SCENARIOS = ("mixed", "outbound", "inbound_nat", "internal", "dirty")

SCENARIO_SPAWN_WEIGHTS = {
    "mixed": {"outbound": 0.62, "inbound": 0.08, "internal": 0.28, "dirty": 0.02},
    "outbound": {"outbound": 0.90, "inbound": 0.02, "internal": 0.06, "dirty": 0.02},
    "inbound_nat": {"outbound": 0.25, "inbound": 0.60, "internal": 0.13, "dirty": 0.02},
    "internal": {"outbound": 0.15, "inbound": 0.03, "internal": 0.80, "dirty": 0.02},
    "dirty": {"outbound": 0.30, "inbound": 0.05, "internal": 0.25, "dirty": 0.40},
}
