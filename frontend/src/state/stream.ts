"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type {
  DeviceInfo,
  DirectionFilter,
  PacketEvent,
  ProtocolFilter,
  PublicNode,
  StatsSnapshot,
} from "@/lib/types";

interface ReplayState {
  active: boolean;
  clock: number;
  speed: number;
  paused: boolean;
  rangeStart: number;
  rangeEnd: number;
}

export function usePacketStream() {
  const eventLogRef = useRef<Map<string, PacketEvent[]>>(new Map());
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [nodes, setNodes] = useState<PublicNode[]>([]);
  const [stats, setStats] = useState<StatsSnapshot | null>(null);
  const [mode, setMode] = useState<string>("simulation");
  const [lastSeq, setLastSeq] = useState(0);
  const [serverTime, setServerTime] = useState(0);
  const [replay, setReplay] = useState<ReplayState>({
    active: false,
    clock: 0,
    speed: 1,
    paused: false,
    rangeStart: 0,
    rangeEnd: 0,
  });
  const [filters, setFilters] = useState<{
    direction: DirectionFilter;
    protocol: ProtocolFilter;
    app: string;
  }>({ direction: "all", protocol: "all", app: "all" });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [lockedId, setLockedId] = useState<string | null>(null);
  const [tick, setTick] = useState(0); // 用于触发重绘的版本号

  const seqRef = useRef(0);
  const liveRef = useRef(true);

  // 合并事件到日志
  const ingest = useCallback((events: PacketEvent[]) => {
    const log = eventLogRef.current;
    for (const ev of events) {
      const arr = log.get(ev.id);
      if (arr) {
        arr.push(ev);
      } else {
        log.set(ev.id, [ev]);
      }
    }
    // 清理过旧事件（保留 15 分钟）
    const cutoff = Date.now() / 1000 - 900;
    for (const [id, arr] of log) {
      const keep = arr.filter((e) => e.timestamp >= cutoff);
      if (keep.length === 0) log.delete(id);
      else log.set(id, keep);
    }
  }, []);

  // 轮询数据包
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    const poll = async () => {
      try {
        const data = await api.packets(seqRef.current);
        seqRef.current = data.last_seq;
        setLastSeq(data.last_seq);
        setServerTime(data.server_time);
        if (data.events.length) {
          ingest(data.events);
          if (!replay.active) setTick((t) => t + 1);
        }
      } catch {
        // 静默容错
      }
    };
    poll();
    timer = setInterval(poll, 1000);
    return () => clearInterval(timer);
  }, [ingest, replay.active]);

  // 轮询统计
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    const poll = async () => {
      try {
        const s = await api.stats();
        setStats(s);
        setMode(s.mode);
      } catch {
        // 静默容错
      }
    };
    poll();
    timer = setInterval(poll, 2000);
    return () => clearInterval(timer);
  }, []);

  // 轮询设备与节点
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    const poll = async () => {
      try {
        const d = await api.devices();
        setDevices(d.devices);
        const n = await api.nodes();
        setNodes(n.nodes);
      } catch {
        // 静默容错
      }
    };
    poll();
    timer = setInterval(poll, 5000);
    return () => clearInterval(timer);
  }, []);

  // 回放时钟推进
  useEffect(() => {
    if (!replay.active || replay.paused) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setReplay((prev) => {
        const nextClock = prev.clock + dt * prev.speed;
        if (nextClock >= prev.rangeEnd) {
          return { ...prev, clock: prev.rangeEnd, paused: true };
        }
        return { ...prev, clock: nextClock };
      });
      setTick((t) => t + 1);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [replay.active, replay.paused, replay.speed]);

  // 进入回放模式时拉取历史
  const enterReplay = useCallback(async (minutes = 10) => {
    try {
      const data = await api.history(minutes);
      const log = new Map<string, PacketEvent[]>();
      for (const ev of data.events) {
        const arr = log.get(ev.id);
        if (arr) arr.push(ev);
        else log.set(ev.id, [ev]);
      }
      eventLogRef.current = log;
      const start = data.server_time - minutes * 60;
      const end = data.server_time;
      setReplay({
        active: true,
        clock: end,
        speed: 1,
        paused: false,
        rangeStart: start,
        rangeEnd: end,
      });
      setTick((t) => t + 1);
    } catch (e) {
      console.error("enterReplay failed", e);
    }
  }, []);

  const exitReplay = useCallback(() => {
    setReplay({
      active: false,
      clock: 0,
      speed: 1,
      paused: false,
      rangeStart: 0,
      rangeEnd: 0,
    });
    eventLogRef.current = new Map();
    seqRef.current = 0;
    setTick((t) => t + 1);
  }, []);

  const setReplaySpeed = useCallback((speed: number) => {
    setReplay((p) => ({ ...p, speed }));
  }, []);

  const togglePause = useCallback(() => {
    setReplay((p) => ({ ...p, paused: !p.paused }));
  }, []);

  const seekReplay = useCallback((clock: number) => {
    setReplay((p) => ({ ...p, clock, paused: true }));
    setTick((t) => t + 1);
  }, []);

  const setFilter = useCallback(
    (key: "direction" | "protocol" | "app", value: string) => {
      setFilters((f) => ({ ...f, [key]: value }));
    },
    []
  );

  // 计算当前时刻的可见包（用于 Canvas 渲染）
  const getVisiblePackets = useCallback(
    (clock?: number): Map<string, PacketEvent> => {
      const t = clock ?? (replay.active ? replay.clock : serverTime || Date.now() / 1000);
      const log = eventLogRef.current;
      const out = new Map<string, PacketEvent>();
      for (const [id, arr] of log) {
        // 找 <= t 的最新事件
        let latest: PacketEvent | null = null;
        for (const ev of arr) {
          if (ev.timestamp <= t) latest = ev;
        }
        if (!latest) continue;
        // 存活判定
        const age = t - latest.timestamp;
        const isTerminal =
          latest.status === "关闭连接" ||
          latest.flag === "failed" ||
          latest.flag === "lost";
        const ttl = isTerminal ? 3.0 : 14.0;
        if (age > ttl) continue;
        // 过滤
        if (filters.direction !== "all" && latest.direction !== filters.direction) continue;
        if (filters.protocol !== "all" && latest.protocol !== filters.protocol) continue;
        if (filters.app !== "all" && latest.app_name !== filters.app) continue;
        out.set(id, latest);
      }
      return out;
    },
    [replay.active, replay.clock, serverTime, filters.direction, filters.protocol, filters.app]
  );

  return {
    eventLogRef,
    devices,
    nodes,
    stats,
    mode,
    lastSeq,
    serverTime,
    replay,
    filters,
    hoveredId,
    lockedId,
    tick,
    setHoveredId,
    setLockedId,
    enterReplay,
    exitReplay,
    setReplaySpeed,
    togglePause,
    seekReplay,
    setFilter,
    getVisiblePackets,
  };
}
