// 语义颜色：严格遵循 AGENTS.md 规范

export const STATUS_COLORS: Record<string, string> = {
  等待连接: "#fbbf24", // 黄色呼吸灯
  请求连接: "#f59e0b", // 黄色快速跳动
  已连接: "#10b981", // 绿色稳定流动
  关闭连接: "#94a3b8", // 灰色淡出
};

export const PROTOCOL_COLORS: Record<string, string> = {
  tcp: "#38bdf8", // 蓝色
  udp: "#34d399", // 绿色
  icmp: "#fbbf24", // 黄色
};

export const FLAG_COLORS: Record<string, string> = {
  failed: "#f43f5e", // 红色爆炸/丢包
  lost: "#f43f5e",
  high_latency: "#fbbf24", // 黄色高延迟
};

export const NODE_COLORS: Record<string, string> = {
  server: "#f43f5e", // 外网服务器 红色发光
  client: "#38bdf8", // 公网客户端 蓝色发光
  gateway: "#f59e0b",
};

export const UI_ACCENT = "#22d3ee";
