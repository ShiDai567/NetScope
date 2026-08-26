"use client";

import { BandwidthChart } from "@/components/charts/BandwidthChart";
import { HudPanel } from "@/components/hud/HudPanel";
import { useWindowedFlows } from "@/hooks/useWindowedFlows";
import { formatCount, formatRate } from "@/lib/format";
import { cyber } from "@/lib/theme";
import { useNetworkStore } from "@/store/networkStore";
import type { Direction } from "@/lib/types";

const DIR_META: { key: Direction; label: string; color: string }[] = [
  { key: "outbound", label: "出站", color: cyber.cyan },
  { key: "inbound", label: "入站", color: cyber.purple },
  { key: "internal", label: "内网", color: cyber.green },
];

/** 左侧：CPU 负载 / 数据包 / 活跃连接 / 带宽趋势 */
export function MetricsPanel() {
  const stats = useNetworkStore((s) => s.stats);
  const windowFlows = useWindowedFlows();

  const up = stats?.bandwidth.upBps ?? 0;
  const down = stats?.bandwidth.downBps ?? 0;
  const cpu = stats?.system.cpuPercent ?? null;
  const mem = stats?.system.memoryPercent ?? null;

  // 窗口内方向计数（真实数据聚合）
  const dirCounts: Record<Direction, number> = {
    outbound: 0,
    inbound: 0,
    internal: 0,
  };
  for (const f of windowFlows) dirCounts[f.direction] += 1;
  const winTotal = Math.max(1, windowFlows.length);

  const loadColor = (v: number | null) =>
    v == null ? cyber.textSecondary : v >= 90 ? cyber.red : v >= 70 ? cyber.amber : cyber.mint;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <HudPanel
        title="CPU 负载"
        right={
          <span className="font-mono text-[8px] tracking-[0.24em] text-slate-600">
            CPU LOAD
          </span>
        }
        className="shrink-0"
      >
        <div className="space-y-2.5 px-3 py-3">
          <div className="flex items-end justify-between">
            <p
              className="font-mono text-3xl font-semibold leading-none tabular-nums"
              style={{ color: loadColor(cpu) }}
            >
              {cpu == null ? "--" : `${Math.round(cpu)}`}
              {cpu != null && <span className="text-base">%</span>}
            </p>
            <p className="font-mono text-[9px] leading-relaxed tracking-wider text-slate-600">
              iKUAI ROUTER
            </p>
          </div>
          <div className="h-1 overflow-hidden bg-slate-800/60">
            <i
              className="block h-full transition-all duration-700"
              style={{
                width: `${Math.max(2, cpu ?? 0)}%`,
                background: loadColor(cpu),
                boxShadow: `0 0 6px ${loadColor(cpu)}`,
              }}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="w-[52px] shrink-0 font-mono text-[10px] tracking-wider text-slate-500">
              内存
            </span>
            <div className="h-1 flex-1 overflow-hidden bg-slate-800/60">
              <i
                className="block h-full bg-violet-400/80 transition-all duration-700"
                style={{ width: `${Math.max(2, mem ?? 0)}%` }}
              />
            </div>
            <span className="w-10 shrink-0 text-right font-mono text-[10px] tabular-nums text-slate-400">
              {mem == null ? "--" : `${Math.round(mem)}%`}
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
          <span className="font-mono text-[9px] tabular-nums tracking-wider text-slate-500">
            <span style={{ color: cyber.cyan }}>↑ {formatRate(up / 8)}</span>
            {" · "}
            <span style={{ color: cyber.violet }}>↓ {formatRate(down / 8)}</span>
          </span>
        }
        className="min-h-[130px] flex-1"
        bodyClassName="relative"
      >
        <BandwidthChart className="absolute inset-0 h-full w-full" />
      </HudPanel>
    </div>
  );
}
