"use client";

import { Globe, Pulse } from "@phosphor-icons/react";

export default function Header() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 glass border-b border-border-subtle">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Globe className="w-6 h-6 text-accent" weight="fill" />
            <div className="absolute inset-0 bg-accent/20 blur-lg rounded-full" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-foreground">
              NetScope
            </h1>
            <p className="text-[10px] font-mono text-foreground/40 uppercase tracking-wider">
              Network Packet Flow Visualization
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-green-400/10 border border-green-400/20">
            <Pulse className="w-3 h-3 text-green-400 animate-pulse" weight="fill" />
            <span className="text-[10px] font-mono text-green-400 uppercase tracking-wider">
              实时监控中
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
