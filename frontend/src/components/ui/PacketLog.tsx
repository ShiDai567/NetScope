"use client";

import { usePacketStore } from "@/store/packetStore";
import { NetworkPacket, Protocol, PacketStatus } from "@/types/packet";
import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import {
  ArrowRight,
  CheckCircle,
  WarningCircle,
  XCircle,
  Clock,
  HardDrives,
  GlobeHemisphereWest,
  Pause,
  Play,
  MapPin,
} from "@phosphor-icons/react";
import { nodes } from "@/lib/nodes";

const PROTOCOL_CONFIG: Record<
  Protocol,
  { color: string; bg: string; label: string }
> = {
  TCP: { color: "text-blue-400", bg: "bg-blue-400/10", label: "TCP" },
  UDP: { color: "text-purple-400", bg: "bg-purple-400/10", label: "UDP" },
  ICMP: { color: "text-orange-400", bg: "bg-orange-400/10", label: "ICMP" },
};

const STATUS_CONFIG: Record<
  PacketStatus,
  {
    color: string;
    bg: string;
    icon: typeof CheckCircle;
    label: string;
    desc: string;
  }
> = {
  success: {
    color: "text-green-400",
    bg: "bg-green-400/10",
    icon: CheckCircle,
    label: "成功",
    desc: "已送达",
  },
  dropped: {
    color: "text-red-400",
    bg: "bg-red-400/10",
    icon: XCircle,
    label: "丢包",
    desc: "传输中断",
  },
  high_latency: {
    color: "text-yellow-400",
    bg: "bg-yellow-400/10",
    icon: WarningCircle,
    label: "高延迟",
    desc: "延迟 > 200ms",
  },
};

type SortField = "time" | "size" | "status";
type SortOrder = "desc" | "asc";

function getNodeName(ip: string): string | undefined {
  const node = nodes.find((n) => n.ip === ip);
  return node?.name;
}

