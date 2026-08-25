/** 全局网络智能中心 —— 统一类型定义 */

export type Direction = "outbound" | "inbound" | "internal";

export type Scene = "global" | "china" | "lan";

export type ConnectionState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface Endpoint {
  ip: string;
  port: number;
  domain: string | null;
  lat: number | null;
  lng: number | null;
}

export interface NatInfo {
  forwardAddress?: string;
  sourcePort?: number;
  destinationPort?: number;
  originalDestination?: string;
}

/** 标准化后的网络流（AGENTS.md §18 契约，前端所有组件只依赖此结构） */
export interface NetworkFlow {
  id: string;
  seq: number;
  timestamp: number; // 秒（服务器时间）
  born: number;
  direction: Direction;
  source: Endpoint;
  destination: Endpoint;
  application: string;
  protocol: string;
  status: string | null;
  bytes: {
    upload: number;
    download: number;
    total: number;
  };
  nat?: NatInfo;
  interface?: string;
  flag?: "failed" | "lost" | "high_latency";
  latencyMs?: number;
  statusSince?: number;
}

export interface DeviceInfo {
  ip: string;
  mac?: string;
  hostname?: string;
  vendor?: string;
  interface?: string;
  isGateway?: boolean;
  ringIndex?: number;
  lat: number | null;
  lng: number | null;
  connections: number;
  upRate: number;
  downRate: number;
}

export interface PublicNode {
  ip: string;
  name: string;
  domain: string | null;
  lat: number;
  lng: number;
  type: "gateway" | "server" | "client";
}

export interface BandwidthSeriesPoint {
  t: number;
  upBps: number;
  downBps: number;
}

export interface StatsSnapshot {
  total: number;
  active: number;
  closed: number;
  failed: number;
  lost: number;
  directions: Record<Direction, number>;
  protocols: Record<string, number>;
  apps: { name: string; count: number }[];
  bandwidth: {
    upBps: number;
    downBps: number;
    series: BandwidthSeriesPoint[];
  };
  lossRate: number;
  avgLatencyMs: number;
  mode: "simulation" | "ikuai";
  uptime: number;
}

export type TimeWindow = 5 | 30 | 60 | 300 | 900 | 3600;

/** 底部事件流条目 */
export interface EventEntry {
  id: string;
  seq: number;
  timestamp: number;
  direction: Direction;
  source: string;
  destination: string;
  protocol: string;
  port: number;
  application: string;
  bytesTotal: number;
  status: string | null;
  flag?: NetworkFlow["flag"];
}

/** 地图聚合流（同一 src→dst 对的合并渲染单元） */
export interface AggregatedFlow {
  key: string;
  direction: Direction;
  from: { lat: number; lng: number };
  to: { lat: number; lng: number };
  packets: number;
  bytes: number;
  lastTimestamp: number;
  sample: NetworkFlow;
}
