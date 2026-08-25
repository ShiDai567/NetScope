"use client";

import { useEffect } from "react";
import { formatBytes, endpointLabel, formatClock, formatMs } from "@/lib/format";
import { cyber, directionColor, statusColor } from "@/lib/theme";
import type { NetworkFlow } from "@/lib/types";
import { selectSelectedFlow, useNetworkStore } from "@/store/networkStore";

const DIR_LABEL: Record<NetworkFlow["direction"], string> = {
  outbound: "出站 · OUTBOUND",
  inbound: "入站 · INBOUND",
  internal: "内网 · INTERNAL",
};

/**
 * 连接详情 —— 点击数据流/事件后的完整信息。
 * Inbound 时展示视觉化 NAT Pipeline：
 *   公网来源 ↓ NAT 转换 ↓ 转发地址 ↓ 内网目标
 */
export function ConnectionDetails() {
  const selectedId = useNetworkStore((s) => s.selectedId);
  const flow = useNetworkStore(selectSelectedFlow);
  const selectFlow = useNetworkStore((s) => s.selectFlow);

  // Escape 关闭（键盘操作不加动画）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") selectFlow(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectFlow]);

  if (!selectedId || !flow) return null;

  const accent = directionColor(flow.direction);
  const nat = flow.nat;

  return (
    <aside
      className="details-in hud-panel absolute bottom-3 right-3 top-3 z-30 flex w-[320px] flex-col"
      role="dialog"
      aria-label="连接详情"
    >
      <i className="hud-corner hud-corner-tl" aria-hidden />
      <i className="hud-corner hud-corner-tr" aria-hidden />
      <i className="hud-corner hud-corner-bl" aria-hidden />
      <i className="hud-corner hud-corner-br" aria-hidden />

      <header className="flex shrink-0 items-center justify-between border-b border-cyan-400/15 px-3 py-2">
        <h2 className="panel-title" style={{ color: accent }}>
          连接详情
        </h2>
        <button
          onClick={() => selectFlow(null)}
          className="px-1 font-mono text-[11px] text-slate-500 transition-colors duration-150 hover:text-slate-200"
          aria-label="关闭详情"
        >
          ✕
        </button>
      </header>

      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {/* 方向徽标 */}
        <div className="mb-3 flex items-center gap-2">
          <span
            className="border px-2 py-0.5 font-mono text-[9px] tracking-[0.18em]"
            style={{ color: accent, borderColor: `${accent}55` }}
          >
            {DIR_LABEL[flow.direction]}
          </span>
          <span
            className="font-mono text-[9px] tracking-[0.14em]"
            style={{ color: statusColor(flow.status) }}
          >
            {flow.status ?? "无状态（UDP / ICMP）"}
          </span>
        </div>

        <Row label="源地址">
          {endpointLabel(flow.source.ip, flow.source.port, flow.source.domain)}
        </Row>
        <Row label="目标地址">
          {endpointLabel(
            flow.destination.ip,
            flow.destination.port,
            flow.destination.domain
          )}
        </Row>
        <Row label="应用">{flow.application}</Row>
        <Row label="协议">{flow.protocol.toUpperCase()}</Row>
        {typeof flow.latencyMs === "number" && (
          <Row label="延迟">{formatMs(flow.latencyMs)}</Row>
        )}
        <Row label="上传量">{formatBytes(flow.bytes.upload)}</Row>
        <Row label="下载量">{formatBytes(flow.bytes.download)}</Row>
        <Row label="总量">{formatBytes(flow.bytes.total)}</Row>
        <Row label="首次出现">{formatClock(flow.born)}</Row>
        <Row label="最近事件">{formatClock(flow.timestamp)}</Row>
        {flow.interface && <Row label="网卡接口">{flow.interface}</Row>}

        {/* NAT Pipeline */}
        {nat && (
          <div className="mt-4 border border-violet-400/25 bg-violet-400/[0.04] p-3">
            <p className="panel-title mb-2.5" style={{ color: cyber.purple }}>
              NAT 转发链路
            </p>
            <NatStep
              title={flow.direction === "inbound" ? "公网来源" : "内网来源"}
              value={endpointLabel(
                flow.source.ip,
                nat.sourcePort ?? flow.source.port
              )}
              color={cyber.purple}
            />
            <PipelineArrow label="NAT 转换" color={cyber.violet} />
            <NatStep
              title="转发地址"
              value={`${nat.forwardAddress ?? "--"}:${
                nat.destinationPort ?? flow.destination.port
              }`}
              color={cyber.blue}
            />
            {nat.originalDestination && (
              <>
                <PipelineArrow label="端口映射" color={cyber.violet} />
                <NatStep
                  title="原始目标"
                  value={nat.originalDestination}
                  color={cyber.cyan}
                />
              </>
            )}
            <PipelineArrow
              label={flow.direction === "inbound" ? "内网目标" : "公网目标"}
              color={accent}
            />
            <NatStep
              title={
                flow.direction === "inbound" ? "局域网端点" : "远程端点"
              }
              value={endpointLabel(
                flow.destination.ip,
                flow.destination.port,
                flow.destination.domain
              )}
              color={accent}
            />
          </div>
        )}
      </div>
    </aside>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-white/[0.04] py-[7px]">
      <span className="shrink-0 font-mono text-[10px] tracking-[0.2em] text-slate-600">
        {label}
      </span>
      <span className="truncate text-right font-mono text-[11px] text-slate-200">
        {children}
      </span>
    </div>
  );
}

function NatStep({
  title,
  value,
  color,
}: {
  title: string;
  value: string;
  color: string;
}) {
  return (
    <div>
      <p className="font-mono text-[9px] tracking-[0.24em]" style={{ color }}>
        {title}
      </p>
      <p className="mt-0.5 truncate rounded-sm bg-black/30 px-2 py-1 font-mono text-[11px] text-slate-100">
        {value}
      </p>
    </div>
  );
}

function PipelineArrow({ label, color }: { label: string; color: string }) {
  return (
    <div className="flex items-center gap-2 py-1 pl-4" aria-hidden>
      <span className="font-mono text-[12px] leading-none" style={{ color }}>
        ↓
      </span>
      <span className="font-mono text-[9px] tracking-[0.26em] text-slate-600">
        {label}
      </span>
    </div>
  );
}
