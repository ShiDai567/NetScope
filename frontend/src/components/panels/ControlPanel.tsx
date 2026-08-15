"use client";

import { ArrowsHorizontal, ArrowRight, ArrowLeft, ArrowsInLineHorizontal } from "@phosphor-icons/react";
import type { DirectionFilter, ProtocolFilter } from "@/lib/types";

interface Props {
  filters: { direction: DirectionFilter; protocol: ProtocolFilter; app: string };
  onFilterChange: (key: "direction" | "protocol" | "app", value: string) => void;
}

const directions: { key: DirectionFilter; label: string; icon: React.ReactNode }[] = [
  { key: "all", label: "全部", icon: <ArrowsInLineHorizontal size={14} /> },
  { key: "outbound", label: "向外发包", icon: <ArrowRight size={14} /> },
  { key: "inbound", label: "向内接受", icon: <ArrowLeft size={14} /> },
    { key: "internal", label: "内网通信", icon: <ArrowsHorizontal size={14} /> },
];

const protocols: { key: ProtocolFilter; label: string; color: string }[] = [
  { key: "all", label: "全部", color: "#94a3b8" },
  { key: "tcp", label: "TCP", color: "#38bdf8" },
  { key: "udp", label: "UDP", color: "#34d399" },
  { key: "icmp", label: "ICMP", color: "#fbbf24" },
];

const apps = ["all", "DNS", "SMB", "SSL", "HTTP", "HTTPS", "其他"];

export default function ControlPanel({ filters, onFilterChange }: Props) {
  return (
    <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
      <h3 className="mb-2 text-xs font-semibold tracking-wider text-cyan-400">
        实时控制面板
      </h3>

      {/* 方向筛选 */}
      <div className="mb-3 grid grid-cols-2 gap-1.5">
        {directions.map((d) => (
          <button
            key={d.key}
            onClick={() => onFilterChange("direction", d.key)}
            className={`flex items-center justify-center gap-1 rounded px-2 py-1.5 text-[11px] transition-colors ${
              filters.direction === d.key
                ? "bg-cyan-400/15 text-cyan-400"
                : "bg-base-800/60 text-slate-400 hover:text-slate-200"
            }`}
          >
            {d.icon}
            {d.label}
          </button>
        ))}
      </div>

      {/* 协议筛选 */}
      <div className="mb-3 flex gap-1">
        {protocols.map((p) => (
          <button
            key={p.key}
            onClick={() => onFilterChange("protocol", p.key)}
            className={`flex-1 rounded px-1.5 py-1 text-[11px] transition-colors ${
              filters.protocol === p.key
                ? "bg-cyan-400/15 text-cyan-400"
                : "bg-base-800/60 text-slate-400 hover:text-slate-200"
            }`}
          >
            <span
              className="mr-1 inline-block h-1.5 w-1.5 rounded-full"
              style={{ background: p.color }}
            />
            {p.label}
          </button>
        ))}
      </div>

      {/* 应用筛选 */}
      <div className="flex flex-wrap gap-1">
        {apps.map((a) => (
          <button
            key={a}
            onClick={() => onFilterChange("app", a)}
            className={`rounded px-2 py-0.5 text-[10px] transition-colors ${
              filters.app === a
                ? "bg-cyan-400/15 text-cyan-400"
                : "bg-base-800/60 text-slate-500 hover:text-slate-300"
            }`}
          >
            {a === "all" ? "全部应用" : a}
          </button>
        ))}
      </div>
    </div>
  );
}
