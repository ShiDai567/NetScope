"use client";

import type { Scene } from "@/lib/types";
import { useNetworkStore } from "@/store/networkStore";

const SCENES: { id: Scene; label: string }[] = [
  { id: "global", label: "全球" },
  { id: "china", label: "中国" },
  { id: "lan", label: "内网" },
];

/** 场景切换：全球 / 中国 / 内网 —— 切换由引擎做平滑 Zoom，不刷新页面 */
export function SceneSwitcher() {
  const scene = useNetworkStore((s) => s.scene);
  const setScene = useNetworkStore((s) => s.setScene);

  return (
    <nav
      className="pointer-events-auto flex items-center border border-cyan-400/20 bg-[#050B14]/85 backdrop-blur-sm"
      role="tablist"
      aria-label="地图场景"
    >
      {SCENES.map((s) => {
        const active = s.id === scene;
        return (
          <button
            key={s.id}
            role="tab"
            aria-selected={active}
            onClick={() => setScene(s.id)}
            className={`relative px-4 py-1.5 font-mono text-[10px] tracking-[0.3em] transition-colors duration-150 ${
              active
                ? "bg-cyan-400/10 text-cyan-200"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            [ {s.label} ]
            {active && (
              <i
                aria-hidden
                className="absolute inset-x-0 -bottom-px h-px bg-cyan-300"
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}
