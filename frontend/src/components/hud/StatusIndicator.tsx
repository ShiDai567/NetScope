"use client";

/** 状态指示点：● ONLINE / ● CONNECTED 等 */
export function StatusIndicator({
  color,
  label,
  pulse = true,
  size = "md",
}: {
  color: string;
  label: string;
  pulse?: boolean;
  size?: "sm" | "md";
}) {
  const dot = size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2";
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`${dot} rounded-full ${pulse ? "pulse-dot" : ""}`}
        style={{ background: color, color }}
      />
      <span
        className="font-mono tracking-[0.22em]"
        style={{ color, fontSize: "10px" }}
      >
        {label}
      </span>
    </span>
  );
}
