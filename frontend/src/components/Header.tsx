"use client";

import { Globe, MapPin, Network, Gear } from "@phosphor-icons/react";

interface HeaderProps {
  mapType: "world" | "china";
  onMapTypeChange: (t: "world" | "china") => void;
  mode: string;
  showNat: boolean;
  onToggleNat: () => void;
  onOpenSettings: () => void;
}

export default function Header({
  mapType,
  onMapTypeChange,
  mode,
  showNat,
  onToggleNat,
  onOpenSettings,
}: HeaderProps) {
  return (
    <header className="absolute left-0 right-0 top-0 z-30 flex h-14 items-center justify-between border-b border-cyan-400/10 bg-[#03050a]/70 px-4 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-cyan-400/30 bg-cyan-400/10">
          <Network weight="bold" className="text-cyan-400" size={18} />
        </div>
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-slate-200">
            NETSCOPE
          </h1>
          <p className="text-[10px] font-mono text-slate-500">
            网络数据包可视化
          </p>
        </div>
        <span
          className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-mono ${
            mode === "ikuai"
              ? "bg-emerald-500/15 text-emerald-400"
              : "bg-slate-500/15 text-slate-400"
          }`}
        >
          {mode === "ikuai" ? "iKuai 直连" : "模拟数据"}
        </span>
      </div>

      <div className="flex items-center gap-2">
        {/* 地图切换 */}
        <div className="flex overflow-hidden rounded-md border border-cyan-400/15 bg-base-800/60">
          <button
            onClick={() => onMapTypeChange("world")}
            className={`flex items-center gap-1 px-3 py-1.5 text-xs transition-colors ${
              mapType === "world"
                ? "bg-cyan-400/15 text-cyan-400"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Globe size={14} />
            世界地图
          </button>
          <button
            onClick={() => onMapTypeChange("china")}
            className={`flex items-center gap-1 px-3 py-1.5 text-xs transition-colors ${
              mapType === "china"
                ? "bg-cyan-400/15 text-cyan-400"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <MapPin size={14} />
            中国地图
          </button>
        </div>

        {/* NAT 开关 */}
        <button
          onClick={onToggleNat}
          className={`rounded-md border px-3 py-1.5 text-xs font-mono transition-colors ${
            showNat
              ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-400"
              : "border-slate-600/30 bg-base-800/60 text-slate-400 hover:text-slate-200"
          }`}
        >
          NAT
        </button>

        {/* 设置 */}
        <button
          onClick={onOpenSettings}
          className="rounded-md border border-slate-600/30 bg-base-800/60 p-1.5 text-slate-400 transition-colors hover:text-slate-200"
        >
          <Gear size={16} />
        </button>
      </div>
    </header>
  );
}
