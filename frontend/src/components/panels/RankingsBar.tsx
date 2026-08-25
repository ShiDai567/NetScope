"use client";

import { useMemo, useState } from "react";
import { HudPanel } from "@/components/hud/HudPanel";
import { useWindowedFlows } from "@/hooks/useWindowedFlows";
import { formatBytes, formatCount } from "@/lib/format";
import { isPrivateIP } from "@/lib/network/isPrivateIp";
import { cyber } from "@/lib/theme";
import type { Endpoint, TimeWindow } from "@/lib/types";
import { useNetworkStore } from "@/store/networkStore";

type RankTab = "regions" | "ips" | "ports" | "apps" | "protocols";

const TABS: { id: RankTab; label: string }[] = [
  { id: "regions", label: "区域" },
  { id: "ips", label: "来源 IP" },
  { id: "ports", label: "端口" },
  { id: "apps", label: "应用" },
  { id: "protocols", label: "协议" },
];

const TIME_WINDOWS: TimeWindow[] = [5, 30, 60, 300, 900, 3600];
const WINDOW_LABEL: Record<TimeWindow, string> = {
  5: "5S",
  30: "30S",
  60: "1M",
  300: "5M",
  900: "15M",
  3600: "1H",
};

/** 与后端 classify_region 相同的地理框规则（前端只做展示聚合，不重判方向） */
function regionOf(direction: string, src: Endpoint, dst: Endpoint): string {
  const peer =
    direction === "outbound" ? dst : direction === "inbound" ? src : dst;
  if (direction === "internal" || isPrivateIP(peer.ip)) return "内网";
  const { lat, lng } = peer;
  if (lat == null || lng == null) return "未知";
  if (lng >= 73 && lng <= 135 && lat >= 18 && lat <= 53) return "中国";
  if (lng >= 60 && lng <= 180 && lat >= -15 && lat <= 55) return "亚太";
  if (lng >= -170 && lng <= -50 && lat >= 15 && lat <= 75) return "北美";
  if (lng >= -15 && lng <= 60 && lat >= 35 && lat <= 72) return "欧洲";
  return "其他";
}

interface RankRow {
  key: string;
  sub?: string;
  count: number;
  bytes: number;
  color?: string;
}

