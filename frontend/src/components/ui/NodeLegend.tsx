"use client";

import { ComputerTower, Desktop } from "@phosphor-icons/react";

export default function NodeLegend() {
  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <h3 className="text-xs font-mono uppercase tracking-wider text-foreground/50">
        节点图例
      </h3>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#00d4aa] animate-pulse-glow" />
          <ComputerTower className="w-3.5 h-3.5 text-[#00d4aa]" weight="fill" />
          <span className="text-xs text-foreground/60">服务器节点</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-[#f59e0b] animate-pulse-glow" />
          <Desktop className="w-3.5 h-3.5 text-[#f59e0b]" weight="fill" />
          <span className="text-xs text-foreground/60">客户端节点</span>
        </div>
      </div>

      <div className="pt-2 border-t border-border-subtle space-y-2">
        <h4 className="text-[10px] font-mono uppercase tracking-wider text-foreground/30">
          数据包状态
        </h4>
        <div className="grid grid-cols-2 gap-1.5">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-400" />
            <span className="text-[10px] text-foreground/50">发送成功</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-red-400" />
            <span className="text-[10px] text-foreground/50">丢包</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-yellow-400" />
            <span className="text-[10px] text-foreground/50">高延迟</span>
          </div>
        </div>
      </div>

      <div className="pt-2 border-t border-border-subtle space-y-2">
        <h4 className="text-[10px] font-mono uppercase tracking-wider text-foreground/30">
          协议类型
        </h4>
        <div className="grid grid-cols-3 gap-1.5">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-blue-400" />
            <span className="text-[10px] text-foreground/50">TCP</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-purple-400" />
            <span className="text-[10px] text-foreground/50">UDP</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-orange-400" />
            <span className="text-[10px] text-foreground/50">ICMP</span>
          </div>
        </div>
      </div>
    </div>
  );
}
