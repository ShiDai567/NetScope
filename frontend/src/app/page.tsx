"use client";

import dynamic from "next/dynamic";

const Dashboard = dynamic(() => import("@/components/Dashboard"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-screen items-center justify-center bg-[#03050a] text-cyan-400">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
        <span className="font-mono text-sm tracking-wider">NetScope 初始化中</span>
      </div>
    </div>
  ),
});

export default function Home() {
  return <Dashboard />;
}
