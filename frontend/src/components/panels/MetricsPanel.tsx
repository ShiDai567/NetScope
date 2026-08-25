"use client";

import { BandwidthChart } from "@/components/charts/BandwidthChart";
import { HudPanel } from "@/components/hud/HudPanel";
import { useWindowedFlows } from "@/hooks/useWindowedFlows";
import { formatBps, formatCount, formatRate } from "@/lib/format";
import { cyber } from "@/lib/theme";
import { useNetworkStore } from "@/store/networkStore";
import type { Direction } from "@/lib/types";

const DIR_META: { key: Direction; label: string; color: string }[] = [
  { key: "outbound", label: "出站", color: cyber.cyan },
  { key: "inbound", label: "入站", color: cyber.purple },
  { key: "internal", label: "内网", color: cyber.green },
];

/** 左侧：实时流量 / 数据包 / 活跃连接 / 带宽趋势 */
export function MetricsPanel() {
  const stats = useNetworkStore((s) => s.stats);
  const windowFlows = useWindowedFlows();

  const up = stats?.bandwidth.upBps ?? 0;
  const down = stats?.bandwidth.downBps ?? 0;

  // 窗口内方向计数（真实数据聚合）
  const dirCounts: Record<Direction, number> = {
    outbound: 0,
    inbound: 0,
    internal: 0,
  };
  for (const f of windowFlows) dirCounts[f.direction] += 1;
  const winTotal = Math.max(1, windowFlows.length);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <HudPanel
        title="网络流量"
        right={
          <span className="font-mono text-[8px] tracking-[0.24em] text-slate-600">
            TRAFFIC
          </span>
        }
        className="shrink-0"
      >
        <div className="space-y-2 px-3 py-3">
          <div className="flex items-baseline justify-between">
            <span className="flex items-center gap-2 font-mono text-[10px] tracking-widest text-slate-500">
              <span style={{ color: cyber.cyan }}>↑</span> 上行
            </span>
            <span
              className="font-mono text-xl font-semibold tabular-nums"
              style={{ color: cyber.cyan }}
            >
              {formatBps(up)}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="flex items-center gap-2 font-mono text-[10px] tracking-widest text-slate-500">
              <span style={{ color: cyber.purple }}>↓</span> 下行
            </span>
            <span
              className="font-mono text-xl font-semibold tabular-nums"
              style={{ color: cyber.violet }}
            >
              {formatBps(down)}
            </span>
          </div>
          <div className="mt-1 flex items-baseline justify-between border-t border-cyan-400/10 pt-2">
            <span className="font-mono text-[10px] tracking-widest text-slate-500">
              合计
            </span>
            <span className="font-mono text-sm font-semibold tabular-nums text-slate-200">
              {formatBps(up + down)}
            </span>
          </div>
        </div>
      </HudPanel>

      <HudPanel
        title="数据包 · 时间窗口"
        right={
          <span className="font-mono text-[8px] tracking-[0.24em] text-slate-600">
            PACKETS
          </span>
        }
        className="shrink-0"
      >
        <div className="px-3 py-3">
          <p className="font-mono text-2xl font-semibold tabular-nums text-cyan-50">
            {formatCount(windowFlows.length)}
          </p>
          <div className="mt-2.5 space-y-1.5">
            {DIR_META.map(({ key, label, color }) => (
              <div key={key} className="flex items-center gap-2">
                <span
                  className="w-[52px] shrink-0 font-mono text-[10px] tracking-wider"
                  style={{ color }}
                >
                  {label}
                </span>
                <div className="h-1 flex-1 overflow-hidden bg-slate-800/60">
                  <i
                    className="block h-full transition-all duration-500"
                    style={{
                      width: `${Math.max(2, (dirCounts[key] / winTotal) * 100)}%`,
                      background: color,
                      boxShadow: `0 0 6px ${color}`,
                    }}
                  />
                </div>
                <span className="w-12 shrink-0 text-right font-mono text-[10px] tabular-nums text-slate-400">
                  {formatCount(dirCounts[key])}
                </span>
              </div>
            ))}
          </div>
        </div>
      </HudPanel>

      <HudPanel
        title="活跃连接"
        right={
          <span className="font-mono text-[8px] tracking-[0.24em] text-slate-600">
            ACTIVE
          </span>
        }
        className="shrink-0"
      >
        <div className="flex items-end justify-between px-3 py-3">
          <p
            className="font-mono text-3xl font-semibold leading-none tabular-nums"
            style={{ color: cyber.mint }}
          >
            {stats ? formatCount(stats.active) : "--"}
          </p>
          <div className="text-right font-mono text-[9px] leading-relaxed tracking-wider text-slate-600">
            <p>已关闭 {stats ? formatCount(stats.closed) : "--"}</p>
            <p style={{ color: (stats?.failed ?? 0) > 0 ? cyber.red : undefined }}>
              失败 {stats ? formatCount(stats.failed) : "--"}
            </p>
          </div>
        </div>
      </HudPanel>

      <HudPanel
        title="带宽趋势"
        right={
          <span className="font-mono text-[8px] tracking-[0.24em] text-slate-600">
            BANDWIDTH
          </span>
        }
        className="min-h-[130px] flex-1"
        bodyClassName="relative"
      >
        <BandwidthChart className="absolute inset-0 h-full w-full" />
        <p className="pointer-events-none absolute bottom-1.5 right-2 font-mono text-[9px] tracking-widest text-slate-500">
          {formatRate(up / 8)} ↑ · {formatRate(down / 8)} ↓
        </p>
      </HudPanel>
    </div>
  );
}
