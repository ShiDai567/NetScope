import type { DeviceInfo, PublicNode, StatsSnapshot } from "@/lib/types";

/**
 * Django REST API 客户端。
 * 所有请求容错：失败返回 null，由上层决定降级展示，绝不让页面崩溃。
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

async function getJson<T>(path: string, timeoutMs = 8000): Promise<T | null> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${API_BASE}${path}`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------- 原始结构

interface RawPacketsResponse {
  server_time: number;
  last_seq: number;
  events: unknown[];
}

interface RawStatsResponse {
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
  system?: {
    cpu_percent?: number | null;
    memory_percent?: number | null;
  };
  latency_heatmap?: {
    x: number[];
    y: string[];
    data: [number, number, number][];
  };
  mode?: string;
  uptime?: number;
}

interface RawDevice {
  ip?: string;
  mac?: string;
  hostname?: string;
  vendor?: string;
  interface?: string;
  is_gateway?: boolean;
  ring_index?: number;
  lat?: number;
  lng?: number;
  connections?: number;
  up_rate?: number;
  down_rate?: number;
}

interface RawNode {
  ip?: string;
  name?: string;
  domain?: string | null;
  lat?: number;
  lng?: number;
  type?: string;
}

// ---------------------------------------------------------------- 归一输出

import type { BandwidthSeriesPoint } from "@/lib/types";

function adaptStats(raw: RawStatsResponse): StatsSnapshot {
  const directions = raw.directions ?? {};
  const protocols = raw.protocols ?? {};
  const series: BandwidthSeriesPoint[] = (raw.bandwidth?.series ?? [])
    .filter((p) => Array.isArray(p) && p.length >= 3)
    .map((p) => ({ t: p[0], upBps: p[1], downBps: p[2] }));
  return {
    total: raw.total ?? 0,
    active: raw.active ?? 0,
    closed: raw.closed ?? 0,
    failed: raw.failed ?? 0,
    lost: raw.lost ?? 0,
    directions: {
      outbound: directions.outbound ?? 0,
      inbound: directions.inbound ?? 0,
      internal: directions.internal ?? 0,
    },
    protocols: { tcp: protocols.tcp ?? 0, udp: protocols.udp ?? 0, ...protocols },
    apps: (raw.apps ?? []).filter((a) => a && typeof a.name === "string"),
    bandwidth: {
      upBps: raw.bandwidth?.up_bps ?? 0,
      downBps: raw.bandwidth?.down_bps ?? 0,
      series,
    },
    lossRate: raw.loss_rate ?? 0,
    avgLatencyMs: raw.avg_latency_ms ?? 0,
    system: {
      cpuPercent:
        typeof raw.system?.cpu_percent === "number" ? raw.system.cpu_percent : null,
      memoryPercent:
        typeof raw.system?.memory_percent === "number"
          ? raw.system.memory_percent
          : null,
    },
    mode: "ikuai",
    uptime: raw.uptime ?? 0,
  };
}

function adaptDevice(raw: RawDevice): DeviceInfo | null {
  if (!raw.ip) return null;
  return {
    ip: raw.ip,
    mac: raw.mac || undefined,
    hostname: raw.hostname || undefined,
    vendor: raw.vendor || undefined,
    interface: raw.interface || undefined,
    isGateway: Boolean(raw.is_gateway),
    ringIndex: typeof raw.ring_index === "number" ? raw.ring_index : undefined,
    lat: typeof raw.lat === "number" ? raw.lat : null,
    lng: typeof raw.lng === "number" ? raw.lng : null,
    connections: raw.connections ?? 0,
    upRate: raw.up_rate ?? 0,
    downRate: raw.down_rate ?? 0,
  };
}

function adaptNode(raw: RawNode): PublicNode | null {
  if (
    !raw.ip ||
    typeof raw.lat !== "number" ||
    typeof raw.lng !== "number" ||
    Number.isNaN(raw.lat) ||
    Number.isNaN(raw.lng)
  ) {
    return null;
  }
  const type =
    raw.type === "gateway" || raw.type === "server" ? raw.type : "client";
  return {
    ip: raw.ip,
    name: raw.name || raw.ip,
    domain: raw.domain || null,
    lat: raw.lat,
    lng: raw.lng,
    type,
  };
}

// ---------------------------------------------------------------- API

export interface ModeResponse {
  mode?: string;
  uptime?: number;
  gateway?: { lat?: number; lng?: number };
  ikuai?: {
    router_url?: string;
    error?: string | null;
    last_poll_at?: number | null;
    connected_at?: number;
  };
}

export const api = {
  async mode(): Promise<ModeResponse | null> {
    return getJson<ModeResponse>("/api/mode");
  },

  async packets(sinceSeq: number): Promise<RawPacketsResponse | null> {
    return getJson<RawPacketsResponse>(`/api/packets?since=${sinceSeq}`);
  },

  async stats(): Promise<StatsSnapshot | null> {
    const raw = await getJson<RawStatsResponse>("/api/stats");
    return raw ? adaptStats(raw) : null;
  },

  async devices(): Promise<DeviceInfo[] | null> {
    const raw = await getJson<{ devices: RawDevice[] }>("/api/devices");
    if (!raw) return null;
    return (raw.devices ?? [])
      .map(adaptDevice)
      .filter((d): d is DeviceInfo => d !== null);
  },

  async nodes(): Promise<PublicNode[] | null> {
    const raw = await getJson<{ nodes: RawNode[] }>("/api/nodes");
    if (!raw) return null;
    return (raw.nodes ?? [])
      .map(adaptNode)
      .filter((n): n is PublicNode => n !== null);
  },
};
