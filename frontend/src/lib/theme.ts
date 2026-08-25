/**
 * Cyber Theme —— 全局唯一视觉常量来源。
 * 组件不得自行散落定义颜色，一律引用此文件或 CSS 变量。
 */
export const cyber = {
  bgDeep: "#020611",
  bgBase: "#050B14",
  bgPanel: "#08111F",

  cyan: "#00E5FF",
  blue: "#00B8FF",
  mint: "#00FFD5",
  violet: "#6C63FF",
  purple: "#8B5CF6",
  amber: "#F59E0B",
  red: "#EF4444",
  green: "#34D399",

  textPrimary: "#E6F1FF",
  textSecondary: "#8FA3BF",
  textDim: "#4A5A73",

  borderFaint: "rgba(0, 229, 255, 0.10)",
  borderSoft: "rgba(0, 229, 255, 0.22)",
} as const;

/** 方向 → 主色（AGENTS.md §14） */
export function directionColor(direction: string): string {
  switch (direction) {
    case "outbound":
      return cyber.cyan;
    case "inbound":
      return cyber.purple;
    case "internal":
      return cyber.green;
    default:
      return cyber.cyan;
  }
}

export function statusColor(status: string | null | undefined): string {
  if (!status) return cyber.textSecondary;
  if (status.includes("关闭")) return cyber.textDim;
  if (status.includes("等待") || status.includes("请求")) return cyber.amber;
  if (status.includes("已连接")) return cyber.mint;
  return cyber.textSecondary;
}

export function flagColor(flag: string | null | undefined): string | null {
  switch (flag) {
    case "failed":
      return cyber.red;
    case "lost":
      return cyber.amber;
    case "high_latency":
      return cyber.amber;
    default:
      return null;
  }
}
