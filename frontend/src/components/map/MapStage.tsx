"use client";

import { useEffect, useRef, useState } from "react";
import { RenderEngine, type HoverPayload } from "@/components/map/renderEngine";
import { useNetworkStore } from "@/store/networkStore";

/**
 * 地图舞台：单一 canvas 承载 GLOBAL / CHINA / LAN 三场景。
 * React 只负责 tooltip / 空态覆盖层，渲染全部走引擎 rAF。
 */
export function MapStage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<RenderEngine | null>(null);
  const [hover, setHover] = useState<HoverPayload | null>(null);
  const [geoLoading, setGeoLoading] = useState(true);
  const [hasTraffic, setHasTraffic] = useState(false);

  // 引擎生命周期
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const engine = new RenderEngine(canvas, {
      onHover: (h) => {
        setHover(h);
        if (h) setGeoLoading(false);
      },
      onClick: (h) => {
        const store = useNetworkStore.getState();
        if (h?.kind === "flow" && h.flowId) {
          store.selectFlow(h.flowId);
        } else if (!h) {
          store.selectFlow(null);
        }
      },
    });
    engine.refreshTo(useNetworkStore.getState().scene);
    engineRef.current = engine;
    // 地理加载指示：引擎就绪后由首次 hover 或超时关闭
    const t = setTimeout(() => setGeoLoading(false), 4000);

    const ro = new ResizeObserver(() => engine.resize());
    ro.observe(canvas);

    return () => {
      clearTimeout(t);
      ro.disconnect();
      engine.dispose();
      engineRef.current = null;
    };
  }, []);

  // 场景切换
  const scene = useNetworkStore((s) => s.scene);
  const connState = useNetworkStore((s) => s.connState);
  useEffect(() => {
    engineRef.current?.setScene(scene);
  }, [scene]);

  // 空态检测
  useEffect(() => {
    const timer = setInterval(() => {
      const st = useNetworkStore.getState();
      setHasTraffic(st.flows.length > 0 || (st.stats?.total ?? 0) > 0);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <canvas ref={canvasRef} className="block h-full w-full" />

      {/* Hover Tooltip —— HUD 风格 */}
      {hover && (
        <div
          className="pointer-events-none absolute z-20 w-60 border bg-[#050B14]/90 p-3 backdrop-blur-sm"
          style={{
            left: Math.min(Math.max(hover.x + 16, 12), 9999),
            top: Math.min(Math.max(hover.y + 16, 12), 9999),
            borderColor: `${hover.accent}55`,
            boxShadow: `0 0 18px ${hover.accent}22`,
          }}
        >
          <div className="hud-corner" aria-hidden />
          <p
            className="font-mono text-[11px] font-semibold tracking-widest"
            style={{ color: hover.accent }}
          >
            {hover.title}
          </p>
          {hover.subtitle && (
            <p className="mt-0.5 font-mono text-[10px] text-slate-500">
              {hover.subtitle}
            </p>
          )}
          <dl className="mt-2 space-y-1">
            {hover.rows.map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-3">
                <dt className="font-mono text-[10px] tracking-wider text-slate-600">
                  {k}
                </dt>
                <dd className="truncate font-mono text-[10px] text-slate-300">
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* 地理数据加载中 */}
      {geoLoading && (
        <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2">
          <p className="animate-pulse font-mono text-[11px] tracking-[0.3em] text-cyan-300/70">
            正在加载地理数据 ...
          </p>
        </div>
      )}

      {/* 空数据状态 */}
      {!hasTraffic && !geoLoading && connState === "connected" && (
        <div className="pointer-events-none absolute left-1/2 top-[38%] z-10 -translate-x-1/2 text-center">
          <p className="font-mono text-xs tracking-[0.4em] text-cyan-200/80">
            系统在线
          </p>
          <p className="mt-2 animate-pulse font-mono text-[10px] tracking-[0.35em] text-slate-500">
            正在等待流量数据
          </p>
        </div>
      )}
    </div>
  );
}
