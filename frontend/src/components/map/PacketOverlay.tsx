"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { NetworkPacket, Protocol, PacketStatus } from "@/types/packet";
import { usePacketStore } from "@/store/packetStore";

interface PacketAnim {
  packet: NetworkPacket;
  progress: number;
  speed: number;
  paused: boolean;
  hovered: boolean;
}

const PROTOCOL_COLORS: Record<Protocol, string> = {
  TCP: "#3b82f6",
  UDP: "#a855f7",
  ICMP: "#f97316",
};

const STATUS_COLORS: Record<PacketStatus, string> = {
  success: "#22c55e",
  dropped: "#ef4444",
  high_latency: "#eab308",
};

interface PacketOverlayProps {
  chartInstance: any;
}

export default function PacketOverlay({ chartInstance }: PacketOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animsRef = useRef<Map<string, PacketAnim>>(new Map());
  const frameRef = useRef<number>(0);
  const [hoveredPacket, setHoveredPacket] = useState<NetworkPacket | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

  const activePackets = usePacketStore((state) => state.activePackets);
  const removePacket = usePacketStore((state) => state.removePacket);

  // Get canvas pixel ratio for sharp rendering
  const getPixelRatio = useCallback(() => {
    return window.devicePixelRatio || 1;
  }, []);

  // Convert lat/lng to pixel coordinates using ECharts geo conversion
  const latLngToPixel = useCallback(
    (lat: number, lng: number): [number, number] | null => {
      if (!chartInstance.current) return null;
      try {
        const pixel = chartInstance.current.convertToPixel({ geoIndex: 0 }, [lng, lat]);
        if (!pixel || !Array.isArray(pixel) || pixel.length !== 2) return null;
        return [pixel[0], pixel[1]];
      } catch {
        return null;
      }
    },
    [chartInstance]
  );

  // Sync canvas size with container and handle resize
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        const ratio = getPixelRatio();
        
        // Set canvas internal resolution (scaled for retina)
        canvas.width = Math.floor(width * ratio);
        canvas.height = Math.floor(height * ratio);
        
        // Set CSS size
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        
        // Scale context for retina
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        }
        
        setCanvasSize({ width, height });
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, [getPixelRatio]);

  // Sync active packets to animations
  useEffect(() => {
    activePackets.forEach((packet) => {
      if (!animsRef.current.has(packet.id)) {
        const baseSpeed = 0.008;
        const speedMultiplier = packet.status === "high_latency" ? 0.25 : 1;
        animsRef.current.set(packet.id, {
          packet,
          progress: 0,
          speed: baseSpeed * speedMultiplier,
          paused: false,
          hovered: false,
        });
      }
    });

    // Remove stale
    animsRef.current.forEach((anim, id) => {
      if (!activePackets.find((p) => p.id === id)) {
        animsRef.current.delete(id);
      }
    });
  }, [activePackets]);

  // Canvas animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const animate = () => {
      const { width, height } = canvasSize;
      if (width === 0 || height === 0) {
        frameRef.current = requestAnimationFrame(animate);
        return;
      }

      ctx.clearRect(0, 0, width, height);

      animsRef.current.forEach((anim, id) => {
        if (anim.hovered) return;
        anim.progress += anim.speed;

        const p = anim.packet;
        const src = latLngToPixel(p.source.lat, p.source.lng);
        const dst = latLngToPixel(p.destination.lat, p.destination.lng);

        if (!src || !dst) return;

        // Validate coordinates are within canvas bounds (with some margin)
        const isValidCoord = (x: number, y: number) => 
          x > -100 && x < width + 100 && y > -100 && y < height + 100;

        if (!isValidCoord(src[0], src[1]) || !isValidCoord(dst[0], dst[1])) return;

        // Dropped: disappear at 50%
        if (p.status === "dropped" && anim.progress >= 0.5) {
          const midX = src[0] + (dst[0] - src[0]) * 0.5;
          const midY = src[1] + (dst[1] - src[1]) * 0.5;
          drawExplosion(ctx, midX, midY, (anim.progress - 0.5) * 2);

          if (anim.progress >= 0.7) {
            removePacket(id);
            animsRef.current.delete(id);
          }
          return;
        }

        // Completed
        if (anim.progress >= 1) {
          removePacket(id);
          animsRef.current.delete(id);
          return;
        }

        const curProgress =
          p.status === "dropped" ? Math.min(anim.progress, 0.5) : anim.progress;

        const curX = src[0] + (dst[0] - src[0]) * curProgress;
        const curY = src[1] + (dst[1] - src[1]) * curProgress;

        // Draw trail
        drawTrail(ctx, src[0], src[1], curX, curY, p.status, p.protocol);

        // Draw packet dot
        drawPacket(ctx, curX, curY, p.status, p.protocol, anim.hovered);
      });

      frameRef.current = requestAnimationFrame(animate);
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(frameRef.current);
    };
  }, [latLngToPixel, removePacket, canvasSize]);

  // Mouse interaction
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setMousePos({ x, y });

      let found: NetworkPacket | null = null;

      animsRef.current.forEach((anim) => {
        const p = anim.packet;
        const src = latLngToPixel(p.source.lat, p.source.lng);
        const dst = latLngToPixel(p.destination.lat, p.destination.lng);
        if (!src || !dst) return;

        const curProgress =
          p.status === "dropped" ? Math.min(anim.progress, 0.5) : anim.progress;
        const curX = src[0] + (dst[0] - src[0]) * curProgress;
        const curY = src[1] + (dst[1] - src[1]) * curProgress;

        const dist = Math.hypot(x - curX, y - curY);
        if (dist < 20) {
          found = p;
          anim.hovered = true;
        } else {
          anim.hovered = false;
        }
      });

      setHoveredPacket(found);
    },
    [latLngToPixel]
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredPacket(null);
    animsRef.current.forEach((anim) => {
      anim.hovered = false;
    });
  }, []);

  return (
    <div ref={containerRef} className="absolute inset-0 pointer-events-auto">
      <canvas
        ref={canvasRef}
        className="block w-full h-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
      {hoveredPacket && (
        <PacketTooltip packet={hoveredPacket} x={mousePos.x} y={mousePos.y} />
      )}
    </div>
  );
}

