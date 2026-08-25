import { isPrivateIP } from "@/lib/network/isPrivateIp";
import type { Direction, Endpoint, NetworkFlow } from "@/lib/types";

/**
 * Backend Raw Packet
 *       ↓
 *  Adapter（容错归一）
 *       ↓
 *  NetworkFlow
 *
 * 后端字段未来可能变化，任何一条异常数据都不允许抛出异常；
 * 归一失败返回 null 并被调用方丢弃。
 */

interface RawEndpoint {
  ip?: unknown;
  port?: unknown;
  domain?: unknown;
  lat?: unknown;
  lng?: unknown;
}

interface RawPacket {
  id?: unknown;
  seq?: unknown;
  timestamp?: unknown;
  born?: unknown;
  direction?: unknown;
  app_name?: unknown;
  protocol?: unknown;
  status?: unknown;
  source?: unknown;
  destination?: unknown;
  nat_info?: unknown;
  total_up?: unknown;
  total_down?: unknown;
  interface?: unknown;
  flag?: unknown;
  latency_ms?: unknown;
  status_since?: unknown;
}

function asString(v: unknown): string | null {
  if (typeof v === "string") {
    const s = v.trim();
    return s === "" || s === "--" || s === "null" ? null : s;
  }
  return null;
}

function asNumber(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && v.trim() !== "--") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function normalizeEndpoint(raw: unknown, fallbackIp: string): Endpoint {
  const e = (raw ?? {}) as RawEndpoint;
  const ip = asString(e.ip) ?? fallbackIp;
  const lat = asNumber(e.lat);
  const lng = asNumber(e.lng);
  const locatable = !isPrivateIP(ip);
  return {
    ip,
    port: Math.max(0, Math.round(asNumber(e.port) ?? 0)),
    domain: asString(e.domain),
    lat: locatable ? lat : lat, // 内网坐标由后端环形布局给出，保留
    lng: locatable ? lng : lng,
  };
}

function hasCoord(e: Endpoint): boolean {
  return (
    e.lat != null &&
    e.lng != null &&
    Number.isFinite(e.lat) &&
    Number.isFinite(e.lng) &&
    !(e.lat === 0 && e.lng === 0)
  );
}

export interface NormalizeResult {
  flow: NetworkFlow | null;
  /** 地图可绘制（两端都有合法坐标） */
  mappable: boolean;
}

export function adaptPacket(raw: unknown): NormalizeResult {
  try {
    const p = (raw ?? {}) as RawPacket;

    const id = asString(p.id) ?? `pkt_${asNumber(p.seq) ?? Math.random()}`;
    const timestamp = asNumber(p.timestamp) ?? Date.now() / 1000;

    let direction = asString(p.direction);
    if (direction !== "outbound" && direction !== "inbound" && direction !== "internal") {
      // 后端已判定方向；缺失时按私有 IP 兜底，不作为常规路径
      const src = (p.source ?? {}) as RawEndpoint;
      const dst = (p.destination ?? {}) as RawEndpoint;
      const srcPriv = isPrivateIP(asString(src.ip));
      const dstPriv = isPrivateIP(asString(dst.ip));
      direction = srcPriv && dstPriv ? "internal" : dstPriv ? "inbound" : "outbound";
    }
    const dir: Direction =
      direction as Direction;

    const natRaw = (p.nat_info ?? {}) as Record<string, unknown>;
    const forwardAddr = asString(natRaw.forward_addr);

    const source = normalizeEndpoint(p.source, forwardAddr ?? "0.0.0.0");
    const destination = normalizeEndpoint(p.destination, "0.0.0.0");

    const upload = Math.max(0, asNumber(p.total_up) ?? 0);
    const download = Math.max(0, asNumber(p.total_down) ?? 0);

    const flagRaw = asString(p.flag);
    const flag =
      flagRaw === "failed" || flagRaw === "lost" || flagRaw === "high_latency"
        ? flagRaw
        : undefined;

    const latencyMs = asNumber(p.latency_ms);
    const statusSince = asNumber(p.status_since);

    const flow: NetworkFlow = {
      id,
      seq: Math.round(asNumber(p.seq) ?? 0),
      timestamp,
      born: asNumber(p.born) ?? timestamp,
      direction: dir,
      source,
      destination,
      application: asString(p.app_name) ?? "未知应用",
      protocol: (asString(p.protocol) ?? "tcp").toLowerCase(),
      status: asString(p.status),
      bytes: { upload, download, total: upload + download },
      nat:
        forwardAddr ||
        asNumber(natRaw.src_port) != null ||
        asNumber(natRaw.dst_port) != null ||
        asString(natRaw.original_dst)
          ? {
              forwardAddress: forwardAddr ?? undefined,
              sourcePort: asNumber(natRaw.src_port) ?? undefined,
              destinationPort: asNumber(natRaw.dst_port) ?? undefined,
              originalDestination: asString(natRaw.original_dst) ?? undefined,
            }
          : undefined,
      interface: asString(p.interface) ?? undefined,
      flag,
      latencyMs: latencyMs != null ? Math.max(0, latencyMs) : undefined,
      statusSince: statusSince ?? undefined,
    };

    return { flow, mappable: hasCoord(source) && hasCoord(destination) };
  } catch {
    return { flow: null, mappable: false };
  }
}
