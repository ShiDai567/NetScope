"use client";

import { ConnectionDetails } from "@/components/details/ConnectionDetails";
import { EventStream } from "@/components/events/EventStream";
import { BootSequence } from "@/components/hud/BootSequence";
import { Header } from "@/components/hud/Header";
import { SceneSwitcher } from "@/components/hud/SceneSwitcher";
import { StatusIndicator } from "@/components/hud/StatusIndicator";
import { MapStage } from "@/components/map/MapStage";
import { MetricsPanel } from "@/components/panels/MetricsPanel";
import { MonitorPanel } from "@/components/panels/MonitorPanel";
import { RankingsBar } from "@/components/panels/RankingsBar";
import { useNetworkStream } from "@/hooks/useNetworkStream";
import { cyber } from "@/lib/theme";
import { useNetworkStore } from "@/store/networkStore";

/**
 * 全局布局（AGENTS.md §80）：
 *
 * ┌──────────────────────────────────────────────┐
 * │ HEADER                                       │
 * ├────────┬─────────────────────────┬───────────┤
 * │ METRICS│        MAP STAGE        │  MONITOR  │
 * ├────────┴─────────────────────────┴───────────┤
 * │ REAL-TIME EVENTS                             │
 * ├──────────────────────────────────────────────┤
 * │ RANKINGS                                     │
 * └──────────────────────────────────────────────┘
 */
export function Dashboard() {
  useNetworkStream();
  const connState = useNetworkStore((s) => s.connState);
  const booted = useNetworkStore((s) => s.booted);

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-[#020611]">
      {/* 背景层：网格 + 扫描线 */}
      <div aria-hidden className="bg-grid-faint pointer-events-none absolute inset-0" />
      <div aria-hidden className="bg-scanlines pointer-events-none absolute inset-0 z-40" />

      <Header />

      <main className="flex min-h-0 flex-1 gap-3 p-3">
        {/* 左：指标 */}
        <div className="hidden w-[286px] shrink-0 xl:block">
          <MetricsPanel />
        </div>

        {/* 中：地图舞台 */}
        <div className="relative min-w-0 flex-1 border border-cyan-400/10 bg-[#030910]/60">
          <MapStage />

          {/* 场景切换（地图上方居中） */}
          <div className="pointer-events-none absolute left-1/2 top-3 z-20 -translate-x-1/2">
            <SceneSwitcher />
          </div>

          {/* 断线横幅 */}
          {connState !== "connected" && (
            <div className="absolute left-1/2 top-14 z-30 -translate-x-1/2 border border-red-400/40 bg-[#140608]/90 px-4 py-2 text-center backdrop-blur-sm">
              <StatusIndicator
                color={cyber.red}
                label={
                  connState === "connecting"
                    ? "正在建立数据链路 ..."
                    : "数据链路断开 · 正在重连 ..."
                }
              />
            </div>
          )}

          <ConnectionDetails />
        </div>

        {/* 右：监控 */}
        <div className="hidden w-[262px] shrink-0 lg:block">
          <MonitorPanel />
        </div>
      </main>

      {/* 底部：事件流 + 排名（等高布局） */}
      <section className="flex h-[172px] shrink-0 gap-3 px-3 pb-3">
        <div className="h-full min-h-0 min-w-0 flex-[5]">
          <EventStream />
        </div>
        <div className="hidden h-full min-h-0 min-w-0 flex-[4] md:block">
          <RankingsBar />
        </div>
      </section>

      {!booted && <BootSequence />}
    </div>
  );
}