function drawTrail(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  status: PacketStatus,
  protocol: Protocol
) {
  const gradient = ctx.createLinearGradient(x1, y1, x2, y2);
  const color = STATUS_COLORS[status];
  gradient.addColorStop(0, color + "00");
  gradient.addColorStop(1, color + "88");

  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Protocol indicator along trail
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  ctx.beginPath();
  ctx.arc(midX, midY, 1.5, 0, Math.PI * 2);
  ctx.fillStyle = PROTOCOL_COLORS[protocol] + "44";
  ctx.fill();
}

function drawPacket(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  status: PacketStatus,
  protocol: Protocol,
  hovered: boolean
) {
  const size = hovered ? 10 : 6;
  const color = STATUS_COLORS[status];
  const protoColor = PROTOCOL_COLORS[protocol];

  // Glow
  const glowSize = hovered ? 20 : 12;
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, glowSize);
  gradient.addColorStop(0, color + "66");
  gradient.addColorStop(1, color + "00");
  ctx.beginPath();
  ctx.arc(x, y, glowSize, 0, Math.PI * 2);
  ctx.fillStyle = gradient;
  ctx.fill();

  // Outer ring (protocol color)
  ctx.beginPath();
  ctx.arc(x, y, size + 2, 0, Math.PI * 2);
  ctx.fillStyle = protoColor + "88";
  ctx.fill();

  // Inner dot (status color)
  ctx.beginPath();
  ctx.arc(x, y, size, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();

  // White center
  ctx.beginPath();
  ctx.arc(x, y, size * 0.4, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();

  if (hovered) {
    ctx.beginPath();
    ctx.arc(x, y, size + 4, 0, Math.PI * 2);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function drawExplosion(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  progress: number
) {
  const maxRadius = 30;
  const radius = maxRadius * progress;
  const alpha = 1 - progress;

  // Outer ring
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(239, 68, 68, ${alpha})`;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Inner fill
  ctx.beginPath();
  ctx.arc(x, y, radius * 0.6, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(239, 68, 68, ${alpha * 0.3})`;
  ctx.fill();

  // Sparks
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    const sparkLen = radius * 0.8;
    const sx = x + Math.cos(angle) * sparkLen;
    const sy = y + Math.sin(angle) * sparkLen;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(sx, sy);
    ctx.strokeStyle = `rgba(251, 191, 36, ${alpha})`;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

function PacketTooltip({
  packet,
  x,
  y,
}: {
  packet: NetworkPacket;
  x: number;
  y: number;
}) {
  return (
    <div
      className="absolute glass rounded-lg p-3 min-w-[260px] z-50 pointer-events-none"
      style={{
        left: Math.min(x + 16, window.innerWidth - 300),
        top: Math.max(y - 10, 10),
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: STATUS_COLORS[packet.status] }}
        />
        <span className="text-xs font-mono text-foreground/70">
          {packet.id}
        </span>
        <span
          className="ml-auto text-[10px] font-mono px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: PROTOCOL_COLORS[packet.protocol] + "22",
            color: PROTOCOL_COLORS[packet.protocol],
          }}
        >
          {packet.protocol}
        </span>
      </div>
      <div className="space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-foreground/40">源地址</span>
          <span className="font-mono text-accent">{packet.source.ip}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground/40">目标地址</span>
          <span className="font-mono text-accent-warm">
            {packet.destination.ip}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground/40">状态</span>
          <span
            className="font-mono"
            style={{ color: STATUS_COLORS[packet.status] }}
          >
            {packet.status === "success"
              ? "成功"
              : packet.status === "dropped"
              ? "丢包"
              : "高延迟"}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground/40">Payload</span>
          <span className="font-mono">{packet.payloadSize} bytes</span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground/40">时间戳</span>
          <span className="font-mono text-[10px]">
            {new Date(packet.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  );
}