function formatGeo(lat: number, lng: number): string {
  const latDir = lat >= 0 ? "N" : "S";
  const lngDir = lng >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(2)}°${latDir} ${Math.abs(lng).toFixed(2)}°${lngDir}`;
}

export default function PacketLog() {
  const packets = usePacketStore((state) => state.packets);
  const [filter, setFilter] = useState<"all" | Protocol>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | PacketStatus>("all");
  const [sortField, setSortField] = useState<SortField>("time");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);

  const filteredPackets = useMemo(() => {
    let result =
      filter === "all" ? packets : packets.filter((p) => p.protocol === filter);
    result =
      statusFilter === "all"
        ? result
        : result.filter((p) => p.status === statusFilter);

    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortField === "time") cmp = a.timestamp - b.timestamp;
      else if (sortField === "size") cmp = a.payloadSize - b.payloadSize;
      else if (sortField === "status") {
        const order = { success: 0, high_latency: 1, dropped: 2 };
        cmp = order[a.status] - order[b.status];
      }
      return sortOrder === "desc" ? -cmp : cmp;
    });

    return result;
  }, [packets, filter, statusFilter, sortField, sortOrder]);

  const recentPackets = filteredPackets.slice(0, 100);

  // Auto-scroll to top when new packets arrive (newest first)
  useEffect(() => {
    const count = recentPackets.length;
    if (autoScroll && count > prevCountRef.current && scrollRef.current) {
      scrollRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
    prevCountRef.current = count;
  }, [recentPackets.length, autoScroll]);

  // Pause auto-scroll if user scrolls up
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    setAutoScroll(el.scrollTop < 20);
  }, []);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "desc" ? "asc" : "desc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  // Stats summary
  const stats = useMemo(() => {
    const total = filteredPackets.length;
    const tcp = filteredPackets.filter((p) => p.protocol === "TCP").length;
    const udp = filteredPackets.filter((p) => p.protocol === "UDP").length;
    const icmp = filteredPackets.filter((p) => p.protocol === "ICMP").length;
    const avgSize =
      total > 0
        ? Math.round(
            filteredPackets.reduce((s, p) => s + p.payloadSize, 0) / total
          )
        : 0;
    return { total, tcp, udp, icmp, avgSize };
  }, [filteredPackets]);

  return (
    <div className="glass rounded-xl p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0 mb-3">
        <div className="flex items-center gap-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-foreground/50">
            数据包日志
          </h3>
          <span className="text-[10px] font-mono text-foreground/30 px-2 py-0.5 rounded-full bg-white/5">
            {stats.total} 条记录
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Protocol filter */}
          <div className="flex gap-1">
            {(["all", "TCP", "UDP", "ICMP"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setFilter(p)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                  filter === p
                    ? "bg-accent/20 text-accent"
                    : "text-foreground/30 hover:text-foreground/50"
                }`}
              >
                {p === "all" ? "全部" : p}
              </button>
            ))}
          </div>

          <span className="w-px h-3 bg-foreground/10" />

          {/* Status filter */}
          <div className="flex gap-1">
            {(
              [
                ["all", "全部"],
                ["success", "成功"],
                ["dropped", "丢包"],
                ["high_latency", "延迟"],
              ] as const
            ).map(([s, label]) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s as "all" | PacketStatus)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                  statusFilter === s
                    ? "bg-accent/20 text-accent"
                    : "text-foreground/30 hover:text-foreground/50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <span className="w-px h-3 bg-foreground/10" />

          {/* Auto-scroll toggle */}
          <button
            onClick={() => setAutoScroll((v) => !v)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
              autoScroll
                ? "bg-accent/20 text-accent"
                : "text-foreground/30 hover:text-foreground/50"
            }`}
            title={autoScroll ? "暂停自动滚动" : "开启自动滚动"}
          >
            {autoScroll ? (
              <Pause className="w-3 h-3" weight="fill" />
            ) : (
              <Play className="w-3 h-3" weight="fill" />
            )}
            {autoScroll ? "实时" : "暂停"}
          </button>
        </div>
      </div>

      {/* Stats summary bar */}
      <div className="flex items-center gap-4 shrink-0 mb-3 px-3 py-2 rounded-lg bg-white/5">
        <div className="flex items-center gap-1.5">
          <HardDrives className="w-3 h-3 text-foreground/30" />
          <span className="text-[10px] text-foreground/40">平均大小</span>
          <span className="text-xs font-mono text-foreground/70">
            {stats.avgSize} bytes
          </span>
        </div>
        <span className="w-px h-3 bg-foreground/10" />
        <div className="flex items-center gap-1.5">
          <GlobeHemisphereWest className="w-3 h-3 text-blue-400" />
          <span className="text-[10px] text-foreground/40">TCP</span>
          <span className="text-xs font-mono text-blue-400">{stats.tcp}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <GlobeHemisphereWest className="w-3 h-3 text-purple-400" />
          <span className="text-[10px] text-foreground/40">UDP</span>
          <span className="text-xs font-mono text-purple-400">
            {stats.udp}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <GlobeHemisphereWest className="w-3 h-3 text-orange-400" />
          <span className="text-[10px] text-foreground/40">ICMP</span>
          <span className="text-xs font-mono text-orange-400">
            {stats.icmp}
          </span>
        </div>
        <span className="w-px h-3 bg-foreground/10" />
        <div className="flex items-center gap-1.5">
          <MapPin className="w-3 h-3 text-foreground/30" />
          <span className="text-[10px] text-foreground/40">地理追踪</span>
          <span className="text-[10px] font-mono text-foreground/50">已开启</span>
        </div>
      </div>

      {/* Table header */}
      <div className="grid grid-cols-[80px_56px_1fr_100px_1fr_100px_90px_100px] gap-2 px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-foreground/30 shrink-0 border-b border-white/5">
        <button
          onClick={() => toggleSort("time")}
          className="text-left hover:text-foreground/50 transition-colors flex items-center gap-1"
        >
          ID
          {sortField === "time" && (
            <span className="text-accent">{sortOrder === "desc" ? "↓" : "↑"}</span>
          )}
        </button>
        <button
          onClick={() => toggleSort("status")}
          className="text-left hover:text-foreground/50 transition-colors flex items-center gap-1"
        >
          协议
          {sortField === "status" && (
            <span className="text-accent">{sortOrder === "desc" ? "↓" : "↑"}</span>
          )}
        </button>
        <span>源地址</span>
        <span>源地理位置</span>
        <span>目标地址</span>
        <button
          onClick={() => toggleSort("size")}
          className="text-left hover:text-foreground/50 transition-colors flex items-center gap-1"
        >
          目标地理位置
          {sortField === "size" && (
            <span className="text-accent">{sortOrder === "desc" ? "↓" : "↑"}</span>
          )}
        </button>
        <span>状态</span>
        <span className="text-right">时间</span>
      </div>

      {/* Table body */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="overflow-y-auto flex-1 min-h-0"
      >
        {recentPackets.length === 0 ? (
          <div className="text-center py-8 text-foreground/20 text-xs">
            <Clock className="w-5 h-5 mx-auto mb-2 opacity-30" />
            暂无数据包记录
          </div>
        ) : (
          <div className="space-y-0.5">
            {recentPackets.map((packet) => (
              <PacketLogRow key={packet.id} packet={packet} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PacketLogRow({ packet }: { packet: NetworkPacket }) {
  const proto = PROTOCOL_CONFIG[packet.protocol];
  const status = STATUS_CONFIG[packet.status];
  const StatusIcon = status.icon;
  const srcName = getNodeName(packet.source.ip);
  const dstName = getNodeName(packet.destination.ip);

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, "0")}:${d
      .getMinutes()
      .toString()
      .padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}.${
      d.getMilliseconds().toString().padStart(3, "0")
    }`;
  };

  const formatSize = (size: number) => {
    if (size < 1024) return `${size} B`;
    return `${(size / 1024).toFixed(1)} KB`;
  };

  return (
    <div className="grid grid-cols-[80px_56px_1fr_100px_1fr_100px_90px_100px] gap-2 px-3 py-2 rounded hover:bg-white/5 transition-colors text-xs font-mono items-center group">
      {/* ID */}
      <span className="text-foreground/40">{packet.id}</span>

      {/* Protocol badge */}
      <span
        className={`inline-flex items-center justify-center px-1.5 py-0.5 rounded text-[10px] font-bold ${proto.bg} ${proto.color} w-fit`}
      >
        {proto.label}
      </span>

      {/* Source */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-foreground/50 truncate">{packet.source.ip}</span>
        {srcName && (
          <span className="text-[9px] text-foreground/30 truncate">
            {srcName}
          </span>
        )}
      </div>

      {/* Source geo */}
      <div className="flex items-center gap-1 min-w-0">
        <MapPin className="w-3 h-3 text-accent/60 shrink-0" />
        <span className="text-[10px] text-foreground/40 truncate">
          {formatGeo(packet.source.lat, packet.source.lng)}
        </span>
      </div>

      {/* Destination */}
      <div className="flex items-center gap-1.5 min-w-0">
        <ArrowRight className="w-3 h-3 text-foreground/20 shrink-0" />
        <span className="text-foreground/50 truncate">
          {packet.destination.ip}
        </span>
        {dstName && (
          <span className="text-[9px] text-foreground/30 truncate">
            {dstName}
          </span>
        )}
      </div>

      {/* Destination geo */}
      <div className="flex items-center gap-1 min-w-0">
        <MapPin className="w-3 h-3 text-accent-warm/60 shrink-0" />
        <span className="text-[10px] text-foreground/40 truncate">
          {formatGeo(packet.destination.lat, packet.destination.lng)}
        </span>
      </div>

      {/* Status */}
      <div className="flex items-center gap-1.5">
        <StatusIcon
          className={`w-3.5 h-3.5 ${status.color}`}
          weight="fill"
        />
        <span className={`text-[10px] ${status.color}`}>{status.label}</span>
      </div>

      {/* Time */}
      <span className="text-foreground/30 text-right text-[10px]">
        {formatTime(packet.timestamp)}
      </span>
    </div>
  );
}
