"use client";

import { useEffect, useState } from "react";
import { StatusIndicator } from "@/components/hud/StatusIndicator";
import { formatDateTime } from "@/lib/format";
import { cyber } from "@/lib/theme";
import { useNetworkStore } from "@/store/networkStore";

/** 顶部 HUD：系统状态 / 标题 / LIVE 时钟 / 数据链路 */
export function Header() {
  const [now, setNow] = useState<Date | null>(null);
  const connState = useNetworkStore((s) => s.connState);
  const apiError = useNetworkStore((s) => s.apiError);
  const mode = useNetworkStore((s) => s.mode);

  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const streamColor =
    connState === "connected"
      ? cyber.mint
      : connState === "connecting"
        ? cyber.amber
        : cyber.red;
  const streamLabel =
    connState === "connected"
      ? "已连接"
      : connState === "connecting"
        ? "同步中 ..."
        : "重连中 ...";

  return (
    <header className="relative z-20 flex h-[64px] shrink-0 items-center justify-between border-b border-cyan-400/10 bg-gradient-to-r from-[#020611] via-[#061021]/90 to-[#020611] px-4">
      {/* 左：系统状态 */}
      <div className="flex w-64 flex-col gap-1.5">
        <StatusIndicator color={cyber.mint} label="系统在线" />
        <StatusIndicator
          color={apiError ? cyber.red : cyber.textDim}
          label={
            apiError ? "API 连接错误" : `数据源 · ${mode === "ikuai" ? "iKuai" : "模拟"}`
          }
          pulse={!!apiError}
          size="sm"
        />
      </div>

      {/* 中：标题 + LIVE 时钟 */}
      <div className="pointer-events-none absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-5">
        <p className="hidden font-mono text-[9px] tracking-[0.34em] text-slate-500 md:block">
          实时网络流量态势感知
        </p>
        <div className="text-center leading-tight">
          <h1 className="whitespace-nowrap font-display text-xl font-semibold tracking-[0.3em] text-cyan-50 md:text-2xl">
            全球网络智能中心
          </h1>
          <p className="mt-0.5 whitespace-nowrap font-mono text-[8px] tracking-[0.42em] text-cyan-300/60">
            GLOBAL NETWORK INTELLIGENCE CENTER
          </p>
        </div>
        <div className="hidden flex-col items-start gap-1 border-l border-cyan-400/15 pl-5 md:flex">
          <span className="inline-flex items-center gap-1.5">
            <i className="pulse-dot h-1.5 w-1.5 rounded-full bg-red-500 text-red-500" />
            <span className="font-mono text-[10px] tracking-[0.3em] text-red-400">
              LIVE
            </span>
          </span>
          <time className="font-mono text-[11px] tabular-nums tracking-widest text-slate-400">
            {now ? formatDateTime(now) : "---------- --:--:--"}
          </time>
        </div>
      </div>

      {/* 右：数据链路 */}
      <div className="flex w-64 flex-col items-end gap-1.5">
        <StatusIndicator
          color={streamColor}
          label={`数据链路 · ${streamLabel}`}
        />
        <span className="font-mono text-[10px] tracking-[0.22em] text-slate-600">
          {mode === "ikuai" ? "iKuai 路由器直连" : "模拟数据流"}
        </span>
      </div>

      {/* 底部装饰线 */}
      <div
        aria-hidden
        className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent"
      />
    </header>
  );
}
