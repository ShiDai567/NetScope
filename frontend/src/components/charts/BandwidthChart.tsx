"use client";

import { useEffect, useRef } from "react";
import { cyber } from "@/lib/theme";
import type { BandwidthSeriesPoint } from "@/lib/types";
import { useNetworkStore } from "@/store/networkStore";

/**
 * 带宽趋势图（自绘 Canvas，无图表库依赖）。
 * 上行=青色填充，下行=紫色描边；60FPS 平滑滚动。
 */
export function BandwidthChart({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const seriesRef = useRef<BandwidthSeriesPoint[]>([]);

  // 订阅 store（统计 2s 一拍）
  useEffect(() => {
    const unsub = useNetworkStore.subscribe((state) => {
      if (state.stats) {
        seriesRef.current = state.stats.bandwidth.series;
      }
    });
    return unsub;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width < 10 || rect.height < 10) {
        raf = requestAnimationFrame(draw);
        return;
      }
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(rect.width);
      const h = Math.round(rect.height);
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const pad = { l: 4, r: 4, t: 8, b: 12 };
      const iw = w - pad.l - pad.r;
      const ih = h - pad.t - pad.b;

      // 网格
      ctx.strokeStyle = "rgba(120,150,200,0.08)";
      ctx.lineWidth = 1;
      for (let gy = 0; gy <= 3; gy++) {
        const y = pad.t + (ih * gy) / 3;
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(w - pad.r, y);
        ctx.stroke();
      }

      const series = seriesRef.current.slice(-60);
      if (series.length >= 2) {
        let maxV = 1;
        for (const p of series) {
          if (p.upBps > maxV) maxV = p.upBps;
          if (p.downBps > maxV) maxV = p.downBps;
        }
        maxV *= 1.15;

        const px = (i: number) =>
          pad.l + (iw * i) / Math.max(1, series.length - 1);
        const py = (v: number) => pad.t + ih - (ih * v) / maxV;

        // 上行：渐变填充
        const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + ih);
        grad.addColorStop(0, `${cyber.cyan}30`);
        grad.addColorStop(1, `${cyber.cyan}00`);
        ctx.beginPath();
        ctx.moveTo(px(0), py(series[0]?.upBps ?? 0));
        for (let i = 1; i < series.length; i++) {
          ctx.lineTo(px(i), py(series[i]?.upBps ?? 0));
        }
        ctx.lineTo(px(series.length - 1), pad.t + ih);
        ctx.lineTo(px(0), pad.t + ih);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();

        // 上行线
        ctx.beginPath();
        for (let i = 0; i < series.length; i++) {
          const p = series[i];
          if (!p) continue;
          if (i === 0) ctx.moveTo(px(i), py(p.upBps));
          else ctx.lineTo(px(i), py(p.upBps));
        }
        ctx.strokeStyle = cyber.cyan;
        ctx.lineWidth = 1.4;
        ctx.globalAlpha = 0.9;
        ctx.stroke();
        ctx.globalAlpha = 1;

        // 下行线
        ctx.beginPath();
        for (let i = 0; i < series.length; i++) {
          const p = series[i];
          if (!p) continue;
          if (i === 0) ctx.moveTo(px(i), py(p.downBps));
          else ctx.lineTo(px(i), py(p.downBps));
        }
        ctx.strokeStyle = cyber.purple;
        ctx.lineWidth = 1.2;
        ctx.globalAlpha = 0.75;
        ctx.setLineDash([4, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;

        // 最新点光标
        const lastUp = series[series.length - 1]?.upBps ?? 0;
        const lx = px(series.length - 1);
        const ly = py(lastUp);
        if (!reduced) {
          const t = (performance.now() % 1600) / 1600;
          ctx.beginPath();
          ctx.arc(lx, ly, 2 + t * 6, 0, Math.PI * 2);
          ctx.strokeStyle = cyber.cyan;
          ctx.globalAlpha = (1 - t) * 0.5;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
        ctx.beginPath();
        ctx.arc(lx, ly, 2, 0, Math.PI * 2);
        ctx.fillStyle = "#fff";
        ctx.fill();
      } else {
        ctx.fillStyle = "rgba(143,163,191,0.4)";
        ctx.font = "9px ui-monospace, monospace";
        ctx.fillText("AWAITING SAMPLES", pad.l + 4, pad.t + ih / 2);
      }

      // 图例
      ctx.font = "8px ui-monospace, monospace";
      ctx.fillStyle = cyber.cyan;
      ctx.globalAlpha = 0.7;
      ctx.fillText("UP", pad.l + 2, h - 3);
      ctx.fillStyle = cyber.purple;
      ctx.fillText("DOWN", pad.l + 20, h - 3);
      ctx.globalAlpha = 1;

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
