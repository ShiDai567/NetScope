"use client";

import { usePacketStore } from "@/store/packetStore";
import {
  PaperPlaneRight,
  CheckCircle,
  WarningCircle,
  TrendDown,
} from "@phosphor-icons/react";

export default function StatsPanel() {
  const stats = usePacketStore((state) => state.stats);

  const statItems = [
    {
      label: "已发送总数",
      value: stats.totalSent,
      icon: PaperPlaneRight,
      color: "text-blue-400",
      bgColor: "bg-blue-400/10",
    },
    {
      label: "成功数",
      value: stats.successCount,
      icon: CheckCircle,
      color: "text-green-400",
      bgColor: "bg-green-400/10",
    },
    {
      label: "高延迟",
      value: stats.highLatencyCount,
      icon: WarningCircle,
      color: "text-yellow-400",
      bgColor: "bg-yellow-400/10",
    },
    {
      label: "丢包率",
      value: `${stats.dropRate.toFixed(1)}%`,
      icon: TrendDown,
      color: "text-red-400",
      bgColor: "bg-red-400/10",
    },
  ];

  return (
    <div className="glass rounded-xl p-4 space-y-3">
      <h3 className="text-xs font-mono uppercase tracking-wider text-foreground/50 mb-3">
        实时统计
      </h3>
      <div className="grid grid-cols-2 gap-3">
        {statItems.map((item) => (
          <div
            key={item.label}
            className="bg-surface-elevated/50 rounded-lg p-3 border border-border-subtle"
          >
            <div className="flex items-center gap-2 mb-1">
              <div className={`${item.bgColor} rounded-md p-1`}>
                <item.icon className={`w-3.5 h-3.5 ${item.color}`} weight="fill" />
              </div>
              <span className="text-[10px] text-foreground/40 uppercase tracking-wider">
                {item.label}
              </span>
            </div>
            <div className={`text-xl font-mono font-bold ${item.color}`}>
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
