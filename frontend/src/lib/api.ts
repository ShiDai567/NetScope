const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:4000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} error: ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} error: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string; uptime: number }>("/api/health"),
  packets: (since: number) =>
    get<{ server_time: number; last_seq: number; events: import("./types").PacketEvent[] }>(
      `/api/packets?since=${since}`
    ),
  history: (minutes = 10) =>
    get<{ server_time: number; last_seq: number; events: import("./types").PacketEvent[] }>(
      `/api/history?minutes=${minutes}`
    ),
  devices: () => get<{ devices: import("./types").DeviceInfo[] }>("/api/devices"),
  nodes: () => get<{ nodes: import("./types").PublicNode[] }>("/api/nodes"),
  stats: () => get<import("./types").StatsSnapshot>("/api/stats"),
  mode: () => get<{ mode: string }>("/api/mode"),
  ikuaiConnect: (body: { routerUrl: string; username: string; password: string }) =>
    post<Record<string, unknown>>("/api/ikuai/connect", body),
  ikuaiDisconnect: () => post<Record<string, unknown>>("/api/ikuai/disconnect", {}),
};
