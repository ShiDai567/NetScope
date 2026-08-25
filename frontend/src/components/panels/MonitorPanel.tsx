"use client";

import { HudPanel } from "@/components/hud/HudPanel";
import { NetworkRadar } from "@/components/panels/NetworkRadar";
import { useWindowedFlows } from "@/hooks/useWindowedFlows";
import { formatCount, formatMs, formatPercent } from "@/lib/format";
import { cyber } from "@/lib/theme";
import { useNetworkStore } from "@/store/networkStore";

/** 右侧：雷达 / 协议分布 / 网络健康 / 异常检测 */
export function MonitorPanel() {
  const stats = useNetworkStore((s) => s.stats);
  const windowFlows = useWindowedFlows();

  // 协议动态统计（真实数据，不写死）
  const protoCounts = new Map<string, number>();
  for (const f of windowFlows) {
    protoCounts.set(f.protocol, (protoCounts.get(f.protocol) ?? 0) + 1);
  }
  const protos = Array.from(protoCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const protoTotal = Math.max(1, windowFlows.length);

  // 健康度：由丢包率 / 失败率推导（不伪造攻击数据）
  const lossRate = stats?.lossRate ?? 0;
  const failRate =
    stats && stats.total > 0 ? (stats.failed / stats.total) * 100 : 0;
  const health = Math.max(60, Math.min(100, 100 - lossRate * 2.2 - failRate * 4));
  const healthState =
    health >= 97
      ? { label: "正常", color: cyber.mint }
      : health >= 90
        ? { label: "预警", color: cyber.amber }
        : { label: "严重", color: cyber.red };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <HudPanel
        title="网络雷达"
        right={
          <span className="font-mono text-[9px] tracking-widest" style={{ color: cyber.mint }}>
            ● 扫描中
          </span>
        }
        className="shrink-0"
      >
        <NetworkRadar className="mx-auto block aspect-square w-full max-w-[190px] p-1" />
      </HudPanel>

      <HudPanel title="协议分布 · 窗口" className="shrink-0">
        <div className="space-y-2 px-3 py-3">
          {protos.length === 0 && (
            <p className="py-1 font-mono text-[10px] tracking-widest text-slate-600">
              暂无协议数据
            </p>
          )}
          {protos.map(([name, count]) => (
            <div key={name} className="flex items-center gap-2">
              <span className="w-12 shrink-0 font-mono text-[10px] uppercase tracking-wider text-slate-300">
                {name}
              </span>
              <div className="h-1.5 flex-1 overflow-hidden bg-slate-800/60">
                <i
                  className="block h-full transition-all duration-500"
                  style={{
                    width: `${Math.max(2, (count / protoTotal) * 100)}%`,
                    background: `linear-gradient(90deg, ${cyber.blue}, ${cyber.cyan})`,
                    boxShadow: `0 0 6px ${cyber.cyan}66`,
                  }}
                />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-[10px] tabular-nums text-slate-400">
                {formatPercent((count / protoTotal) * 100, 0)}
              </span>
            </div>
          ))}
        </div>
      </HudPanel>

      <HudPanel title="网络健康" className="shrink-0">
        <div className="flex items-center justify-between gap-3 px-3 py-3">
          <div className="relative h-16 w-16 shrink-0">
            <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
              <circle
                cx="32"
                cy="32"
                r="27"
                fill="none"
                stroke="rgba(255,255,255,0.06)"
                strokeWidth="5"
              />
              <circle
                cx="32"
                cy="32"
                r="27"
                fill="none"
                stroke={healthState.color}
                strokeWidth="5"
                strokeLinecap="round"
                strokeDasharray={`${(health / 100) * 169.6} 169.6`}
                style={{ transition: "stroke-dasharray 600ms ease-out" }}
              />
            </svg>
            <p
              className="absolute inset-0 flex items-center justify-center font-mono text-[13px] font-semibold tabular-nums"
              style={{ color: healthState.color }}
            >
              {health.toFixed(1)}
            </p>
          </div>
          <dl className="min-w-0 flex-1 space-y-1 font-mono text-[10px]">
            <div className="flex items-center justify-between">
              <dt className="tracking-wider text-slate-600">状态</dt>
              <dd style={{ color: healthState.color }}>{healthState.label}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="tracking-wider text-slate-600">丢包率</dt>
              <dd className="tabular-nums text-slate-300">
                {formatPercent(lossRate, 2)}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="tracking-wider text-slate-600">平均延迟</dt>
              <dd className="tabular-nums text-slate-300">
                {formatMs(stats?.avgLatencyMs)}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="tracking-wider text-slate-600">累计链路</dt>
              <dd className="tabular-nums text-slate-300">
                {formatCount(stats?.total)}
              </dd>
            </div>
          </dl>
        </div>
      </HudPanel>

      {/* 异常检测 —— 明确标记为模拟占位 */}
      <HudPanel title="异常检测" className="shrink-0 opacity-70">
        <div className="flex items-center justify-between px-3 py-2">
          <p className="font-mono text-[9px] tracking-[0.25em] text-slate-500">
            等待后端引擎接入
          </p>
          <span className="border border-amber-400/40 px-1.5 py-0.5 font-mono text-[8px] tracking-[0.2em] text-amber-400">
            模拟
          </span>
        </div>
      </HudPanel>
    </div>
  );
}
