"use client";

import { useEffect } from "react";
import SciFiMap from "@/components/map/SciFiMap";
import Header from "@/components/ui/Header";
import StatsPanel from "@/components/ui/StatsPanel";
import SendButton from "@/components/ui/SendButton";
import PacketLog from "@/components/ui/PacketLog";
import NodeLegend from "@/components/ui/NodeLegend";
import { usePacketStore } from "@/store/packetStore";
import { generatePacket } from "@/lib/packetGenerator";

export default function Home() {
  const addPacket = usePacketStore((state) => state.addPacket);

  // Auto-generate packets periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (Math.random() > 0.6) {
        const packet = generatePacket();
        addPacket(packet);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [addPacket]);

  // Keyboard shortcut to send packet
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat) {
        e.preventDefault();
        const packet = generatePacket();
        addPacket(packet);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [addPacket]);

  return (
    <main className="relative w-screen h-screen bg-background overflow-hidden flex flex-col">
      {/* Background grid */}
      <div className="absolute inset-0 grid-bg opacity-50 pointer-events-none" />

      {/* Header */}
      <Header />

      {/* Main content area */}
      <div className="flex-1 flex pt-14 min-h-0">
        {/* Left sidebar */}
        <aside className="w-72 shrink-0 flex flex-col gap-3 p-4 overflow-y-auto z-10">
          <SendButton />
          <StatsPanel />
          <NodeLegend />
        </aside>

        {/* Right: Map area */}
        <section className="flex-1 relative min-h-0 pr-4 pb-4">
          <SciFiMap />
        </section>
      </div>

      {/* Bottom: Packet log */}
      <div className="h-[32vh] min-h-[240px] max-h-[420px] shrink-0 px-4 pb-4 z-10">
        <PacketLog />
      </div>
    </main>
  );
}
