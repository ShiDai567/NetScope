"use client";

import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import { nodes } from "@/lib/nodes";
import PacketOverlay from "./PacketOverlay";

export default function SciFiMap() {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Initialize chart
  useEffect(() => {
    if (!chartRef.current) return;

    const chart = echarts.init(chartRef.current, undefined, {
      renderer: "canvas",
    });
    chartInstance.current = chart;

    // Fetch world map JSON
    fetch("https://cdn.jsdelivr.net/npm/echarts/map/json/world.json")
      .then((res) => res.json())
      .then((worldJson) => {
        echarts.registerMap("world", worldJson);

        const serverNodes = nodes.filter((n) => n.type === "server");
        const clientNodes = nodes.filter((n) => n.type === "client");

        const option: echarts.EChartsOption = {
          backgroundColor: "transparent",
          geo: {
            map: "world",
            roam: true,
            zoom: 1.2,
            center: [20, 20],
            silent: true,
            itemStyle: {
              areaColor: "#0a1628",
              borderColor: "#1e3a5f",
              borderWidth: 1,
            },
            emphasis: {
              disabled: true,
            },
            regions: [
              {
                name: "China",
                itemStyle: {
                  areaColor: "#0d1f35",
                },
              },
            ],
          },
          series: [
            {
              type: "effectScatter",
              coordinateSystem: "geo",
              data: serverNodes.map((node) => ({
                name: node.name,
                value: [node.lng, node.lat, 1],
                itemStyle: {
                  color: "#00d4aa",
                },
                symbolSize: 12,
              })),
              rippleEffect: {
                brushType: "stroke",
                scale: 3,
                period: 4,
              },
              label: {
                show: true,
                position: "right",
                formatter: "{b}",
                fontSize: 10,
                color: "#00d4aa",
                fontFamily: "var(--font-geist-mono)",
              },
              zlevel: 2,
            },
            {
              type: "effectScatter",
              coordinateSystem: "geo",
              data: clientNodes.map((node) => ({
                name: node.name,
                value: [node.lng, node.lat, 1],
                itemStyle: {
                  color: "#f59e0b",
                },
                symbolSize: 8,
              })),
              rippleEffect: {
                brushType: "stroke",
                scale: 2.5,
                period: 3,
              },
              label: {
                show: true,
                position: "right",
                formatter: "{b}",
                fontSize: 9,
                color: "#f59e0b",
                fontFamily: "var(--font-geist-mono)",
              },
              zlevel: 2,
            },
          ],
        };

        chart.setOption(option);
        setMapLoaded(true);
      })
      .catch((err) => {
        console.error("Failed to load world map:", err);
      });

    const handleResize = () => {
      chart.resize();
    };

    handleResize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={chartRef} className="w-full h-full" />

      {/* Packet animation overlay */}
      {mapLoaded && <PacketOverlay chartInstance={chartInstance} />}

      {/* Sci-fi overlay effects */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Corner decorations */}
        <div className="absolute top-4 left-4 w-16 h-16 border-l-2 border-t-2 border-accent/30" />
        <div className="absolute top-4 right-4 w-16 h-16 border-r-2 border-t-2 border-accent/30" />
        <div className="absolute bottom-4 left-4 w-16 h-16 border-l-2 border-b-2 border-accent/30" />
        <div className="absolute bottom-4 right-4 w-16 h-16 border-r-2 border-b-2 border-accent/30" />

        {/* Scan line effect */}
        <div
          className="absolute left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-accent/20 to-transparent animate-scanline"
          style={{ animation: "scanline 4s linear infinite" }}
        />
      </div>
    </div>
  );
}
