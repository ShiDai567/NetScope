const express = require('express');
const cors = require('cors');

const app = express();
const PORT = 4000;

app.use(cors());

// ── Network topology (mirrors frontend) ──
const servers = [
  { id: 'srv_us', name: 'Server (Silicon Valley)', lat: 27.994110585072477, lng: 120.69934126685061, ip: '8.8.8.8', type: 'server' },
];

const clients = [
  { id: 'cli_cn', name: 'Client (Beijing)',   lat: 39.90, lng: 116.40, ip: '192.168.1.10', type: 'client' },
  { id: 'cli_eu', name: 'Client (London)',    lat: 51.50, lng: -0.12,  ip: '192.168.1.20', type: 'client' },
  { id: 'cli_br', name: 'Client (São Paulo)', lat: -23.55, lng: -46.63, ip: '192.168.1.30', type: 'client' },
];

// Valid routes: Server↔Client, Server↔Server only
const validRoutes = [];
for (const s of servers) {
  for (const c of clients) {
    validRoutes.push({ from: s, to: c });
    validRoutes.push({ from: c, to: s });
  }
}
for (let i = 0; i < servers.length; i++) {
  for (let j = i + 1; j < servers.length; j++) {
    validRoutes.push({ from: servers[i], to: servers[j] });
    validRoutes.push({ from: servers[j], to: servers[i] });
  }
}

let packetCounter = 0;

function generatePacket() {
  const route = validRoutes[Math.floor(Math.random() * validRoutes.length)];
  const { from, to } = route;

  const statuses  = ['success', 'success', 'success', 'delayed', 'dropped'];
  const protocols = ['TCP', 'UDP', 'ICMP'];

  packetCounter++;

  return {
    id: `pkt_${String(packetCounter).padStart(3, '0')}`,
    source: {
      ip: from.ip,
      name: from.name,
      lat: from.lat,
      lng: from.lng,
      type: from.type,
    },
    destination: {
      ip: to.ip,
      name: to.name,
      lat: to.lat,
      lng: to.lng,
      type: to.type,
    },
    protocol: protocols[Math.floor(Math.random() * protocols.length)],
    status: statuses[Math.floor(Math.random() * statuses.length)],
    payloadSize: Math.floor(Math.random() * 1500) + 64,
    timestamp: Math.floor(Date.now() / 1000),
  };
}

// ── API: GET /api/packet — returns 1~3 random packets ──
app.get('/api/packet', (req, res) => {
  const count = Math.floor(Math.random() * 3) + 1; // 1~3 packets per poll
  const packets = Array.from({ length: count }, () => generatePacket());
  res.json(packets);
});

// ── API: GET /api/health ──
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

app.listen(PORT, () => {
  console.log(`🚀 NetScope Backend running at http://localhost:${PORT}`);
  console.log(`   GET /api/packet  — random packets`);
  console.log(`   GET /api/health  — server health`);
});
