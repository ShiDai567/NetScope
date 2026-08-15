"use client";

import { Play, Pause, SkipBack, SkipForward } from "@phosphor-icons/react";

interface Props {
  replay: {
    active: boolean;
    clock: number;
    speed: number;
    paused: boolean;
    rangeStart: number;
    rangeEnd: number;
  };
  serverTime: number;
  onEnterReplay: (minutes?: number) => void;
  onExitReplay: () => void;
  onSpeedChange: (speed: number) => void;
  onTogglePause: () => void;
  onSeek: (clock: number) => void;
}

export default function TimelineBar({
  replay,
  serverTime,
  onEnterReplay,
  onExitReplay,
  onSpeedChange,
  onTogglePause,
  onSeek,
}: Props) {
  const isLive = !replay.active;

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString("zh-CN", { hour12: false });
  };

  const progress = replay.active
    ? ((replay.clock - replay.rangeStart) /
        Math.max(1, replay.rangeEnd - replay.rangeStart)) *
      100
    : 100;

  return (
    <div className="flex items-center gap-3 border-t border-cyan-400/10 bg-[#03050a]/85 px-4 py-2 backdrop-blur-md">
      {/* LIVE / 回放 切换 */}
      <button
        onClick={() => (isLive ? onEnterReplay(10) : onExitReplay())}
        className={`rounded px-2.5 py-1 text-[10px] font-bold tracking-wider transition-colors ${
          isLive
            ? "bg-rose-500/15 text-rose-400"
            : "bg-cyan-400/15 text-cyan-400"
        }`}
      >
        {isLive ? "LIVE" : "回放"}
      </button>

      {!isLive && (
        <>
          <button
            onClick={onTogglePause}
            className="rounded p-1 text-slate-300 hover:text-cyan-400"
          >
            {replay.paused ? <Play size={16} /> : <Pause size={16} />}
          </button>

          <div className="flex gap-0.5">
            {[0.5, 1, 2, 5].map((s) => (
              <button
                key={s}
                onClick={() => onSpeedChange(s)}
                className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${
                  replay.speed === s
                    ? "bg-cyan-400/15 text-cyan-400"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          <span className="w-20 text-right text-[10px] font-mono text-slate-400">
            {formatTime(replay.clock)}
          </span>
        </>
      )}

      {/* 时间滑块 */}
      <div className="relative flex-1">
        <input
          type="range"
          min={replay.active ? replay.rangeStart : serverTime - 600}
          max={replay.active ? replay.rangeEnd : serverTime}
          step={1}
          value={replay.active ? replay.clock : serverTime}
          onChange={(e) => {
            const val = Number(e.target.value);
            if (isLive) onEnterReplay(10);
            onSeek(val);
          }}
          className="h-1 w-full cursor-pointer appearance-none rounded-full bg-base-700 accent-cyan-400"
        />
        <div
          className="pointer-events-none absolute left-0 top-0 h-1 rounded-full bg-cyan-400/40"
          style={{ width: `${progress}%` }}
        />
      </div>

      {!isLive && (
        <span className="w-20 text-[10px] font-mono text-slate-500">
          {formatTime(replay.rangeEnd)}
        </span>
      )}
    </div>
  );
}
