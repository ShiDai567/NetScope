"use client";

import { useEffect, useRef, useState } from "react";
import { HudPanel } from "@/components/hud/HudPanel";
import { formatBytes, formatClock } from "@/lib/format";
import { cyber, directionColor } from "@/lib/theme";
import { EVENT_STREAM_VISIBLE, useNetworkStore } from "@/store/networkStore";

const DIR_BADGE: Record<string, string> = {
  outbound: "出站",
  inbound: "入站",
  internal: "内网",
};

const FLAG_LABEL: Record<string, string> = {
  failed: "失败",
  lost: "丢失",
  high_latency: "高延迟",
};

/** 底部实时事件流：新事件从顶部滑入，hover 暂停滚动 */
export function EventStream() {
  const events = useNetworkStore((s) => s.events);
  const selectFlow = useNetworkStore((s) => s.selectFlow);
  const [paused, setPaused] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const visible = paused ? events : events.slice(0, EVENT_STREAM_VISIBLE);

  // 新数据到达时回到顶部（非暂停态）
  const countRef = useRef(0);
  useEffect(() => {
    if (!paused && events.length > countRef.current) {
      listRef.current?.scrollTo({ top: 0 });
    }
    countRef.current = events.length;
  }, [events.length, paused]);

  return (
    <HudPanel
      title="实时网络事件"
      className="h-full min-h-0"
      bodyClassName="relative min-h-0"
      right={
        <span className="font-mono text-[9px] tracking-widest text-slate-600">
          {events.length} 条事件 · {paused ? "滚动已暂停" : "自动滚动"}
        </span>
      }
    >
      <div
        ref={listRef}
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        className="thin-scroll h-full max-h-full overflow-y-auto px-2 py-1"
      >
        {visible.length === 0 && (
          <p className="px-2 py-3 font-mono text-[10px] tracking-widest text-slate-600">
            暂无事件 —— 正在监听 …
          </p>
        )}
        <ul>
          {/* 倒序渲染：最新在上 */}
          {visible.map((ev, idx) => {
            const color = directionColor(ev.direction);
            const alert =
              ev.flag === "failed"
                ? cyber.red
                : ev.flag === "lost" || ev.flag === "high_latency"
                  ? cyber.amber
                  : null;
            return (
              <li
                key={ev.id}
                onClick={() => selectFlow(ev.id.split(":")[0] ?? null)}
                className={`flex cursor-pointer items-center gap-3 border-b border-white/[0.03] px-2 py-[5px] hover:bg-cyan-400/[0.05] ${
                  idx === 0 && !paused ? "event-in" : ""
                }`}
              >
                <time className="w-14 shrink-0 font-mono text-[10px] tabular-nums text-slate-500">
                  {formatClock(ev.timestamp)}
                </time>
                <span
                  className="w-8 shrink-0 text-center font-mono text-[10px]"
                  style={{ color }}
                >
                  {DIR_BADGE[ev.direction] ?? "···"}
                </span>
                <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-200">
                  {ev.source}
                  <span className="mx-1.5 text-slate-600">→</span>
                  {ev.destination}
                  <span className="ml-2 text-[9px] text-slate-500">
                    {ev.protocol.toUpperCase()}
                    {ev.port > 0 ? `/${ev.port}` : ""}
                  </span>
                  {ev.application !== "未知应用" && (
                    <span className="ml-2 hidden text-[9px] tracking-wide text-slate-600 lg:inline">
                      {ev.application}
                    </span>
                  )}
                </span>
                {alert && (
                  <span
                    className="shrink-0 font-mono text-[9px] tracking-[0.18em]"
                    style={{ color: alert }}
                  >
                    ⚠ {FLAG_LABEL[ev.flag ?? ""] ?? ""}
                  </span>
                )}
                <span className="w-16 shrink-0 text-right font-mono text-[10px] tabular-nums text-slate-400">
                  {formatBytes(ev.bytesTotal)}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </HudPanel>
  );
}
