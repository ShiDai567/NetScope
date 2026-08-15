export interface Endpoint {
  ip: string;
  port: number;
  domain: string | null;
  lat: number;
  lng: number;
}

export interface NatInfo {
  forward_addr: string;
  src_port: number;
  dst_port: number;
  original_dst?: string;
}

export interface PacketEvent {
  id: string;
  timestamp: number;
  born: number;
  direction: "outbound" | "inbound" | "internal";
  app_name: string;
  protocol: "tcp" | "udp" | "icmp";
  status: "等待连接" | "请求连接" | "已连接" | "关闭连接" | null;
  source: Endpoint;
  destination: Endpoint;
  nat_info: NatInfo;
  total_up: number;
  total_down: number;
  flag?: "failed" | "lost" | "high_latency";
  latency_ms?: number;
  status_since?: number;
  interface?: string;
  seq?: number;
}

export interface DeviceInfo {
  ip: string;
  mac: string;
  hostname: string;
  vendor: string;
  interface: string;
  is_gateway?: boolean;
  lat: number;
  lng: number;
  connections: number;
  up_rate: number;
  down_rate: number;
  total_up?: number;
  total_down?: number;
}

export interface PublicNode {
  ip: string;
  name: string;
  domain: string | null;
  lat: number;
  lng: number;
  type: "server" | "client" | "gateway";
}

export interface StatsSnapshot {
  total: number;
  active: number;
  closed: number;
  failed: number;
  lost: number;
  directions: Record<string, number>;
  protocols: Record<string, number>;
  apps: { name: string; count: number }[];
  bandwidth: {
    up_bps: number;
    down_bps: number;
    series: [number, number, number][];
  };
  loss_rate: number;
  avg_latency_ms: number;
  latency_heatmap: {
    x: number[];
    y: string[];
    data: [number, number, number][];
  };
  mode: string;
  uptime: number;
}

export type DirectionFilter = "all" | "outbound" | "inbound" | "internal";
export type ProtocolFilter = "all" | "tcp" | "udp" | "icmp";
export type AppFilter =
  | "all"
  | "DNS"
  | "SMB"
  | "SSL"
  | "HTTP"
  | "HTTPS"
  | "其他";
