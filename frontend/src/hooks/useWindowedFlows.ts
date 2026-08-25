"use client";

import { useMemo } from "react";
import type { NetworkFlow } from "@/lib/types";
import { useNetworkStore } from "@/store/networkStore";

/**
 * 时间窗口内的流列表。
 *
 * 注意：不能把 `.filter()` 直接作为 zustand 选择器 ——
 * 每次返回新数组会制造不稳定快照，触发 React 无限更新。
 * 这里订阅原始引用，再经 useMemo 派生。
 */
export function useWindowedFlows(): NetworkFlow[] {
  const flows = useNetworkStore((s) => s.flows);
  const offset = useNetworkStore((s) => s.serverOffset);
  const win = useNetworkStore((s) => s.timeWindow);

  return useMemo(() => {
    const cutoff = Date.now() / 1000 - offset - win;
    return flows.filter((f) => f.timestamp >= cutoff);
  }, [flows, offset, win]);
}
