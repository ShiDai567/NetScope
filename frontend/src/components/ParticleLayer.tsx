"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { DeviceInfo, PacketEvent, PublicNode } from "@/lib/types";
import {
  FLAG_COLORS,
  PROTOCOL_COLORS,
  STATUS_COLORS,
} from "@/lib/colors";

interface ParticleLayerProps {
  mapRef: React.RefObject<HTMLDivElement | null>;
  eventLogRef: React.RefObject<Map<string, PacketEvent[]> | null>;
  visiblePackets: Map<string, PacketEvent>;
  devices: DeviceInfo[];
  nodes: PublicNode[];
  hoveredId: string | null;
  lockedId: string | null;
  showNat: boolean;
  replayClock?: number;
  onHover: (id: string | null) => void;
  onLock: (id: string | null) => void;
  onMouseMove: (pos: { x: number; y: number }) => void;
  tick: number;
}

interface ParticleState {
  packet: PacketEvent;
  progress: number;
  screenPos: [number, number];
  prevPositions: [number, number][];
  born: number;
}

export default function ParticleLayer({
  mapRef,
  eventLogRef,
  visiblePackets,
  devices,
  nodes,
  hoveredId,
  lockedId,
  showNat,
  replayClock,
  onHover,
  onLock,
  onMouseMove,
}: ParticleLayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<Map<string, ParticleState>>(new Map());
  const mouseRef = useRef<{ x: number; y: number }>({ x: -1000, y: -1000 });
  const rafRef = useRef(0);
  const lastTimeRef = useRef(0);

  // 用 ref 保存高频变化的数据，避免 rAF 循环因 props 变化而重启
  const dataRef = useRef({
    visiblePackets,
    hoveredId,
    lockedId,
    showNat,
    replayClock,
    onHover,
  });
  useEffect(() => {
    dataRef.current = {
      visiblePackets,
      hoveredId,
      lockedId,
      showNat,
      replayClock,
      onHover,
    };
  });

  // 主渲染循环（只启动一次）
  useEffect(() => {
    const canvas = canvasRef.current;
    const mapEl = mapRef.current;
    if (!canvas || !mapEl) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const rect = mapEl.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = rect.width + "px";
      canvas.style.height = rect.height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const step = (now: number) => {
      const dt = lastTimeRef.current ? (now - lastTimeRef.current) / 1000 : 0.016;
      lastTimeRef.current = now;

      const rect = mapEl.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);

      const d = dataRef.current;
      const clock = d.replayClock ?? Date.now() / 1000;
      const particles = particlesRef.current;
      const chart = echarts.getInstanceByDom(mapEl);

      // 更新粒子状态
      for (const [id, state] of particles) {
        if (!d.visiblePackets.has(id)) {
          particles.delete(id);
          continue;
        }
      }
      for (const [id, packet] of d.visiblePackets) {
        let state = particles.get(id);
        if (!state) {
          state = {
            packet,
            progress: 0,
            screenPos: [0, 0],
            prevPositions: [],
            born: packet.born,
          };
          particles.set(id, state);
        } else {
          state.packet = packet;
        }
        updateParticle(state, dt, clock, chart, rect);
      }

      // 绘制 NAT 虚线（全部或仅锁定）
      if (d.showNat || d.lockedId) {
        for (const [id, state] of particles) {
          if (d.lockedId && id !== d.lockedId) continue;
          if (!d.showNat && id !== d.lockedId) continue;
          drawNatLine(ctx, state, chart, rect);
        }
      }

      // 绘制锁定路径高亮
      if (d.lockedId) {
        const locked = particles.get(d.lockedId);
        if (locked) drawLockedPath(ctx, locked, chart, rect);
      }

      // 绘制粒子
      for (const [id, state] of particles) {
        const dimOthers = d.lockedId !== null && id !== d.lockedId;
        drawParticle(ctx, state, dimOthers, id === d.hoveredId);
      }

      // 命中检测
      const hovered = findHovered(particles, mouseRef.current);
      if (hovered !== d.hoveredId) d.onHover(hovered);

      rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [mapRef]);

  return (
    <div className="absolute inset-0 z-20">
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0" />
      {/* 透明交互层：捕获鼠标事件但不阻挡 ECharts 地图交互 */}
      <div
        className="absolute inset-0"
        style={{ cursor: hoveredId ? "pointer" : "default" }}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
          mouseRef.current = pos;
          onMouseMove(pos);
        }}
        onMouseLeave={() => {
          mouseRef.current = { x: -1000, y: -1000 };
          onHover(null);
        }}
        onClick={() => {
          const hovered = findHovered(particlesRef.current, mouseRef.current);
          onLock(hovered);
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------
// 粒子更新
// ------------------------------------------------------------------

function updateParticle(
  state: ParticleState,
  dt: number,
  clock: number,
  chart: echarts.ECharts | null | undefined,
  rect: DOMRect
) {
  const p = state.packet;
  const src = geoToPixel(chart, [p.source.lng, p.source.lat], rect);
  const dst = geoToPixel(chart, [p.destination.lng, p.destination.lat], rect);
  if (!src || !dst) return;

  const age = clock - p.born;
  const status = p.status;
  const flag = p.flag;

  let t = state.progress;
  let speed = 0.18; // 基础飞行速度（进度/秒）

  if (p.protocol === "tcp") {
    if (status === "等待连接") {
      // 闪烁在源点附近
      t = 0;
      const breathe = Math.sin(age * 4) * 0.03;
      state.screenPos = [src[0] + breathe * 20, src[1] + breathe * 10];
    } else if (status === "请求连接") {
      t = Math.min(0.15, age * 0.25);
      const jitter = Math.sin(age * 12) * 3;
      const pt = arcPoint(src, dst, p.direction, t);
      state.screenPos = [pt[0] + jitter, pt[1] + jitter];
    } else if (status === "已连接") {
      t = Math.min(1, (age - 1.5) * speed);
      state.screenPos = arcPoint(src, dst, p.direction, t);
    } else if (status === "关闭连接") {
      t = Math.min(1, state.progress + dt * speed * 0.6);
      state.screenPos = arcPoint(src, dst, p.direction, t);
    }
  } else {
    // UDP / ICMP
    if (flag === "lost") {
      const dieAt = (p.status_since ?? p.born) + 0.5;
      const life = Math.max(0, dieAt - clock);
      t = Math.min(0.55, age * speed);
      state.screenPos = arcPoint(src, dst, p.direction, t);
    } else {
      t = Math.min(1, age * speed * 1.2);
      state.screenPos = arcPoint(src, dst, p.direction, t);
    }
  }

  state.progress = t;
  state.prevPositions.unshift([...state.screenPos]);
  if (state.prevPositions.length > 6) state.prevPositions.pop();
}

// ------------------------------------------------------------------
// 绘制
// ------------------------------------------------------------------

function drawParticle(
  ctx: CanvasRenderingContext2D,
  state: ParticleState,
  dim: boolean,
  isHovered: boolean
) {
  const p = state.packet;
  const [x, y] = state.screenPos;
  const color = particleColor(p);
  const size = particleSize(p);

  ctx.globalAlpha = dim ? 0.12 : isHovered ? 1.0 : 0.9;

  // 拖尾
  for (let i = 1; i < state.prevPositions.length; i++) {
    const [px, py] = state.prevPositions[i];
    const alpha = (1 - i / state.prevPositions.length) * 0.35;
    ctx.globalAlpha = dim ? 0.06 : alpha;
    ctx.beginPath();
    ctx.arc(px, py, size * (1 - i * 0.12), 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }

  ctx.globalAlpha = dim ? 0.15 : isHovered ? 1.0 : 0.92;

  // 外发光
  ctx.beginPath();
  ctx.arc(x, y, size * 2.5, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = isHovered ? 24 : 12;
  ctx.fill();
  ctx.shadowBlur = 0;

  // 核心
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();

  // 状态指示环
  if (p.status === "等待连接") {
    const ring = (Math.sin(Date.now() / 300) + 1) / 2;
    ctx.beginPath();
    ctx.arc(x, y, size + 4 + ring * 4, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2;
    ctx.stroke();
  }

  ctx.globalAlpha = 1;
}

function drawLockedPath(
  ctx: CanvasRenderingContext2D,
  state: ParticleState,
  chart: echarts.ECharts | null | undefined,
  rect: DOMRect
) {
  const p = state.packet;
  const src = geoToPixel(chart, [p.source.lng, p.source.lat], rect);
  const dst = geoToPixel(chart, [p.destination.lng, p.destination.lat], rect);
  if (!src || !dst) return;

  ctx.beginPath();
  ctx.strokeStyle = "#22d3ee";
  ctx.lineWidth = 1.5;
  ctx.globalAlpha = 0.6;
  ctx.setLineDash([]);
  drawArcPath(ctx, src, dst, p.direction);
  ctx.stroke();

  // 箭头
  const arrowT = 0.92;
  const ap = arcPoint(src, dst, p.direction, arrowT);
  const tangent = arcTangent(src, dst, p.direction, arrowT);
  drawArrow(ctx, ap, tangent, "#22d3ee");
  ctx.globalAlpha = 1;
}

function drawNatLine(
  ctx: CanvasRenderingContext2D,
  state: ParticleState,
  chart: echarts.ECharts | null | undefined,
  rect: DOMRect
) {
  const p = state.packet;
  const nat = p.nat_info;
  if (!nat) return;

  // 找到 forward_addr 对应的屏幕位置
  const fwd = geoToPixel(chart, [p.destination.lng, p.destination.lat], rect);
  // 简化：NAT 虚线从 source 画到 destination 的 midpoint，表示转换路径
  const src = geoToPixel(chart, [p.source.lng, p.source.lat], rect);
  const dst = geoToPixel(chart, [p.destination.lng, p.destination.lat], rect);
  if (!src || !dst || !fwd) return;

  ctx.beginPath();
  ctx.strokeStyle = "#f59e0b";
  ctx.lineWidth = 1;
  ctx.globalAlpha = 0.45;
  ctx.setLineDash([4, 4]);
  ctx.moveTo(src[0], src[1]);
  ctx.lineTo(dst[0], dst[1]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}

// ------------------------------------------------------------------
// 几何工具
// ------------------------------------------------------------------

function geoToPixel(
  chart: echarts.ECharts | null | undefined,
  coord: [number, number],
  rect: DOMRect
): [number, number] | null {
  if (!chart) return null;
  try {
    const pt = chart.convertToPixel({ geoIndex: 0 }, coord);
    if (!pt || isNaN(pt[0]) || isNaN(pt[1])) return null;
    return [pt[0], pt[1]];
  } catch {
    return null;
  }
}

function arcPoint(
  src: [number, number],
  dst: [number, number],
  direction: string,
  t: number
): [number, number] {
  if (direction === "internal") {
    return [src[0] + (dst[0] - src[0]) * t, src[1] + (dst[1] - src[1]) * t];
  }
  const mx = (src[0] + dst[0]) / 2;
  const my = (src[1] + dst[1]) / 2;
  const dx = dst[0] - src[0];
  const dy = dst[1] - src[1];
  const dist = Math.sqrt(dx * dx + dy * dy);
  const offset = direction === "outbound" ? -dist * 0.25 : dist * 0.25;
  const cp = [mx - dy * (offset / dist), my + dx * (offset / dist)];

  const u = 1 - t;
  const x = u * u * src[0] + 2 * u * t * cp[0] + t * t * dst[0];
  const y = u * u * src[1] + 2 * u * t * cp[1] + t * t * dst[1];
  return [x, y];
}

function arcTangent(
  src: [number, number],
  dst: [number, number],
  direction: string,
  t: number
): [number, number] {
  if (direction === "internal") {
    const dx = dst[0] - src[0];
    const dy = dst[1] - src[1];
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    return [dx / len, dy / len];
  }
  const mx = (src[0] + dst[0]) / 2;
  const my = (src[1] + dst[1]) / 2;
  const dx = dst[0] - src[0];
  const dy = dst[1] - src[1];
  const dist = Math.sqrt(dx * dx + dy * dy);
  const offset = direction === "outbound" ? -dist * 0.25 : dist * 0.25;
  const cp = [mx - dy * (offset / dist), my + dx * (offset / dist)];

  const u = 1 - t;
  const tx = 2 * u * (cp[0] - src[0]) + 2 * t * (dst[0] - cp[0]);
  const ty = 2 * u * (cp[1] - src[1]) + 2 * t * (dst[1] - cp[1]);
  const len = Math.sqrt(tx * tx + ty * ty) || 1;
  return [tx / len, ty / len];
}

function drawArcPath(
  ctx: CanvasRenderingContext2D,
  src: [number, number],
  dst: [number, number],
  direction: string
) {
  if (direction === "internal") {
    ctx.moveTo(src[0], src[1]);
    ctx.lineTo(dst[0], dst[1]);
    return;
  }
  const mx = (src[0] + dst[0]) / 2;
  const my = (src[1] + dst[1]) / 2;
  const dx = dst[0] - src[0];
  const dy = dst[1] - src[1];
  const dist = Math.sqrt(dx * dx + dy * dy);
  const offset = direction === "outbound" ? -dist * 0.25 : dist * 0.25;
  const cp = [mx - dy * (offset / dist), my + dx * (offset / dist)];
  ctx.moveTo(src[0], src[1]);
  ctx.quadraticCurveTo(cp[0], cp[1], dst[0], dst[1]);
}

function drawArrow(
  ctx: CanvasRenderingContext2D,
  pos: [number, number],
  dir: [number, number],
  color: string
) {
  const size = 6;
  const nx = -dir[1];
  const ny = dir[0];
  ctx.beginPath();
  ctx.moveTo(pos[0] + dir[0] * size, pos[1] + dir[1] * size);
  ctx.lineTo(pos[0] - dir[0] * size * 0.5 + nx * size * 0.6, pos[1] - dir[1] * size * 0.5 + ny * size * 0.6);
  ctx.lineTo(pos[0] - dir[0] * size * 0.5 - nx * size * 0.6, pos[1] - dir[1] * size * 0.5 - ny * size * 0.6);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();
}

// ------------------------------------------------------------------
// 颜色与大小
// ------------------------------------------------------------------

function particleColor(p: PacketEvent): string {
  if (p.flag && FLAG_COLORS[p.flag]) return FLAG_COLORS[p.flag];
  if (p.status && STATUS_COLORS[p.status]) return STATUS_COLORS[p.status];
  if (p.protocol && PROTOCOL_COLORS[p.protocol]) return PROTOCOL_COLORS[p.protocol];
  return "#94a3b8";
}

function particleSize(p: PacketEvent): number {
  const total = p.total_up + p.total_down;
  return Math.max(2.5, Math.min(7, 2.5 + Math.log10(total + 1) * 1.2));
}

// ------------------------------------------------------------------
// 命中检测
// ------------------------------------------------------------------

function findHovered(
  particles: Map<string, ParticleState>,
  mouse: { x: number; y: number }
): string | null {
  let best: string | null = null;
  let bestDist = 18;
  for (const [id, state] of particles) {
    const [x, y] = state.screenPos;
    const dx = x - mouse.x;
    const dy = y - mouse.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < bestDist) {
      bestDist = dist;
      best = id;
    }
  }
  return best;
}
