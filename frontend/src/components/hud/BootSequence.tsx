"use client";

import { useEffect, useRef, useState } from "react";
import { cyber } from "@/lib/theme";
import { useNetworkStore } from "@/store/networkStore";

const STEPS = [
  "连接 Django API ...",
  "建立 WebSocket 链路 ...",
  "加载地理引擎 ...",
  "加载网络节点 ...",
  "开启数据包监听 ...",
];

/**
 * 系统启动动画：约 1.6s，完成后 Fade In 进入主界面。
 * 纯展示层，不阻塞真实数据加载。
 */
export function BootSequence() {
  const booted = useNetworkStore((s) => s.booted);
  const setBooted = useNetworkStore((s) => s.setBooted);
  const [visible, setVisible] = useState(true);
  const [progress, setProgress] = useState(0);
  const [stepIdx, setStepIdx] = useState(0);
  const doneRef = useRef(false);

  useEffect(() => {
    const start = performance.now();
    const total = 1550;
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / total);
      setProgress(p);
      setStepIdx(Math.min(STEPS.length - 1, Math.floor(p * STEPS.length)));
      if (p < 1) {
        raf = requestAnimationFrame(step);
      } else if (!doneRef.current) {
        doneRef.current = true;
        setBooted(true);
        setTimeout(() => setVisible(false), 650); // fade out
      }
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [setBooted]);

  if (!visible) return null;

  const pct = Math.round(progress * 100);
  const done = progress >= 1;

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#020611] transition-opacity duration-600 ${
        done ? "opacity-0" : "opacity-100"
      }`}
      aria-hidden={done}
    >
      <div className="w-72">
        <p className="font-mono text-[11px] tracking-[0.42em] text-cyan-200">
          正在初始化网络核心 ...
        </p>

        <div className="mt-5 h-5 space-y-1">
          {!done ? (
            STEPS.slice(0, stepIdx + 1).map((s) => (
              <p
                key={s}
                className="fade-up font-mono text-[10px] tracking-[0.2em] text-slate-500"
              >
                {s}
              </p>
            ))
          ) : (
            <p className="fade-up font-mono text-[11px] tracking-[0.34em]" style={{ color: cyber.mint }}>
              系统在线
            </p>
          )}
        </div>

        <div className="mt-5 flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden border border-cyan-400/25">
            <div
              className="h-full origin-left bg-gradient-to-r from-cyan-500 to-mint-300"
              style={{
                transform: `scaleX(${progress})`,
                background: `linear-gradient(90deg, ${cyber.blue}, ${cyber.mint})`,
              }}
            />
          </div>
          <span className="w-10 text-right font-mono text-[11px] tabular-nums text-cyan-200">
            {pct}%
          </span>
        </div>
      </div>

      {/* 背景网格 */}
      <div aria-hidden className="bg-grid-faint absolute inset-0 -z-10 opacity-60" />
    </div>
  );
}
