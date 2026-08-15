export type Protocol = "TCP" | "UDP" | "ICMP";
export type PacketStatus = "success" | "dropped" | "high_latency";

export interface GeoLocation {
  ip: string;
  lat: number;
  lng: number;
  name?: string;
}

export interface NetworkPacket {
  id: string;
  source: GeoLocation;
  destination: GeoLocation;
  protocol: Protocol;
  status: PacketStatus;
  payloadSize: number;
  timestamp: number;
}

export interface NodeData {
  id: string;
  ip: string;
  lat: number;
  lng: number;
  name: string;
  type: "server" | "client";
  region: string;
}

export interface PacketAnimation {
  packet: NetworkPacket;
  progress: number;
  paused: boolean;
  speed: number;
}

export interface PacketStats {
  totalSent: number;
  successCount: number;
  droppedCount: number;
  highLatencyCount: number;
  dropRate: number;
}
