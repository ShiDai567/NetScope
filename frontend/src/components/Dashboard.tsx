"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { usePacketStream } from "@/state/stream";
import Header from "./Header";
import MapView from "./MapView";
import ParticleLayer from "./ParticleLayer";
import Starfield from "./Starfield";
import ControlPanel from "./panels/ControlPanel";
import StatsPanel from "./panels/StatsPanel";
import TimelineBar from "./panels/TimelineBar";
import PacketTooltip from "./panels/PacketTooltip";
import SettingsDrawer from "./panels/SettingsDrawer";
import type { PacketEvent } from "@/lib/types";

export default function Dashboard() {
  const stream = usePacketStream();
  const mapRef = useRef<HTMLDivElement>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapType, setMapType] = useState<"world" | "china">("world");
  const [showNat, setShowNat] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const visible = useMemo(() => {
    return stream.getVisiblePackets();
  }, [stream.getVisiblePackets, stream.tick]);

  const handleMapReady = useCallback(() => setMapReady(true), []);

  const handleMapClick = useCallback(() => {
    stream.setLockedId(null);
  }, [stream]);

  const lockedPacket: PacketEvent | null = useMemo(() => {
    if (!stream.lockedId) return null;
    const arr = stream.eventLogRef.current.get(stream.lockedId);
    return arr?.[arr.length - 1] ?? null;
  }, [stream.lockedId, stream.tick]);

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#03050a]">
      {/* Three.js 星空背景 */}
      <Starfield />

      {/* ECharts 地图 */}
      <div
        ref={mapRef}
        className="absolute inset-0"
        onClick={handleMapClick}
      >
        <MapView
          mapType={mapType}
          devices={stream.devices}
          nodes={stream.nodes}
          visiblePackets={visible}
          onReady={handleMapReady}
        />
      </div>

      {/* Canvas 粒子层 */}
      {mapReady && (
        <ParticleLayer
          mapRef={mapRef}
          eventLogRef={stream.eventLogRef}
          visiblePackets={visible}
          devices={stream.devices}
          nodes={stream.nodes}
          hoveredId={stream.hoveredId}
          lockedId={stream.lockedId}
          showNat={showNat}
          replayClock={stream.replay.active ? stream.replay.clock : undefined}
          onHover={stream.setHoveredId}
          onLock={stream.setLockedId}
          onMouseMove={setMousePos}
          tick={stream.tick}
        />
      )}

      {/* 顶部栏 */}
      <Header
        mapType={mapType}
        onMapTypeChange={setMapType}
        mode={stream.mode}
        showNat={showNat}
        onToggleNat={() => setShowNat((s) => !s)}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      {/* 左侧面板 */}
      <div className="pointer-events-none absolute left-4 top-16 bottom-24 flex w-72 flex-col gap-3">
        <div className="pointer-events-auto">
          <ControlPanel filters={stream.filters} onFilterChange={stream.setFilter} />
        </div>
      </div>

      {/* 右侧面板 */}
      <div className="pointer-events-none absolute right-4 top-16 bottom-24 flex w-80 flex-col gap-3">
        <div className="pointer-events-auto">
          <StatsPanel stats={stream.stats} />
        </div>
      </div>

      {/* 底部时间轴 */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0">
        <div className="pointer-events-auto">
          <TimelineBar
            replay={stream.replay}
            serverTime={stream.serverTime}
            onEnterReplay={stream.enterReplay}
            onExitReplay={stream.exitReplay}
            onSpeedChange={stream.setReplaySpeed}
            onTogglePause={stream.togglePause}
            onSeek={stream.seekReplay}
          />
        </div>
      </div>

      {/* 数据包悬停 Tooltip */}
      <PacketTooltip
        hoveredId={stream.hoveredId}
        lockedId={stream.lockedId}
        eventLogRef={stream.eventLogRef}
        onLock={stream.setLockedId}
        mousePos={mousePos}
      />

      {/* 设置抽屉（iKuai 连接） */}
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        mode={stream.mode}
      />
    </div>
  );
}