/** 底部排名条：时间窗口 + 五个维度的实时 Top 榜 */
export function RankingsBar() {
  const [tab, setTab] = useState<RankTab>("regions");
  const timeWindow = useNetworkStore((s) => s.timeWindow);
  const setTimeWindow = useNetworkStore((s) => s.setTimeWindow);
  const flows = useWindowedFlows();

  const rows: RankRow[] = useMemo(() => {
    switch (tab) {
      case "regions": {
        const m = new Map<string, RankRow>();
        for (const f of flows) {
          const r = regionOf(f.direction, f.source, f.destination);
          const cur = m.get(r) ?? { key: r, count: 0, bytes: 0 };
          cur.count += 1;
          cur.bytes += f.bytes.total;
          m.set(r, cur);
        }
        return sortRows(m);
      }
      case "ips": {
        const m = new Map<string, RankRow>();
        for (const f of flows) {
          // TOP SOURCE：outbound 取内网设备，inbound 取公网来源
          const ip =
            f.direction === "inbound"
              ? f.source.ip
              : (f.nat?.forwardAddress ?? f.source.ip);
          const isPriv = isPrivateIP(ip);
          const k = `${ip}`;
          const cur = m.get(k) ?? {
            key: ip,
            sub: isPriv ? "内网设备" : "公网",
            count: 0,
            bytes: 0,
            color: isPriv ? cyber.green : cyber.purple,
          };
          cur.count += 1;
          cur.bytes += f.bytes.total;
          m.set(k, cur);
        }
        return sortRows(m);
      }
      case "ports": {
        const m = new Map<string, RankRow>();
        for (const f of flows) {
          if (f.destination.port <= 0) continue;
          const k = String(f.destination.port);
          const cur = m.get(k) ?? { key: k, count: 0, bytes: 0 };
          cur.count += 1;
          cur.bytes += f.bytes.total;
          m.set(k, cur);
        }
        return sortRows(m);
      }
      case "apps": {
        const m = new Map<string, RankRow>();
        for (const f of flows) {
          const k = f.application || "未知";
          const cur = m.get(k) ?? { key: k, count: 0, bytes: 0 };
          cur.count += 1;
          cur.bytes += f.bytes.total;
          m.set(k, cur);
        }
        return sortRows(m);
      }
      case "protocols": {
        const m = new Map<string, RankRow>();
        for (const f of flows) {
          const k = f.protocol.toUpperCase();
          const cur = m.get(k) ?? {
            key: k,
            count: 0,
            bytes: 0,
            color: cyber.cyan,
          };
          cur.count += 1;
          cur.bytes += f.bytes.total;
          m.set(k, cur);
        }
        return sortRows(m);
      }
    }
  }, [tab, flows]);

  const maxCount = Math.max(1, ...rows.map((r) => r.count));

  return (
    <HudPanel
      title="实时排行"
      className="h-full min-h-0"
      right={
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] tracking-widest text-slate-600">
            窗口
          </span>
          <div className="flex border border-cyan-400/15">
            {TIME_WINDOWS.map((tw) => (
              <button
                key={tw}
                onClick={() => setTimeWindow(tw)}
                className={`px-1.5 py-0.5 font-mono text-[9px] tracking-wider transition-colors duration-150 ${
                  tw === timeWindow
                    ? "bg-cyan-400/15 text-cyan-200"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {WINDOW_LABEL[tw]}
              </button>
            ))}
          </div>
        </div>
      }
    >
      <div className="flex h-full min-h-0 flex-col">
        {/* 维度切换 */}
        <div className="flex shrink-0 items-center gap-4 border-b border-cyan-400/10 px-3 py-1.5">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`font-mono text-[9px] tracking-[0.22em] transition-colors duration-150 ${
                tab === t.id
                  ? "border-b border-cyan-300 pb-0.5 text-cyan-200"
                  : "pb-0.5 text-slate-500 hover:text-slate-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* 行 */}
        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-3 py-1.5">
          {rows.length === 0 ? (
            <p className="py-2 font-mono text-[10px] tracking-widest text-slate-600">
              正在等待网络数据 …
            </p>
          ) : (
            rows.slice(0, 8).map((r, idx) => (
              <div
                key={r.key}
                className="flex w-full items-center gap-3 py-[3px]"
              >
                <span className="w-5 shrink-0 font-mono text-[9px] text-slate-600">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <span
                  className="w-44 shrink-0 truncate font-mono text-[11px]"
                  style={{ color: r.color ?? "#CBD5E1" }}
                >
                  {r.key}
                  {r.sub && (
                    <span className="ml-2 text-[8px] tracking-widest text-slate-600">
                      {r.sub}
                    </span>
                  )}
                </span>
                <div className="h-1 flex-1 overflow-hidden bg-slate-800/50">
                  <i
                    className="block h-full transition-all duration-700"
                    style={{
                      width: `${Math.max(2, (r.count / maxCount) * 100)}%`,
                      background:
                        r.color ?? `linear-gradient(90deg, ${cyber.blue}, ${cyber.cyan})`,
                    }}
                  />
                </div>
                <span className="w-14 shrink-0 text-right font-mono text-[10px] tabular-nums text-slate-400">
                  {formatBytes(r.bytes)}
                </span>
                <span className="w-12 shrink-0 text-right font-mono text-[10px] tabular-nums text-slate-500">
                  ×{formatCount(r.count)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </HudPanel>
  );
}

function sortRows(m: Map<string, RankRow>): RankRow[] {
  return Array.from(m.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, 24);
}
