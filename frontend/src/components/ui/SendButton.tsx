"use client";

import { useCallback } from "react";
import { PaperPlaneRight } from "@phosphor-icons/react";
import { usePacketStore } from "@/store/packetStore";
import { generatePacket } from "@/lib/packetGenerator";

export default function SendButton() {
  const addPacket = usePacketStore((state) => state.addPacket);

  const handleSend = useCallback(() => {
    const packet = generatePacket();
    addPacket(packet);
  }, [addPacket]);

  return (
    <button
      onClick={handleSend}
      className="group relative w-full bg-accent/10 hover:bg-accent/20 border border-accent/30 hover:border-accent/50 rounded-xl p-4 transition-all duration-300 active:scale-[0.98]"
    >
      <div className="flex items-center justify-center gap-3">
        <div className="relative">
          <PaperPlaneRight
            className="w-5 h-5 text-accent group-hover:translate-x-0.5 transition-transform duration-300"
            weight="fill"
          />
          <div className="absolute inset-0 bg-accent/30 blur-lg rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </div>
        <span className="text-sm font-medium text-accent tracking-wide">
          发送数据包
        </span>
      </div>
      <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-accent/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
    </button>
  );
}
