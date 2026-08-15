"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { DeviceInfo, PublicNode } from "@/lib/types";

interface MapViewProps {
  mapType: "world" | "china";
  devices: DeviceInfo[];
  nodes: PublicNode[];
  visiblePackets: Map<string, import("@/lib/types").PacketEvent>;
  onReady: () => void;
}

export default function MapView({
  mapType,
  devices,
  nodes,
  visiblePackets,
  onReady,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const readyRef = useRef(false);
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onReadyRef.current = onReady;
  });

  // 加载并注册地图（仅 mapType 变化时重建，避免父组件重渲染导致重复初始化）
  useEffect(() => {
    let disposed = false;
    let cleanup: (() => void) | undefined;

    const init = async () => {
      const url = mapType === "world" ? "/maps/world.json" : "/maps/china.json";
      const name = mapType === "world" ? "world" : "china";
      try {
        const res = await fetch(url);
        const geoJson = await res.json();
        if (disposed) return;
        echarts.registerMap(name, geoJson);

        const el = containerRef.current;
        if (!el) return;
        const chart = echarts.init(el, undefined, { renderer: "canvas" });
        chartRef.current = chart;

        chart.setOption(buildMapOption(name, mapType));

        const onResize = () => chart.resize();
        window.addEventListener("resize", onResize);
        cleanup = () => {
          window.removeEventListener("resize", onResize);
          chart.dispose();
        };

        if (!readyRef.current) {
          readyRef.current = true;
          onReadyRef.current();
        }
      } catch (e) {
        console.error("地图加载失败", e);
      }
    };
    init();

    return () => {
      disposed = true;
      cleanup?.();
      chartRef.current = null;
    };
  }, [mapType]);

  // 更新节点数据
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const internalNodes = devices.map((d) => ({
      name: d.hostname,
      value: [d.lng, d.lat, d.connections],
      itemStyle: { color: "#10b981" },
      data: d,
    }));

    const publicNodes = nodes.map((n) => ({
      name: n.name,
      value: [n.lng, n.lat, 1],
      itemStyle: { color: n.type === "server" ? "#f43f5e" : "#38bdf8" },
      data: n,
    }));

    // 活跃节点放大
    const activeIps = new Set<string>();
    for (const p of visiblePackets.values()) {
      activeIps.add(p.source.ip);
      activeIps.add(p.destination.ip);
    }

    const effectData = [...internalNodes, ...publicNodes]
      .filter((n) => activeIps.has(n.data.ip))
      .map((n) => ({
        name: n.name,
        value: [n.value[0], n.value[1], Math.max(1, n.value[2])],
        itemStyle: { color: n.itemStyle.color },
      }));

    chart.setOption({
      series: [
        {
          name: "内网设备",
          data: internalNodes,
        },
        {
          name: "公网节点",
          data: publicNodes,
        },
        {
          name: "活跃涟漪",
          data: effectData,
        },
      ],
    });
  }, [devices, nodes, visiblePackets]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      style={{ background: "transparent" }}
    />
  );
}

function buildMapOption(mapName: string, mapType: "world" | "china"): echarts.EChartsOption {
  const roam = true;
  const zoom = mapType === "china" ? 1.2 : 1.0;
  const center = mapType === "china" ? [105, 36] : undefined;

  return {
    backgroundColor: "transparent",
    geo: {
      map: mapName,
      roam,
      zoom,
      center,
      silent: false,
      itemStyle: {
        areaColor: "rgba(10, 22, 48, 0.55)",
        borderColor: "rgba(34, 211, 238, 0.18)",
        borderWidth: 0.8,
        shadowColor: "rgba(34, 211, 238, 0.06)",
        shadowBlur: 10,
      },
      emphasis: {
        disabled: true,
      },
      select: {
        disabled: true,
      },
    },
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(6, 10, 22, 0.92)",
      borderColor: "rgba(34, 211, 238, 0.25)",
      borderWidth: 1,
      textStyle: { color: "#e2e8f0", fontSize: 12, fontFamily: "Geist Mono, monospace" },
      padding: [8, 12],
      formatter: (params: any) => {
        const d = params.data?.data;
        if (!d) return params.name;
        if (d.mac) {
          // 内网设备
          return `
            <div style="font-weight:600;margin-bottom:4px;color:#22d3ee">${d.hostname}</div>
            <div>IP: ${d.ip}</div>
            <div>MAC: ${d.mac}</div>
            <div>厂商: ${d.vendor}</div>
            <div>接口: ${d.interface}</div>
            <div>连接数: ${d.connections}</div>
          `;
        }
        // 公网节点
        return `
          <div style="font-weight:600;margin-bottom:4px;color:#22d3ee">${d.name}</div>
          <div>IP: ${d.ip}</div>
          ${d.domain ? `<div>域名: ${d.domain}</div>` : ""}
        `;
      },
    },
    series: [
      {
        type: "scatter",
        name: "内网设备",
        coordinateSystem: "geo",
        symbolSize: (val: any) => Math.max(6, Math.min(18, 6 + (val?.[2] || 0) * 0.3)),
        itemStyle: {
          color: "#10b981",
          shadowBlur: 8,
          shadowColor: "rgba(16, 185, 129, 0.5)",
        },
        emphasis: {
          scale: 1.5,
          itemStyle: {
            shadowBlur: 16,
            shadowColor: "rgba(16, 185, 129, 0.8)",
          },
        },
        data: [],
      },
      {
        type: "scatter",
        name: "公网节点",
        coordinateSystem: "geo",
        symbolSize: 7,
        itemStyle: {
          shadowBlur: 8,
          shadowColor: "rgba(0,0,0,0.3)",
        },
        data: [],
      },
      {
        type: "effectScatter",
        name: "活跃涟漪",
        coordinateSystem: "geo",
        symbolSize: 10,
        showEffectOn: "render",
        rippleEffect: {
          brushType: "stroke",
          scale: 3,
          period: 3,
        },
        itemStyle: {
          shadowBlur: 10,
        },
        data: [],
      },
    ],
  } as echarts.EChartsOption;
}
