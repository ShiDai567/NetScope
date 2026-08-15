import { create } from "zustand";
import { NetworkPacket, PacketStats } from "@/types/packet";

interface PacketState {
  packets: NetworkPacket[];
  activePackets: NetworkPacket[];
  stats: PacketStats;
  hoveredPacketId: string | null;
  setHoveredPacketId: (id: string | null) => void;
  addPacket: (packet: NetworkPacket) => void;
  removePacket: (id: string) => void;
  updateStats: () => void;
}

export const usePacketStore = create<PacketState>((set, get) => ({
  packets: [],
  activePackets: [],
  stats: {
    totalSent: 0,
    successCount: 0,
    droppedCount: 0,
    highLatencyCount: 0,
    dropRate: 0,
  },
  hoveredPacketId: null,
  setHoveredPacketId: (id) => set({ hoveredPacketId: id }),
  addPacket: (packet) => {
    set((state) => {
      const newPackets = [...state.packets, packet];
      const newActive = [...state.activePackets, packet];
      return {
        packets: newPackets,
        activePackets: newActive,
      };
    });
    get().updateStats();
  },
  removePacket: (id) => {
    set((state) => ({
      activePackets: state.activePackets.filter((p) => p.id !== id),
    }));
  },
  updateStats: () => {
    const { packets } = get();
    const totalSent = packets.length;
    const successCount = packets.filter((p) => p.status === "success").length;
    const droppedCount = packets.filter((p) => p.status === "dropped").length;
    const highLatencyCount = packets.filter(
      (p) => p.status === "high_latency"
    ).length;
    const dropRate = totalSent > 0 ? (droppedCount / totalSent) * 100 : 0;

    set({
      stats: {
        totalSent,
        successCount,
        droppedCount,
        highLatencyCount,
        dropRate: Math.round(dropRate * 100) / 100,
      },
    });
  },
}));
