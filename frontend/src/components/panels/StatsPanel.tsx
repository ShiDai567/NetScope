"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { StatsSnapshot } from "@/lib/types";
import { fmtBps } from "@/lib/format";

interface Props {
  stats: StatsSnapshot | null;
}

export default function StatsPanel({ stats }: Props) {
  const bwChartRef = useRef<HTMLDivElement>(null);
  const protoChartRef = useRef<HTMLDivElement>(null);
  const heatChartRef = useRef<HTMLDivElement>(null);
  const bwInstance = useRef<echarts.ECharts | null>(null);
  const protoInstance = useRef<echarts.ECharts | null>(null);
  const heatInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (bwChartRef.current && !bwInstance.current) {
      bwInstance.current = echarts.init(bwChartRef.current);
    }
    if (protoChartRef.current && !protoInstance.current) {
      protoInstance.current = echarts.init(protoChartRef.current);
    }
    if (heatChartRef.current && !heatInstance.current) {
      heatInstance.current = echarts.init(heatChartRef.current);
    }
    const onResize = () => {
      bwInstance.current?.resize();
      protoInstance.current?.resize();
      heatInstance.current?.resize();
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!stats) return;

    // 带宽趋势图
    const series = stats.bandwidth.series;
    const labels = series.map((s) => {
      const d = new Date(s[0] * 1000);
      return `${d.getHours()}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
    });
    bwInstance.current?.setOption({
      backgroundColor: "transparent",
      grid: { top: 8, right: 8, bottom: 20, left: 48 },
      xAxis: {
        type: "category",
        data: labels,
        axisLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
        axisLabel: { color: "#64748b", fontSize: 9, interval: "auto" },
      },
      yAxis: {
        type: "value",
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(148,163,184,0.08)" } },
        axisLabel: {
          color: "#64748b",
          fontSize: 9,
          formatter: (v: number) => (v >= 1e6 ? `${(v / 1e6).toFixed(0)}M` : `${(v / 1e3).toFixed(0)}k`),
        },
      },
      series: [
        {
          name: "上传",
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { color: "#22d3ee", width: 1.5 },
          areaStyle: { color: "rgba(34,211,238,0.08)" },
          data: series.map((s) => s[1]),
        },
        {
          name: "下载",
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: { color: "#f43f5e", width: 1.5 },
          areaStyle: { color: "rgba(244,63,94,0.06)" },
          data: series.map((s) => s[2]),
        },
      ],
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(6,10,22,0.92)",
        borderColor: "rgba(34,211,238,0.2)",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
      },
      legend: {
        data: ["上传", "下载"],
        textStyle: { color: "#94a3b8", fontSize: 10 },
        top: 0,
        right: 0,
        itemWidth: 10,
        itemHeight: 6,
      },
    });

    // 协议饼图
    const protoData = [
      { value: stats.protocols.tcp || 0, name: "TCP", itemStyle: { color: "#38bdf8" } },
      { value: stats.protocols.udp || 0, name: "UDP", itemStyle: { color: "#34d399" } },
      { value: stats.protocols.icmp || 0, name: "ICMP", itemStyle: { color: "#fbbf24" } },
    ].filter((d) => d.value > 0);
    protoInstance.current?.setOption({
      backgroundColor: "transparent",
      series: [
        {
          type: "pie",
          radius: ["40%", "65%"],
          center: ["50%", "55%"],
          label: { color: "#94a3b8", fontSize: 10 },
          labelLine: { lineStyle: { color: "rgba(148,163,184,0.3)" } },
          data: protoData,
        },
      ],
      tooltip: {
        backgroundColor: "rgba(6,10,22,0.92)",
        borderColor: "rgba(34,211,238,0.2)",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
      },
    });

    // 延迟热力图
    const hm = stats.latency_heatmap;
    heatInstance.current?.setOption({
      backgroundColor: "transparent",
      grid: { top: 24, right: 8, bottom: 20, left: 56 },
      xAxis: {
        type: "category",
        data: hm.x.map((t) => {
          const d = new Date(t * 1000);
          return `${d.getHours()}:${d.getMinutes().toString().padStart(2, "0")}`;
        }),
        axisLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
        axisLabel: { color: "#64748b", fontSize: 8 },
      },
      yAxis: {
        type: "category",
        data: hm.y,
        axisLine: { lineStyle: { color: "rgba(148,163,184,0.2)" } },
        axisLabel: { color: "#94a3b8", fontSize: 9 },
      },
      visualMap: {
        min: 0,
        max: 200,
        calculable: false,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        itemWidth: 8,
        itemHeight: 60,
        inRange: { color: ["#0f1628", "#0891b2", "#22d3ee", "#fbbf24", "#f43f5e"] },
        textStyle: { color: "#64748b", fontSize: 9 },
      },
      series: [
        {
          type: "heatmap",
          data: hm.data,
          label: { show: false },
          itemStyle: { borderColor: "rgba(6,10,22,0.5)", borderWidth: 1 },
        },
      ],
      tooltip: {
        backgroundColor: "rgba(6,10,22,0.92)",
        borderColor: "rgba(34,211,238,0.2)",
        textStyle: { color: "#e2e8f0", fontSize: 11 },
        formatter: (p: any) => `${p.name || ""}: ${p.value?.[2] ?? ""} ms`,
      },
    });
  }, [stats]);

  if (!stats) {
    return (
      <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
        <div className="text-xs text-slate-500">统计加载中...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 计数卡片 */}
      <div className="grid grid-cols-2 gap-2">
        <StatCard label="总连接" value={stats.total} color="#22d3ee" />
        <StatCard label="活跃" value={stats.active} color="#10b981" />
        <StatCard label="已关闭" value={stats.closed} color="#94a3b8" />
        <StatCard label="失败" value={stats.failed + stats.lost} color="#f43f5e" />
      </div>

      {/* 方向分布 */}
      <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
        <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          方向分布
        </h4>
        <div className="space-y-1.5">
          {[
            { k: "outbound", label: "向外发包", color: "#38bdf8" },
            { k: "inbound", label: "向内接受", color: "#f43f5e" },
            { k: "internal", label: "内网通信", color: "#10b981" },
          ].map((row) => {
            const val = stats.directions[row.k] || 0;
            const max = Math.max(1, ...Object.values(stats.directions));
            const pct = (val / max) * 100;
            return (
              <div key={row.k} className="flex items-center gap-2">
                <span className="w-14 text-[10px] text-slate-400">{row.label}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-base-800">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: row.color }}
                  />
                </div>
                <span className="w-6 text-right text-[10px] font-mono text-slate-300">
                  {val}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 实时带宽 */}
      <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
        <div className="mb-1 flex items-center justify-between">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            实时带宽
          </h4>
          <div className="flex gap-2 text-[10px] font-mono">
            <span className="text-cyan-400">↑ {fmtBps(stats.bandwidth.up_bps)}</span>
            <span className="text-rose-400">↓ {fmtBps(stats.bandwidth.down_bps)}</span>
          </div>
        </div>
        <div ref={bwChartRef} className="h-28 w-full" />
      </div>

      {/* 协议分布 */}
      <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          协议分布
        </h4>
        <div ref={protoChartRef} className="h-32 w-full" />
      </div>

      {/* 延迟热力图 */}
      <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
        <div className="mb-1 flex items-center justify-between">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            延迟热力图
          </h4>
          <span className="text-[10px] font-mono text-slate-400">
            avg {stats.avg_latency_ms.toFixed(1)} ms
          </span>
        </div>
        <div ref={heatChartRef} className="h-36 w-full" />
      </div>

      {/* 丢包率 */}
      <div className="rounded-lg border border-cyan-400/10 bg-[#03050a]/80 p-3 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            丢包率
          </span>
          <span
            className={`text-lg font-mono font-bold ${
              stats.loss_rate > 5 ? "text-rose-500" : "text-emerald-400"
            }`}
          >
            {stats.loss_rate.toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="rounded-md border border-cyan-400/10 bg-base-800/40 p-2">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className="text-lg font-mono font-bold" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
