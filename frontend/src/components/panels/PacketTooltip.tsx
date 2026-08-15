"use client";

import { useMemo } from "react";
import type { PacketEvent } from "@/lib/types";
import { fmtBytes, fmtTime } from "@/lib/format";
import { STATUS_COLORS, PROTOCOL_COLORS } from "@/lib/colors";

interface Props {
  hoveredId: string | null;
  lockedId: string | null;
  eventLogRef: React.RefObject<Map<string, PacketEvent[]> | null>;
  onLock: (id: string | null) => void;
  mousePos: { x: number; y: number };
}

export default function PacketTooltip({
  hoveredId,
  lockedId,
  eventLogRef,
  onLock,
  mousePos,
}: Props) {
  const packet = useMemo(() => {
    const id = hoveredId || lockedId;
    if (!id) return null;
    const arr = eventLogRef.current?.get(id);
    return arr?.[arr.length - 1] ?? null;
  }, [hoveredId, lockedId, eventLogRef]);

  if (!packet) return null;

  const isLocked = lockedId === packet.id;
  const statusColor = packet.status ? STATUS_COLORS[packet.status] : "#94a3b8";
  const protoColor = PROTOCOL_COLORS[packet.protocol] || "#94a3b8";

  const left = Math.min(mousePos.x + 16, typeof window !== "undefined" ? window.innerWidth - 320 : mousePos.x);
  const top = Math.min(mousePos.y + 16, typeof window !== "undefined" ? window.innerHeight - 300 : mousePos.y);

  return (
    <div
      className="pointer-events-auto absolute z-40"
      style={{ left, top }}
    >
      <div className="w-72 rounded-lg border border-cyan-400/20 bg-[#03050a]/95 p-3 shadow-2xl backdrop-blur-md">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold text-cyan-400">
            {packet.app_name}
          </span>
          <button
            onClick={() => onLock(isLocked ? null : packet.id)}
            className={`rounded px-2 py-0.5 text-[10px] ${
              isLocked
                ? "bg-cyan-400/20 text-cyan-400"
                : "bg-base-700 text-slate-400 hover:text-slate-200"
            }`}
          >
            {isLocked ? "取消锁定" : "锁定跟踪"}
          </button>
        </div>

        <div className="space-y-1 text-[11px]">
          <Row label="源地址" value={`${packet.source.ip}:${packet.source.port}`} />
          <Row label="目的地址" value={`${packet.destination.ip}:${packet.destination.port}`} />
          {packet.source.domain && (
            <Row label="源域名" value={packet.source.domain} />
          )}
          {packet.destination.domain && (
            <Row label="目的域名" value={packet.destination.domain} />
          )}
          <div className="flex gap-2">
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-mono"
              style={{ background: `${protoColor}20`, color: protoColor }}
            >
              {packet.protocol.toUpperCase()}
            </span>
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-mono"
              style={{ background: `${statusColor}20`, color: statusColor }}
            >
              {packet.status || "无状态"}
            </span>
            <span className="rounded bg-base-700 px-1.5 py-0.5 text-[10px] text-slate-400">
              {packet.direction === "outbound"
                ? "向外"
                : packet.direction === "inbound"
                ? "向内"
                : "内网"}
            </span>
          </div>
          <Row
            label="Payload"
            value={`↑ ${fmtBytes(packet.total_up)} / ↓ ${fmtBytes(
              packet.total_down
            )}`}
          />
          <Row
            label="NAT"
            value={`${packet.nat_info.forward_addr}:${packet.nat_info.src_port} → ${packet.nat_info.dst_port}`}
          />
          {packet.nat_info.original_dst && (
            <Row label="原始目标" value={packet.nat_info.original_dst} />
          )}
          <Row label="时间戳" value={fmtTime(packet.timestamp)} />
          {packet.latency_ms !== undefined && (
            <Row label="延迟" value={`${packet.latency_ms} ms`} />
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-slate-300">{value}</span>
    </div>
  );
}
