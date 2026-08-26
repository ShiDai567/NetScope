"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api/client";
import { adaptPacket, type NormalizeResult } from "@/lib/adapters/packet";
import type { NetworkFlow } from "@/lib/types";
import { useNetworkStore } from "@/store/networkStore";

/**
 * 实时数据链路（当前为轮询传输，接口与 WebSocket 传输等价可替换）：
 *
 *   Django API ──poll──▶ Buffer ──80ms 批量──▶ Adapter ──▶ Store
 *
 * - 数据包轮询：900ms 周期，失败指数退避至 6s
 * - 统计轮询：2s；设备/节点轮询：5s
 * - 每批数据一次性提交 store，避免逐条触发 React 渲染
 */

const PACKET_INTERVAL = 900;
const STATS_INTERVAL = 2000;
const DEVICES_INTERVAL = 5000;
const FLUSH_MS = 80;
const MAX_BACKOFF = 5400;

export function useNetworkStream(): void {
  const seqRef = useRef(0);
  const bufferRef = useRef<NormalizeResult[]>([]);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestServerTimeRef = useRef(0);

  useEffect(() => {
    let stopped = false;
    let packetTimer: ReturnType<typeof setTimeout> | null = null;
    let backoff = 0;

    const flush = () => {
      flushTimerRef.current = null;
      const batch = bufferRef.current;
      bufferRef.current = [];
      if (batch.length === 0) return;

      const flows: NetworkFlow[] = [];
      for (const item of batch) {
        if (item.flow) flows.push(item.flow);
      }
      if (flows.length === 0) return;
      useNetworkStore.getState().ingestFlows(
        flows,
        latestServerTimeRef.current,
        seqRef.current
      );
    };

    const scheduleFlush = () => {
      if (flushTimerRef.current != null) return;
      flushTimerRef.current = setTimeout(flush, FLUSH_MS);
    };

    // ---- 数据包轮询
    const pollPackets = async () => {
      if (stopped) return;
      let failed = false;
      try {
        const data = await api.packets(seqRef.current);
        if (stopped) return;
        if (!data) {
          failed = true;
        } else {
          latestServerTimeRef.current = data.server_time || latestServerTimeRef.current;
          seqRef.current = data.last_seq ?? seqRef.current;
          const store = useNetworkStore.getState();
          store.setConnState("connected");
          if (store.apiError && data.events.length === 0) store.setApiError(false);
          if (data.events?.length) {
            for (const ev of data.events) bufferRef.current.push(adaptPacket(ev));
            scheduleFlush();
          }
        }
      } catch {
        failed = true;
      }

      if (failed) {
        useNetworkStore.getState().setConnState("disconnected");
        backoff = Math.min(MAX_BACKOFF, backoff + PACKET_INTERVAL * 2);
      } else {
        backoff = 0;
      }
      packetTimer = setTimeout(pollPackets, PACKET_INTERVAL + backoff);
    };

    // ---- 统计轮询
    void (async () => {
      while (!stopped) {
        const s = await api.stats();
        if (!stopped && s) {
          useNetworkStore.getState().setStats(s);
        }
        await new Promise((r) => setTimeout(r, STATS_INTERVAL));
      }
    })();

    // ---- 模式 / 网关 / iKuai 状态 / 地理纪元
    const pollMode = async () => {
      while (!stopped) {
        const m = await api.mode();
        if (!stopped && m) {
          const store = useNetworkStore.getState();
          if (
            typeof m.gateway?.lat === "number" &&
            typeof m.gateway?.lng === "number"
          ) {
            store.setGateway(m.gateway.lat, m.gateway.lng);
          }
          // 核心位置变更（SERVER_LOCATION 改动 / 重定位）：清空旧伪坐标流
          if (typeof m.geo_epoch === "number") {
            store.handleGeoEpoch(
              m.geo_epoch,
              typeof m.gateway?.lat === "number" ? m.gateway.lat : undefined,
              typeof m.gateway?.lng === "number" ? m.gateway.lng : undefined
            );
          }
          store.setIkuaiInfo({
            routerUrl: m.ikuai?.router_url ?? null,
            error: m.ikuai?.error ?? null,
          });
        }
        await new Promise((r) => setTimeout(r, 8000));
      }
    };
    void pollMode();

    // ---- 设备/节点轮询
    void (async () => {
      while (!stopped) {
        const [d, n] = await Promise.all([api.devices(), api.nodes()]);
        if (!stopped) {
          if (d) useNetworkStore.getState().setDevices(d);
          if (n) useNetworkStore.getState().setNodes(n);
        }
        await new Promise((r) => setTimeout(r, DEVICES_INTERVAL));
      }
    })();

    void pollPackets();

    return () => {
      stopped = true;
      if (packetTimer) clearTimeout(packetTimer);
      if (flushTimerRef.current != null) clearTimeout(flushTimerRef.current);
    };
  }, []);
}
