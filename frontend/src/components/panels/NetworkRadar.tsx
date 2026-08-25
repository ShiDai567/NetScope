"use client";

import { useEffect, useRef } from "react";
import { cyber, directionColor } from "@/lib/theme";
import { formatCount } from "@/lib/format";
import { useNetworkStore } from "@/store/networkStore";

/**
 * NETWORK RADAR —— 数据驱动：
 * 每个活跃公网端点按「相对网关的方位角 + 距离」映射为雷达光点，
 * 真实节点出现时触发检测脉冲。不生成任何假节点。
 */
export function NetworkRadar({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const detections = new Map<string, number>(); // key -> 首次出现时刻

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width < 10) {
        raf = requestAnimationFrame(draw);
        return;
      }
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const size = Math.min(Math.round(rect.width), Math.round(rect.height));
      if (canvas.width !== size * dpr || canvas.height !== size * dpr) {
        canvas.width = size * dpr;
        canvas.height = size * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size, size);

      const cx = size / 2;
      const cy = size / 2;
      const R = size / 2 - 6;
      const now = performance.now();

      // 刻度环
      for (let ring = 1; ring <= 3; ring++) {
        ctx.beginPath();
        ctx.arc(cx, cy, (R * ring) / 3, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,229,255,${ring === 3 ? 0.28 : 0.12})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(cx - R, cy);
      ctx.lineTo(cx + R, cy);
      ctx.moveTo(cx, cy - R);
      ctx.lineTo(cx, cy + R);
      ctx.strokeStyle = "rgba(0,229,255,0.08)";
      ctx.stroke();

      // 扫描扇区
      const sweepAngle = reduced ? -Math.PI / 4 : (now / 1400) % (Math.PI * 2);
      const wedges = 26;
      for (let i = 0; i < wedges; i++) {
        const a = sweepAngle - i * 0.045;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, R, a - 0.05, a + 0.005);
        ctx.closePath();
        ctx.fillStyle = `rgba(0,229,255,${(0.1 * (1 - i / wedges)).toFixed(3)})`;
        ctx.fill();
      }
      // 扫描前沿
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(sweepAngle) * R, cy + Math.sin(sweepAngle) * R);
      ctx.strokeStyle = `${cyber.cyan}CC`;
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // 光点：活跃公网端点
      const store = useNetworkStore.getState();
      const nowSec = Date.now() / 1000 + store.serverOffset;
      const g = store.gateway;
      const seen = new Set<string>();
      for (const f of store.flows) {
        if (nowSec - f.timestamp > 14) continue;
        const peer =
          f.direction === "outbound"
            ? f.destination
            : f.direction === "inbound"
              ? f.source
              : null;
        if (!peer || peer.lat == null || peer.lng == null) continue;
        if (seen.has(f.id)) continue;
        seen.add(f.id);

        // 方位角 + 归一化距离（对数压缩，近处不挤成一团）
        const dLng = peer.lng - g.lng;
        const dLat = peer.lat - g.lat;
        const angle = Math.atan2(dLat, dLng) - Math.PI / 2;
        const distDeg = Math.hypot(dLng * 0.7, dLat);
        const rNorm = Math.min(1, Math.log1p(distDeg) / Math.log1p(180));
        const bx = cx + Math.cos(angle) * rNorm * R;
        const by = cy + Math.sin(angle) * rNorm * R;

        const detKey = `${peer.ip}`;
        if (!detections.has(detKey)) detections.set(detKey, nowSec);
        const sinceDetect = nowSec - (detections.get(detKey) ?? nowSec);

        // 检测脉冲
        if (sinceDetect < 1.8 && !reduced) {
          const t = sinceDetect / 1.8;
          ctx.beginPath();
          ctx.arc(bx, by, 3 + t * 16, 0, Math.PI * 2);
          ctx.strokeStyle = cyber.mint;
          ctx.globalAlpha = (1 - t) * 0.7;
          ctx.lineWidth = 1;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }

        const color = directionColor(f.direction);
        const fresh = Math.max(0, 1 - (nowSec - f.timestamp) / 14);
        ctx.beginPath();
        ctx.arc(bx, by, 1.6 + fresh * 1.6, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.35 + fresh * 0.65;
        ctx.fill();
        ctx.globalAlpha = 1;
      }
      if (detections.size > 400) detections.clear();

      // 中心核心点
      ctx.beginPath();
      ctx.arc(cx, cy, 3, 0, Math.PI * 2);
      ctx.fillStyle = cyber.cyan;
      ctx.shadowColor = cyber.cyan;
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.shadowBlur = 0;

      // 计数
      ctx.font = "9px ui-monospace, monospace";
      ctx.fillStyle = "rgba(143,163,191,0.7)";
      ctx.textAlign = "center";
      ctx.fillText(`节点 ${formatCount(seen.size)}`, cx, size - 4);

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden />;
}
