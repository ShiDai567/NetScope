/**
 * Network topology — single source of truth.
 *
 * Route rules:
 *   ✅ Server ↔ Client
 *   ✅ Server ↔ Server
 *   ❌ Client ↔ Client
 */

export const servers = [
  { id: 'srv_us', name: 'Server (Silicon Valley)', coord: [120.69934126685061, 27.994110585072477], ip: '8.8.8.8' },
];

export const clients = [
  { id: 'cli_cn', name: 'Client (Beijing)',   coord: [116.40, 39.90],   ip: '192.168.1.10' },
  { id: 'cli_eu', name: 'Client (London)',    coord: [-0.12, 51.50],    ip: '192.168.1.20' },
  { id: 'cli_br', name: 'Client (São Paulo)', coord: [-46.63, -23.55], ip: '192.168.1.30' },
];

// Pre-compute valid routes once
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

let counter = 0;

/** Generate one random packet along a valid route */
export function createPacket() {
  const route = validRoutes[Math.floor(Math.random() * validRoutes.length)];
  const { from, to } = route;

  const status   = ['success','success','success','delayed','dropped'][Math.floor(Math.random() * 5)];
  const protocol = ['TCP','UDP','ICMP'][Math.floor(Math.random() * 3)];
  counter++;

  let endCoord = to.coord;
  let period = 3;
  if (status === 'delayed') period = 6;
  if (status === 'dropped') {
    endCoord = [
      from.coord[0] + (to.coord[0] - from.coord[0]) * 0.6,
      from.coord[1] + (to.coord[1] - from.coord[1]) * 0.6,
    ];
  }

  const color = { success: '#00ff88', delayed: '#ffcc00', dropped: '#ff3366' }[status];
  const lifetime = (status === 'dropped' ? period * 0.6 : period) * 1000 + 300;

  // Find which client is involved (could be from or to)
  const client = clients.find(c => c.id === from.id || c.id === to.id);

  return {
    id: `pkt_${counter}`,
    _key: `${Date.now()}_${Math.random().toString(36).slice(2,6)}`,
    from, to, status, protocol, color, period, lifetime,
    clientId: client ? client.id : null,
    coords: [from.coord, endCoord],
    size: Math.floor(Math.random() * 1500) + 64,
    timestamp: Math.floor(Date.now() / 1000),
  };
}
