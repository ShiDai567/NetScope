import { create } from "zustand";
import type {
  ConnectionState,
  DeviceInfo,
  EventEntry,
  NetworkFlow,
  PublicNode,
  Scene,
  StatsSnapshot,
  TimeWindow,
} from "@/lib/types";

/** 前端实时数据上限：超出即淘汰最旧（AGENTS.md §35） */
export const MAX_EVENTS = 5000;
export const EVENT_STREAM_VISIBLE = 400;

export interface GatewayInfo {
  lat: number;
  lng: number;
}

interface NetworkState {
  // ---- 数据链路
  connState: ConnectionState;
  apiError: boolean;
  mode: "ikuai";
  serverTime: number;
  serverOffset: number; // server_time - client_time，用于对齐时间戳
  lastSeq: number;
  lastDataAt: number;

  // ---- 实时数据
  stats: StatsSnapshot | null;
  devices: DeviceInfo[];
  nodes: PublicNode[];
  gateway: GatewayInfo;
  ikuaiError: string | null;
  ikuaiRouter: string | null;
  /** 最近连接快照：同 id 后到覆盖先到；按 seq 升序追加 */
  flows: NetworkFlow[];
  /** 派生事件流（首次出现 / 状态跃迁 / 终态） */
  events: EventEntry[];

  // ---- UI
  booted: boolean;
  scene: Scene;
  timeWindow: TimeWindow;
  selectedId: string | null;

  // ---- actions
  setConnState: (s: ConnectionState) => void;
  setApiError: (v: boolean) => void;
  ingestFlows: (flows: NetworkFlow[], serverTime: number, lastSeq: number) => void;
  setStats: (s: StatsSnapshot) => void;
  setDevices: (d: DeviceInfo[]) => void;
  setNodes: (n: PublicNode[]) => void;
  setGateway: (lat: number, lng: number) => void;
  setIkuaiInfo: (info: { routerUrl: string | null; error: string | null }) => void;
  setBooted: (v: boolean) => void;
  setScene: (s: Scene) => void;
  setTimeWindow: (t: TimeWindow) => void;
  selectFlow: (id: string | null) => void;
}

/**
 * flows 采用「同 id 覆盖」策略：
 * 一条连接的生命周期事件只保留最新快照，
 * 事件流的跃迁记录由传输层在 ingest 时对比产生。
 */
export const useNetworkStore = create<NetworkState>((set) => ({
  connState: "connecting",
  apiError: false,
  mode: "ikuai",
  serverTime: 0,
  serverOffset: 0,
  lastSeq: 0,
  lastDataAt: 0,

  stats: null,
  devices: [],
  nodes: [],
  gateway: { lat: 39.9042, lng: 116.4074 },
  ikuaiError: null,
  ikuaiRouter: null,
  flows: [],
  events: [],

  booted: false,
  scene: "global",
  timeWindow: 300,
  selectedId: null,

  setConnState: (connState) => set({ connState }),
  setApiError: (apiError) => set({ apiError }),

  ingestFlows: (incoming, serverTime, lastSeq) =>
    set((state) => {
      const byId = new Map<string, NetworkFlow>();
      for (const f of state.flows) byId.set(f.id, f);
      const prevStatus = new Map<string, string | null>();
      for (const [id, f] of byId) prevStatus.set(id, f.status);
      const prevFlag = new Map<string, NetworkFlow["flag"]>();
      for (const [id, f] of byId) prevFlag.set(id, f.flag);

      const newEvents: EventEntry[] = [];
      for (const flow of incoming) {
        const existed = byId.has(flow.id);
        byId.set(flow.id, flow);

        const statusChanged = prevStatus.get(flow.id) !== flow.status;
        const flagChanged = prevFlag.get(flow.id) !== flow.flag;
        if (!existed || statusChanged || flagChanged) {
          newEvents.push({
            id: `${flow.id}:${flow.seq}`,
            seq: flow.seq,
            timestamp: flow.timestamp,
            direction: flow.direction,
            source: flow.source.ip,
            destination: flow.destination.ip,
            protocol: flow.protocol,
            port: flow.destination.port,
            application: flow.application,
            bytesTotal: flow.bytes.total,
            status: flow.status,
            flag: flow.flag,
          });
        }
      }

      // 上限裁剪
      let flows = Array.from(byId.values());
      if (flows.length > MAX_EVENTS) {
        flows = flows.slice(flows.length - MAX_EVENTS);
      }

      let events = newEvents.length
        ? [...newEvents.reverse(), ...state.events]
        : state.events;
      if (events.length > MAX_EVENTS) {
        events = events.slice(0, MAX_EVENTS);
      }

      return {
        flows,
        events,
        serverTime,
        lastSeq,
        serverOffset: serverTime ? serverTime - Date.now() / 1000 : state.serverOffset,
        lastDataAt: Date.now(),
      };
    }),

  setStats: (stats) => set({ stats, mode: stats.mode }),
  setDevices: (devices) => set({ devices }),
  setNodes: (nodes) => set({ nodes }),
  setGateway: (lat, lng) => set({ gateway: { lat, lng } }),
  setIkuaiInfo: ({ routerUrl, error }) =>
    set({ ikuaiRouter: routerUrl, ikuaiError: error }),
  setBooted: (booted) => set({ booted }),
  setScene: (scene) => set({ scene }),
  setTimeWindow: (timeWindow) => set({ timeWindow }),
  selectFlow: (selectedId) => set({ selectedId }),
}));

// ---------------------------------------------------------------- 选择器

export function selectSelectedFlow(state: NetworkState): NetworkFlow | null {
  if (!state.selectedId) return null;
  return state.flows.find((f) => f.id === state.selectedId) ?? null;
}

/**
 * 时间窗口过滤请使用 hooks/useWindowedFlows ——
 * 不要把返回新数组的方法直接当作 zustand 选择器（不稳定快照会导致无限更新）。
 */
