import { NetworkPacket, Protocol, PacketStatus, GeoLocation, NodeData } from "@/types/packet";
import { nodes } from "./nodes";

let packetIdCounter = 0;

function generateId(): string {
  packetIdCounter++;
  return `pkt_${String(packetIdCounter).padStart(4, "0")}`;
}

function randomProtocol(): Protocol {
  const protocols: Protocol[] = ["TCP", "UDP", "ICMP"];
  return protocols[Math.floor(Math.random() * protocols.length)];
}

function randomStatus(): PacketStatus {
  const rand = Math.random();
  if (rand < 0.75) return "success";
  if (rand < 0.9) return "high_latency";
  return "dropped";
}

function randomPayloadSize(): number {
  return Math.floor(Math.random() * 1400) + 64;
}

export function generatePacket(
  sourceOverride?: GeoLocation,
  destinationOverride?: GeoLocation
): NetworkPacket {
  const serverNodes = nodes.filter((n) => n.type === "server");
  const clientNodes = nodes.filter((n) => n.type === "client");

  const sourceNode: NodeData =
    (sourceOverride as unknown as NodeData) ||
    (Math.random() > 0.5
      ? serverNodes[Math.floor(Math.random() * serverNodes.length)]
      : clientNodes[Math.floor(Math.random() * clientNodes.length)]);

  const destinationNode: NodeData =
    (destinationOverride as unknown as NodeData) ||
    (sourceNode.type === "server"
      ? clientNodes[Math.floor(Math.random() * clientNodes.length)]
      : serverNodes[Math.floor(Math.random() * serverNodes.length)]);

  return {
    id: generateId(),
    source: {
      ip: sourceNode.ip,
      lat: sourceNode.lat,
      lng: sourceNode.lng,
    },
    destination: {
      ip: destinationNode.ip,
      lat: destinationNode.lat,
      lng: destinationNode.lng,
    },
    protocol: randomProtocol(),
    status: randomStatus(),
    payloadSize: randomPayloadSize(),
    timestamp: Date.now(),
  };
}

export function generatePackets(count: number): NetworkPacket[] {
  return Array.from({ length: count }, () => generatePacket());
}
