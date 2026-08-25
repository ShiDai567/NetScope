/** 数值格式化工具 —— 全部容错，非法输入返回占位符 */

const DASH = "--";

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return DASH;
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ["KB", "MB", "GB", "TB", "PB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v >= 100 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}

export function formatBps(bps: number | null | undefined): string {
  if (bps == null || !Number.isFinite(bps) || bps < 0) return DASH;
  if (bps < 1000) return `${Math.round(bps)} bps`;
  const units = ["Kbps", "Mbps", "Gbps", "Tbps"];
  let v = bps / 1000;
  let i = 0;
  while (v >= 1000 && i < units.length - 1) {
    v /= 1000;
    i += 1;
  }
  return `${v >= 100 ? Math.round(v) : v.toFixed(2)} ${units[i]}`;
}

export function formatRate(bytesPerSec: number | null | undefined): string {
  if (bytesPerSec == null || !Number.isFinite(bytesPerSec)) return DASH;
  return formatBps(bytesPerSec * 8);
}

export function formatCount(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return DASH;
  if (Math.abs(n) >= 1_000_000)
    return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (Math.abs(n) >= 10_000) return `${(n / 1000).toFixed(1)}K`;
  return Math.round(n).toLocaleString("en-US");
}

export function formatPercent(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return DASH;
  return `${v.toFixed(digits)}%`;
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return DASH;
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  return `${ms.toFixed(ms < 10 ? 1 : 0)} ms`;
}

/** 服务器秒时间戳 → HH:MM:SS */
export function formatClock(timestampSec: number): string {
  if (!Number.isFinite(timestampSec)) return "--:--:--";
  const d = new Date(timestampSec * 1000);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function formatDateTime(d: Date): string {
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(
    d.getHours()
  )}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** 端点展示：ip:port 或 domain */
export function endpointLabel(
  ip: string | undefined,
  port: number | undefined,
  domain?: string | null
): string {
  const safeIp = ip && ip !== "--" ? ip : "未知地址";
  const host = domain && domain !== "--" ? domain : safeIp;
  if (!port || port <= 0) return host;
  return `${host}:${port}`;
}
