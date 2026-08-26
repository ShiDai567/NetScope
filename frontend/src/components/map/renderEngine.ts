import {
  BASE_H,
  BASE_W,
  buildArc,
  createMapper,
  projectX,
  projectY,
  type ArcGeometry,
  type ScreenMapper,
  type ViewTransform,
  ViewAnimator,
} from "@/lib/network/projection";
import { cyber, directionColor } from "@/lib/theme";
import { countryZh } from "@/lib/network/countryNames";
import { formatBytes, formatCount, formatRate } from "@/lib/format";
import type { AggregatedFlow, Scene } from "@/lib/types";
import { useNetworkStore } from "@/store/networkStore";

// ---------------------------------------------------------------- 常量

const FLOW_TTL = 14; // 连接在地图上的存活窗口（秒）
const TERMINAL_TTL = 4;
const AGG_REFRESH_MS = 500;
const MAX_PARTICLES = 520;

const VIEW_PRESETS: Record<Scene, ViewTransform> = {
  // 视点取本初子午线附近，保证世界地图水平居中（配合东西环绕无死边）
  global: { cx: projectX(12), cy: projectY(24), scale: 1 },
  china: { cx: projectX(104.5), cy: projectY(36), scale: 4.6 },
  lan: { cx: -1, cy: -1, scale: 15 }, // cx/cy 运行时以网关坐标填充
};

const LAN_GEO_FADE_START = 5.5;
const LAN_GEO_FADE_END = 9.5;
const LAN_LABEL_SCALE = 9;

export interface HoverPayload {
  kind: "flow" | "node" | "country" | "province" | "device" | "core";
  x: number;
  y: number;
  title: string;
  subtitle?: string;
  rows: [string, string][];
  accent: string;
  flowId?: string;
}

interface EngineCallbacks {
  onHover: (h: HoverPayload | null) => void;
  onClick: (h: HoverPayload | null) => void;
}

interface Particle {
  t: number;
  speed: number;
  delay: number;
}

interface FlowEffect {
  x: number;
  y: number;
  born: number;
  color: string;
}

interface ActiveAgg extends AggregatedFlow {
  geomCache: Map<number, ArcGeometry>; // key = mapper epoch，避免每帧重建
  particles: Particle[];
  spawnAcc: number;
  effectDone: Set<string>;
}

// ---------------------------------------------------------------- 工具

function quantize(v: number): number {
  return Math.round(v * 2) / 2;
}

function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

// ---------------------------------------------------------------- 引擎

export class RenderEngine {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private cbs: EngineCallbacks;
  private dpr = 1;
  private width = 0;
  private height = 0;
  private raf = 0;
  private disposed = false;

  private scene: Scene = "global";
  private view: ViewTransform = { ...VIEW_PRESETS.global };
  private animator: ViewAnimator | null = null;
  private mapperEpoch = 0;

  private geoReady = false;
  private countryPaths: {
    name: string;
    zh: string;
    path: Path2D;
  }[] = [];
  private provinceMeta: { name: string; path: Path2D }[] = [];
  private graticulePath: Path2D | null = null;

  private aggs = new Map<string, ActiveAgg>();
  private lastAggAt = 0;
  private effects: FlowEffect[] = [];
  private announcedNodes = new Map<string, number>();
  private stars: { x: number; y: number; r: number; ph: number }[] = [];

  private hoverTarget: HoverPayload | null = null;
  private mouseX = -1;
  private mouseY = -1;
  private mouseInside = false;
  private reducedMotion = false;
  private bootedAt = performance.now();

  constructor(canvas: HTMLCanvasElement, cbs: EngineCallbacks) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) throw new Error("Canvas 2D 不可用");
    this.ctx = ctx;
    this.cbs = cbs;
    this.reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    this.resize();
    this.loadGeo();
    this.bindEvents();
    this.loop = this.loop.bind(this);
    this.raf = requestAnimationFrame(this.loop);
  }

  // ------------------------------------------------------------- 生命周期

  setScene(scene: Scene) {
    if (scene === this.scene) return;
    this.scene = scene;
    const target =
      scene === "lan"
        ? this.lanView()
        : (VIEW_PRESETS[scene] as ViewTransform);
    this.animator = new ViewAnimator({ ...this.view }, target, 1150);
  }

  refreshTo(scene: Scene) {
    // 无动画直接对齐（启动时使用）
    this.scene = scene;
    this.view =
      scene === "lan" ? this.lanView() : { ...VIEW_PRESETS[scene] };
    this.animator = null;
    this.mapperEpoch += 1;
  }

  dispose() {
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.unbindEvents();
  }

  private lanView(): ViewTransform {
    const g = useNetworkStore.getState().gateway;
    return {
      cx: projectX(g.lng),
      cy: projectY(g.lat),
      scale: VIEW_PRESETS.lan.scale,
    };
  }

  // ------------------------------------------------------------- 地理数据

  private async loadGeo() {
    interface GeoFeature {
      properties?: { name?: unknown } | null;
      geometry?: { type?: string; coordinates?: unknown } | null;
    }
    interface GeoCollection {
      features?: GeoFeature[];
    }
    try {
      const [worldRes, chinaRes] = await Promise.all([
        fetch("/maps/world.json"),
        fetch("/maps/china.json"),
      ]);
      const world = (await worldRes.json()) as GeoCollection;
      const china = (await chinaRes.json()) as GeoCollection;

      const countries: { name: string; zh: string; path: Path2D }[] = [];
      for (const f of world.features ?? []) {
        const path = featurePath(f);
        if (!path) continue;
        const name =
          typeof f.properties?.name === "string" ? f.properties.name : "";
        const safeName = name || "未知区域";
        countries.push({ name: safeName, zh: countryZh(safeName), path });
      }
      this.countryPaths = countries;

      const provMeta: { name: string; path: Path2D }[] = [];
      for (const f of china.features ?? []) {
        const path = featurePath(f);
        const props = (f as GeoFeatureLike).properties ?? null;
        const pname =
          props && typeof props.name === "string" ? props.name : null;
        if (path) provMeta.push({ name: pname ?? "未知省份", path });
      }
      this.provinceMeta = provMeta;

      // 经纬网格
      const grid = new Path2D();
      for (let lng = -180; lng <= 180; lng += 15) {
        grid.moveTo(projectX(lng), 0);
        grid.lineTo(projectX(lng), BASE_H);
      }
      for (let lat = -75; lat <= 75; lat += 15) {
        grid.moveTo(0, projectY(lat));
        grid.lineTo(BASE_W, projectY(lat));
      }
      this.graticulePath = grid;

      this.geoReady = true;
    } catch {
      this.geoReady = false; // 保持深空背景，不崩溃
    }
  }

  // ------------------------------------------------------------- 输入

  private onPointerMove = (e: PointerEvent) => {
    const rect = this.canvas.getBoundingClientRect();
    this.mouseX = e.clientX - rect.left;
    this.mouseY = e.clientY - rect.top;
    this.mouseInside = true;
  };

  private onPointerLeave = () => {
    this.mouseInside = false;
    if (this.hoverTarget) {
      this.hoverTarget = null;
      this.cbs.onHover(null);
    }
  };

  private onClick = () => {
    this.cbs.onClick(this.hoverTarget);
  };

  private bindEvents() {
    this.canvas.addEventListener("pointermove", this.onPointerMove);
    this.canvas.addEventListener("pointerleave", this.onPointerLeave);
    this.canvas.addEventListener("click", this.onClick);
  }

  private unbindEvents() {
    this.canvas.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("pointerleave", this.onPointerLeave);
    this.canvas.removeEventListener("click", this.onClick);
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.width = Math.max(320, Math.round(rect.width));
    this.height = Math.max(240, Math.round(rect.height));
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);

    // 星空
    const count = Math.round((this.width * this.height) / 16000);
    this.stars = Array.from({ length: count }, () => ({
      x: rand(0, this.width),
      y: rand(0, this.height),
      r: rand(0.4, 1.4),
      ph: rand(0, Math.PI * 2),
    }));
  }

  // ------------------------------------------------------------- 聚合

  private recomputeAggs(nowSec: number) {
    const store = useNetworkStore.getState();

    for (const flow of store.flows) {
      const age = nowSec - flow.timestamp;
      if (age > FLOW_TTL) continue;
      if (flow.source.lat == null || flow.source.lng == null) continue;
      if (flow.destination.lat == null || flow.destination.lng == null) continue;
      if (flow.source.lat === flow.destination.lat && flow.source.lng === flow.destination.lng)
        continue;

      const key = `${quantize(flow.source.lat)},${quantize(flow.source.lng)}>${quantize(
        flow.destination.lat
      )},${quantize(flow.destination.lng)}:${flow.direction}`;

      let agg = this.aggs.get(key);
      if (!agg) {
        agg = {
          key,
          direction: flow.direction,
          from: { lat: flow.source.lat, lng: flow.source.lng },
          to: { lat: flow.destination.lat, lng: flow.destination.lng },
          packets: 0,
          bytes: 0,
          lastTimestamp: flow.timestamp,
          sample: flow,
          geomCache: new Map(),
          particles: [],
          spawnAcc: 0,
          effectDone: new Set(),
        };
        this.aggs.set(key, agg);
      }
      agg.packets += 1;
      agg.bytes = Math.max(agg.bytes, flow.bytes.total);
      agg.lastTimestamp = Math.max(agg.lastTimestamp, flow.timestamp);
      agg.sample = flow.bytes.total >= agg.sample.bytes.total ? flow : agg.sample;
    }

    // 淘汰过期聚合
    for (const [key, agg] of this.aggs) {
      const terminal = agg.sample.flag === "failed" || agg.sample.flag === "lost" || agg.sample.status === "关闭连接";
      const ttl = terminal ? TERMINAL_TTL : FLOW_TTL;
      if (nowSec - agg.lastTimestamp > ttl) this.aggs.delete(key);
    }
  }

  /** 强度归一化：log 尺度，禁止原始 bytes 直接参与渲染参数 */
  private intensityOf(agg: ActiveAgg): number {
    let maxBytes = 1;
    for (const a of this.aggs.values()) {
      if (a.bytes > maxBytes) maxBytes = a.bytes;
    }
    return clamp01(Math.log1p(agg.bytes) / Math.log1p(maxBytes));
  }

  // ------------------------------------------------------------- 主循环

  private loop() {
    if (this.disposed) return;
    const now = performance.now();
    const nowSec = Date.now() / 1000;
    const store = useNetworkStore.getState();

    // 视图动画
    if (this.animator && !this.animator.done) {
      this.view = this.animator.sample(now);
      this.mapperEpoch += 1;
    } else if (this.animator) {
      this.animator = null;
    }
    if (
      this.scene === "lan" &&
      !this.animator &&
      Math.abs(this.view.cx - projectX(store.gateway.lng)) > 0.01
    ) {
      this.view.cx = projectX(store.gateway.lng);
      this.view.cy = projectY(store.gateway.lat);
      this.mapperEpoch += 1;
    }

    // 定期重算聚合
    if (now - this.lastAggAt > AGG_REFRESH_MS) {
      this.lastAggAt = now;
      this.recomputeAggs(nowSec + store.serverOffset);
    }

    this.draw(now, nowSec + store.serverOffset);
    this.updateHover();
    this.raf = requestAnimationFrame(this.loop);
  }

  // ------------------------------------------------------------- 绘制

  private draw(now: number, nowSec: number) {
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;
    const store = useNetworkStore.getState();

    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

    // 深空背景
    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, "#020611");
    bg.addColorStop(0.55, "#050B14");
    bg.addColorStop(1, "#08111F");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // 星空
    for (const s of this.stars) {
      const tw = this.reducedMotion ? 0.5 : 0.25 + 0.35 * Math.sin(now / 900 + s.ph);
      ctx.fillStyle = `rgba(190,220,255,${tw.toFixed(3)})`;
      ctx.fillRect(s.x, s.y, s.r, s.r);
    }

    const mapper = createMapper(this.view, w, h);
    const geoAlpha = this.geoFadeAlpha();
    const selectedId = store.selectedId;

    // ---- 地理图层（东西方向环绕复制，消除左右死边）
    if (this.geoReady && geoAlpha > 0.01) {
      ctx.save();
      const k = (w / BASE_W) * this.view.scale;
      const px = 1 / k; // 1 屏幕像素的世界尺寸
      const span = BASE_W * k;
      const offsets =
        span < w * 2 ? [-span, 0, span] : [0]; // 高倍缩放时无需复制

      for (const off of offsets) {
        ctx.setTransform(
          this.dpr * k,
          0,
          0,
          this.dpr * k,
          this.dpr * (w / 2 - this.view.cx * k + off),
          this.dpr * (h / 2 - this.view.cy * k)
        );

        // 网格
        if (this.graticulePath) {
          ctx.strokeStyle = `rgba(120,150,200,${(0.05 * geoAlpha).toFixed(3)})`;
          ctx.lineWidth = px;
          ctx.stroke(this.graticulePath);
        }

        // 陆地：微弱内发光 + 极细亮边
        for (const c of this.countryPaths) {
          ctx.fillStyle = `rgba(10,22,40,${(0.85 * geoAlpha).toFixed(3)})`;
          ctx.fill(c.path);
        }
        ctx.strokeStyle = `rgba(0,229,255,${(0.05 * geoAlpha).toFixed(3)})`;
        ctx.lineWidth = 3 * px;
        for (const c of this.countryPaths) ctx.stroke(c.path); // 外发光层
        ctx.strokeStyle = `rgba(64,180,220,${(0.38 * geoAlpha).toFixed(3)})`;
        ctx.lineWidth = px;
        for (const c of this.countryPaths) ctx.stroke(c.path); // 亮边层

        // Hover 高亮（国家 / 省份）
        if (this.hoverTarget?.kind === "country") {
          const hovered = this.countryPaths.find(
            (c) => c.zh === this.hoverTarget?.title
          );
          if (hovered) {
            ctx.fillStyle = `rgba(0,229,255,${(0.09 * geoAlpha).toFixed(3)})`;
            ctx.fill(hovered.path);
            ctx.strokeStyle = `rgba(0,229,255,${(0.8 * geoAlpha).toFixed(3)})`;
            ctx.lineWidth = px;
            ctx.stroke(hovered.path);
          }
        } else if (this.hoverTarget?.kind === "province") {
          const hovered = this.provinceMeta.find(
            (p) => p.name === this.hoverTarget?.title
          );
          if (hovered) {
            ctx.fillStyle = `rgba(94,200,242,${(0.12 * geoAlpha).toFixed(3)})`;
            ctx.fill(hovered.path);
            ctx.strokeStyle = `rgba(94,200,242,${(0.85 * geoAlpha).toFixed(3)})`;
            ctx.lineWidth = px;
            ctx.stroke(hovered.path);
          }
        }

        // 省界（放大后淡入）
        const provAlpha = clamp01((this.view.scale - 1.7) / 1.6) * geoAlpha;
        if (provAlpha > 0.02) {
          ctx.strokeStyle = `rgba(0,200,255,${(0.16 * provAlpha).toFixed(3)})`;
          ctx.lineWidth = px;
          for (const p of this.provinceMeta) ctx.stroke(p.path);
        }
      }
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    // ---- 数据流
    const visibleAggs: { agg: ActiveAgg; a: ArcGeometry; i: number }[] = [];
    for (const agg of this.aggs.values()) {
      if (!this.flowVisible(agg)) continue;
      const s = mapper.toScreen(agg.from.lng, agg.from.lat);
      const e = mapper.toScreen(agg.to.lng, agg.to.lat);
      const axp = this.nearCenterX(s.x);
      const bxp = this.nearCenterX(e.x);
      // 跨越日界线时取最短路径表示
      let dx = bxp - axp;
      if (dx > w / 2) dx -= this.wrapSpan();
      else if (dx < -w / 2) dx += this.wrapSpan();
      const bxFinal = axp + dx;

      if (
        (axp < -80 && bxFinal < -80) ||
        (axp > w + 80 && bxFinal > w + 80) ||
        (s.y < -80 && e.y < -80) ||
        (s.y > h + 80 && e.y > h + 80)
      ) {
        continue;
      }
      let geom = agg.geomCache.get(this.mapperEpoch);
      if (!geom) {
        geom = buildArc(axp, s.y, bxFinal, e.y, 0.22);
        agg.geomCache.clear();
        agg.geomCache.set(this.mapperEpoch, geom);
      }
      visibleAggs.push({ agg, a: geom, i: this.intensityOf(agg) });
    }

    // 按强度排序，弱的先画
    visibleAggs.sort((p, q) => p.i - q.i);

    for (const { agg, a, i } of visibleAggs) {
      const color = directionColor(agg.direction);
      const isSel = selectedId != null && agg.packets > 0 && agg.sample.id === selectedId;
      this.drawArc(ctx, agg, a, color, i, isSel);

      // 终态特效（失败=红 / 丢失=琥珀）
      const flag = agg.sample.flag;
      if ((flag === "failed" || flag === "lost") && !agg.effectDone.has(agg.sample.id)) {
        agg.effectDone.add(agg.sample.id);
        this.effects.push({
          x: a.bx,
          y: a.by,
          born: now,
          color: flag === "failed" ? cyber.red : cyber.amber,
        });
      }

      this.stepParticles(ctx, agg, a, color, i, now);
    }
    this.prevFrame = now;

    // 特效环（失败 / 丢失）
    this.effects = this.effects.filter((e) => now - e.born < 1400);
    for (const e of this.effects) {
      const t = (now - e.born) / 1400;
      ctx.beginPath();
      ctx.arc(e.x, e.y, 4 + t * 26, 0, Math.PI * 2);
      ctx.strokeStyle = e.color;
      ctx.globalAlpha = (1 - t) * 0.7;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // ---- 公网节点
    this.drawPublicNodes(ctx, mapper, now, nowSec);

    // ---- 内网设备（LAN）
    const deviceAlpha = clamp01((this.view.scale - 6.5) / 3);
    if (deviceAlpha > 0.02) {
      this.drawDevices(ctx, mapper, now, deviceAlpha);
    }

    // ---- 网关核心
    this.drawCore(ctx, mapper, now);

    // ---- 扫描线（克制）
    if (!this.reducedMotion) {
      const sweepT = ((now - this.bootedAt) % 7000) / 7000;
      const sx = sweepT * (w + 300) - 150;
      const grad = ctx.createLinearGradient(sx - 90, 0, sx + 90, 0);
      grad.addColorStop(0, "rgba(0,229,255,0)");
      grad.addColorStop(0.5, "rgba(0,229,255,0.045)");
      grad.addColorStop(1, "rgba(0,229,255,0)");
      ctx.fillStyle = grad;
      ctx.fillRect(sx - 90, 0, 180, h);
    }

    // ---- 场景角标
    this.drawSceneHud(ctx, store.flows.length);
  }

  private prevFrame: number | null = null;

  /** 当前缩放下世界东西方向的屏幕跨度 */
  private wrapSpan(): number {
    return BASE_W * ((this.width / BASE_W) * this.view.scale);
  }

  private isWrapping(): boolean {
    return this.wrapSpan() < this.width * 2;
  }

  /** 把屏幕 x 归位到「离屏幕中心最近的环绕表示」（全球视图消除左右死边） */
  private nearCenterX(x: number): number {
    if (!this.isWrapping()) return x;
    const c = this.width / 2;
    const span = this.wrapSpan();
    let d = x - c;
    d = ((d % span) + span * 1.5) % span - span / 2; // [-span/2, span/2)
    return c + d;
  }

  private geoFadeAlpha(): number {
    if (this.view.scale <= LAN_GEO_FADE_START) return 1;
    if (this.view.scale >= LAN_GEO_FADE_END) return 0;
    return 1 - (this.view.scale - LAN_GEO_FADE_START) / (LAN_GEO_FADE_END - LAN_GEO_FADE_START);
  }

  private flowVisible(agg: ActiveAgg): boolean {
    const s = this.view.scale;
    if (agg.direction === "internal") return s >= 5.2;
    // 公网流在接近 LAN 时淡出
    return s < LAN_GEO_FADE_END + 0.5;
  }

  // ------------------------------------------------------------ 弧线与粒子

  private drawArc(
    ctx: CanvasRenderingContext2D,
    agg: ActiveAgg,
    a: ArcGeometry,
    color: string,
    intensity: number,
    selected: boolean
  ) {
    const width = 0.8 + intensity * 2.4;

    // 光晕层
    ctx.beginPath();
    ctx.moveTo(a.ax, a.ay);
    ctx.quadraticCurveTo(a.cx, a.cy, a.bx, a.by);
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.05 + intensity * 0.08;
    ctx.lineWidth = width * 4;
    ctx.stroke();

    // 主体渐变线
    const grad = ctx.createLinearGradient(a.ax, a.ay, a.bx, a.by);
    grad.addColorStop(0, "rgba(0,0,0,0)");
    grad.addColorStop(0.18, color);
    grad.addColorStop(0.82, color);
    grad.addColorStop(1, "rgba(0,0,0,0)");
    ctx.beginPath();
    ctx.moveTo(a.ax, a.ay);
    ctx.quadraticCurveTo(a.cx, a.cy, a.bx, a.by);
    ctx.strokeStyle = grad;
    ctx.globalAlpha = selected ? 0.95 : 0.34 + intensity * 0.3;
    ctx.lineWidth = width;
    ctx.stroke();

    // 流动虚线（方向感）
    if (!this.reducedMotion) {
      ctx.save();
      ctx.setLineDash([3, 14]);
      ctx.lineDashOffset = -(performance.now() / 28) % 17;
      ctx.beginPath();
      ctx.moveTo(a.ax, a.ay);
      ctx.quadraticCurveTo(a.cx, a.cy, a.bx, a.by);
      ctx.strokeStyle = "#ffffff";
      ctx.globalAlpha = selected ? 0.5 : 0.12 + intensity * 0.12;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();
    }

    // 目的地箭头
    const ang = Math.atan2(a.by - a.cy, a.bx - a.cx);
    ctx.save();
    ctx.translate(a.bx, a.by);
    ctx.rotate(ang);
    ctx.beginPath();
    ctx.moveTo(2, 0);
    ctx.lineTo(-5, -3.6);
    ctx.lineTo(-5, 3.6);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.9;
    ctx.fill();
    ctx.restore();

    ctx.globalAlpha = 1;
  }

  private stepParticles(
    ctx: CanvasRenderingContext2D,
    agg: ActiveAgg,
    a: ArcGeometry,
    color: string,
    intensity: number,
    now: number
  ) {
    if (this.reducedMotion || a.length < 40) return;
    const dtSec = this.prevFrame ? Math.min(0.06, (now - this.prevFrame) / 1000) : 0.016;

    const target = Math.min(10, 2 + Math.round(intensity * 8));
    agg.spawnAcc += dtSec * target * 0.45;
    while (agg.spawnAcc >= 1 && agg.particles.length < target) {
      agg.spawnAcc -= 1;
      if (agg.particles.length < target) {
        agg.particles.push({
          t: 0,
          speed: 0.32 + intensity * 0.5 + rand(0, 0.12),
          delay: rand(0, 0.6),
        });
      }
    }
    if (agg.spawnAcc > 2) agg.spawnAcc = 0;

    for (let idx = agg.particles.length - 1; idx >= 0; idx--) {
      const p = agg.particles[idx];
      if (!p) continue;
      if (p.delay > 0) {
        p.delay -= dtSec;
        continue;
      }
      p.t += p.speed * dtSec;
      if (p.t > 1) {
        agg.particles.splice(idx, 1);
        continue;
      }
      const u = 1 - p.t;
      const x = u * u * a.ax + 2 * u * p.t * a.cx + p.t * p.t * a.bx;
      const y = u * u * a.ay + 2 * u * p.t * a.cy + p.t * p.t * a.by;

      // 拖尾
      const tt = Math.max(0, p.t - 0.045);
      const uu = 1 - tt;
      const tx = uu * uu * a.ax + 2 * uu * tt * a.cx + tt * tt * a.bx;
      const ty = uu * uu * a.ay + 2 * uu * tt * a.cy + tt * tt * a.by;

      const fade = Math.sin(p.t * Math.PI);
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(x, y);
      ctx.strokeStyle = color;
      ctx.globalAlpha = 0.5 * fade;
      ctx.lineWidth = 1.4;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x, y, 1.6, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.globalAlpha = 0.85 * fade;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    if (this.aggs.size * 8 > MAX_PARTICLES) {
      // 全局粒子上限保护：随机修剪
      for (const other of this.aggs.values()) {
        if (other.particles.length > 4) other.particles.length = 4;
      }
    }
  }

  // ------------------------------------------------------------ 节点

  private drawPublicNodes(
    ctx: CanvasRenderingContext2D,
    mapper: ScreenMapper,
    now: number,
    nowSec: number
  ) {
    const nodes = useNetworkStore.getState().nodes;
    const w = this.width;
    const h = this.height;

    for (const node of nodes) {
      // LAN 缩放下公网节点随地理层一起淡出
      const nodeAlpha = this.geoFadeAlpha();
      if (nodeAlpha < 0.05) continue;
      const raw = mapper.toScreen(node.lng, node.lat);
      const p = { x: this.nearCenterX(raw.x), y: raw.y };
      if (p.x < -30 || p.x > this.width + 30 || p.y < -30 || p.y > h + 30) continue;

      // 新节点脉冲（真实节点出现 → Pulse，AGENTS.md §48）
      // 注意：nowSec 含 serverOffset，而 offset 会随轮询重新校准而回跳，
      // 因此必须钳制时间差，否则 pulse > 1 会导致 arc 半径为负（IndexSizeError）
      const announced = this.announcedNodes.get(node.ip);
      if (announced == null || nowSec - announced > 30 || nowSec < announced) {
        this.announcedNodes.set(node.ip, nowSec);
      }
      let pulse = 0;
      if (announced != null && nowSec >= announced) {
        const since = Math.min(nowSec - announced, 1.6);
        if (since < 1.6) pulse = 1 - since / 1.6;
      }

      const isServer = node.type === "server";
      const baseR = isServer ? 2.6 : 1.9;
      const alpha = isServer ? 0.9 : 0.65;

      if (pulse > 0) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, baseR + (1 - pulse) * 14, 0, Math.PI * 2);
        ctx.strokeStyle = cyber.mint;
        ctx.globalAlpha = pulse * 0.6;
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      if (isServer) {
        // 服务端：菱形轮廓
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(Math.PI / 4);
        ctx.strokeStyle = cyber.blue;
        ctx.globalAlpha = alpha;
        ctx.lineWidth = 1.1;
        ctx.strokeRect(-baseR, -baseR, baseR * 2, baseR * 2);
        ctx.fillStyle = cyber.cyan;
        ctx.fillRect(-1.2, -1.2, 2.4, 2.4);
        ctx.restore();
      } else {
        ctx.beginPath();
        ctx.arc(p.x, p.y, baseR, 0, Math.PI * 2);
        ctx.fillStyle = cyber.violet;
        ctx.globalAlpha = alpha;
        ctx.fill();
        if (pulse > 0) {
          ctx.beginPath();
          ctx.arc(p.x, p.y, baseR, 0, Math.PI * 2);
          ctx.strokeStyle = cyber.violet;
          ctx.globalAlpha = pulse * 0.8;
          ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
    }
  }

  private drawDevices(
    ctx: CanvasRenderingContext2D,
    mapper: ScreenMapper,
    now: number,
    alpha: number
  ) {
    const devices = useNetworkStore.getState().devices;
    const showLabel = this.view.scale >= LAN_LABEL_SCALE;
    for (const d of devices) {
      if (d.isGateway || d.lat == null || d.lng == null) continue;
      const raw = mapper.toScreen(d.lng, d.lat);
      const p = { x: this.nearCenterX(raw.x), y: raw.y };
      const active = d.connections > 0;
      const r = active ? 4.2 : 3.2;
      const color = active ? cyber.green : "#3A4A63";

      // 底座光晕
      const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 3.4);
      glow.addColorStop(0, `${color}44`);
      glow.addColorStop(1, `${color}00`);
      ctx.fillStyle = glow;
      ctx.globalAlpha = alpha;
      ctx.fillRect(p.x - r * 3.4, p.y - r * 3.4, r * 6.8, r * 6.8);

      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.globalAlpha = alpha;
      ctx.fill();
      ctx.strokeStyle = "#0B142420";
      ctx.lineWidth = 1;
      ctx.stroke();

      if (active && !this.reducedMotion) {
        const t = (now % 2600) / 2600;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r + t * 10, 0, Math.PI * 2);
        ctx.strokeStyle = cyber.green;
        ctx.globalAlpha = alpha * (1 - t) * 0.5;
        ctx.stroke();
      }

      if (showLabel) {
        // 上下交错排布标签，减少环形布局下的文字重叠
        const parity =
          d.ringIndex ??
          d.ip.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
        const above = parity % 2 === 1;
        const baseY = above ? p.y - r - 35 : p.y + r + 13;
        const step = above ? -11 : 11;

        ctx.globalAlpha = alpha * 0.92;
        ctx.font = "10px 'JetBrains Mono', ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillStyle = cyber.textSecondary;
        const label = d.hostname || d.ip;
        ctx.fillText(label, p.x, baseY);
        if (d.hostname) {
          ctx.fillStyle = cyber.textDim;
          ctx.fillText(d.ip, p.x, baseY + step);
        }
        if (active) {
          ctx.fillStyle = `${cyber.green}CC`;
          ctx.fillText(`${d.connections} 连接`, p.x, baseY + step * 2);
        }
      }
    }
    ctx.globalAlpha = 1;
  }

  private drawCore(
    ctx: CanvasRenderingContext2D,
    mapper: ScreenMapper,
    now: number
  ) {
    const storeState = useNetworkStore.getState();
    const g = storeState.gateway;
    const raw = mapper.toScreen(g.lng, g.lat);
    const p = { x: this.nearCenterX(raw.x), y: raw.y };
    const w = this.width;
    const h = this.height;
    if (p.x < -60 || p.x > w + 60 || p.y < -60 || p.y > h + 60) return;

    const zoomShrink = clamp01((this.view.scale - 4) / 8); // LAN 时核心缩小为路由器节点
    const R = 9.5 - zoomShrink * 4.5;
    // 真实数据源：iKuai 连接出错时核心显示异常态（⚠ 异常 / 琥珀色）
    const online = !storeState.ikuaiError;

    // 底部辉光
    const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, R * 4.5);
    glow.addColorStop(0, "rgba(0,229,255,0.35)");
    glow.addColorStop(0.5, "rgba(0,229,255,0.08)");
    glow.addColorStop(1, "rgba(0,229,255,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(p.x - R * 4.5, p.y - R * 4.5, R * 9, R * 9);

    // Pulse 扩散环
    if (!this.reducedMotion) {
      const pt = ((now - this.bootedAt) % 2800) / 2800;
      for (const off of [0, 0.5]) {
        const t = (pt + off) % 1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, R + t * R * 3.2, 0, Math.PI * 2);
        ctx.strokeStyle = cyber.cyan;
        ctx.globalAlpha = (1 - t) * 0.35;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }

    // 旋转环（两段反向弧）
    if (!this.reducedMotion) {
      const rot = (now - this.bootedAt) / 1000;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(rot * 0.9);
      ctx.beginPath();
      ctx.arc(0, 0, R + R * 0.35, 0, Math.PI * 0.66);
      ctx.strokeStyle = cyber.cyan;
      ctx.globalAlpha = 0.85;
      ctx.lineWidth = 1.4;
      ctx.stroke();
      ctx.rotate(-rot * 2.1);
      ctx.beginPath();
      ctx.arc(0, 0, R + R * 0.6, Math.PI, Math.PI * 1.52);
      ctx.strokeStyle = cyber.mint;
      ctx.globalAlpha = 0.5;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();
    }

    // 内核
    ctx.beginPath();
    ctx.arc(p.x, p.y, R, 0, Math.PI * 2);
    ctx.fillStyle = "#04121F";
    ctx.globalAlpha = 1;
    ctx.fill();
    ctx.strokeStyle = online ? cyber.cyan : cyber.amber;
    ctx.globalAlpha = 0.95;
    ctx.lineWidth = 1.6;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(p.x, p.y, R * 0.42, 0, Math.PI * 2);
    ctx.fillStyle = online ? cyber.mint : cyber.amber;
    ctx.shadowColor = online ? cyber.cyan : cyber.amber;
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.shadowBlur = 0;

    // 标签
    const isLanZoom = this.view.scale >= 6;
    ctx.font = "10px 'JetBrains Mono', ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.fillStyle = cyber.textSecondary;
    if (isLanZoom) {
      ctx.fillText("iKuai 主路由 · 网关", p.x, p.y - R - 12);
    } else {
      ctx.fillText("核心服务器 · NETWORK CORE", p.x, p.y - R - 10);
      ctx.fillStyle = online ? `${cyber.mint}DD` : `${cyber.amber}DD`;
      ctx.fillText(online ? "● 在线" : "⚠ 异常", p.x, p.y + R + 16);
    }
    ctx.globalAlpha = 1;
  }

  private drawSceneHud(ctx: CanvasRenderingContext2D, flowCount: number) {
    const pad = 14;
    ctx.font = "10px 'JetBrains Mono', ui-monospace, monospace";
    ctx.textAlign = "left";

    // 左下：坐标信息
    ctx.fillStyle = cyber.textDim;
    const label =
      this.scene === "global"
        ? "等距圆柱投影 · WGS84"
        : this.scene === "china"
          ? "中国区域 · 省界网格"
          : "内网拓扑 · RFC1918";
    ctx.fillText(label, pad, this.height - pad);

    // 右下：活动流计数
    ctx.textAlign = "right";
    ctx.fillStyle = flowCount > 0 ? `${cyber.cyan}99` : cyber.textDim;
    ctx.fillText(
      flowCount > 0 ? `活跃链路 ${formatCount(flowCount)}` : "暂无活动数据流",
      this.width - pad,
      this.height - pad
    );
  }

  // ------------------------------------------------------------ Hover 拾取

  private updateHover() {
    if (!this.mouseInside) return;
    const mx = this.mouseX;
    const my = this.mouseY;
    const mapper = createMapper(this.view, this.width, this.height);
    const store = useNetworkStore.getState();
    let found: HoverPayload | null = null;

    // 1) 设备（LAN 放大态优先）
    if (this.view.scale >= 6) {
      for (const d of store.devices) {
        if (d.isGateway || d.lat == null || d.lng == null) continue;
        const raw = mapper.toScreen(d.lng, d.lat);
        const p = { x: this.nearCenterX(raw.x), y: raw.y };
        if (Math.hypot(p.x - mx, p.y - my) < 12) {
          found = {
            kind: "device",
            x: p.x,
            y: p.y,
            title: d.hostname || d.ip,
            subtitle: d.ip,
            accent: d.connections > 0 ? cyber.green : cyber.textSecondary,
            rows: [
              ["并发连接", formatCount(d.connections)],
              ["上行速率", formatRate(d.upRate)],
              ["下行速率", formatRate(d.downRate)],
            ],
          };
          break;
        }
      }
    }

    // 2) 公网节点
    if (!found) {
      for (const n of store.nodes) {
        const raw = mapper.toScreen(n.lng, n.lat);
        const p = { x: this.nearCenterX(raw.x), y: raw.y };
        if (Math.hypot(p.x - mx, p.y - my) < 10) {
          found = {
            kind: "node",
            x: p.x,
            y: p.y,
            title: n.name,
            subtitle: n.domain ?? n.ip,
            accent:
              n.type === "gateway"
                ? cyber.mint
                : n.type === "server"
                  ? cyber.cyan
                  : cyber.violet,
            rows: [["IP 地址", n.ip]],
          };
          break;
        }
      }
    }

    // 3) 数据流（采样距离）
    if (!found) {
      let bestDist = 9;
      let bestAgg: ActiveAgg | null = null;
      let bestGeom: ArcGeometry | null = null;
      for (const agg of this.aggs.values()) {
        if (!this.flowVisible(agg)) continue;
        const s = mapper.toScreen(agg.from.lng, agg.from.lat);
        const e = mapper.toScreen(agg.to.lng, agg.to.lat);
        const axp = this.nearCenterX(s.x);
        let dx = this.nearCenterX(e.x) - axp;
        if (dx > this.width / 2) dx -= this.wrapSpan();
        else if (dx < -this.width / 2) dx += this.wrapSpan();
        const bxp = axp + dx;
        if (
          (axp < -80 && bxp < -80) ||
          (axp > this.width + 80 && bxp > this.width + 80)
        )
          continue;
        let geom = agg.geomCache.get(this.mapperEpoch);
        if (!geom) {
          geom = buildArc(axp, s.y, bxp, e.y, 0.22);
          agg.geomCache.clear();
          agg.geomCache.set(this.mapperEpoch, geom);
        }
        for (let step = 1; step < 23; step++) {
          const t = step / 23;
          const u = 1 - t;
          const x = u * u * geom.ax + 2 * u * t * geom.cx + t * t * geom.bx;
          const y = u * u * geom.ay + 2 * u * t * geom.cy + t * t * geom.by;
          const dist = Math.hypot(x - mx, y - my);
          if (dist < bestDist) {
            bestDist = dist;
            bestAgg = agg;
            bestGeom = geom;
          }
        }
      }
      if (bestAgg && bestGeom) {
        const hx =
          (bestGeom.ax + bestGeom.bx) / 2 + (bestGeom.cx - (bestGeom.ax + bestGeom.bx) / 2) / 2;
        const hy =
          (bestGeom.ay + bestGeom.by) / 2 + (bestGeom.cy - (bestGeom.ay + bestGeom.by) / 2) / 2;
        const sample = bestAgg.sample;
        found = {
          kind: "flow",
          x: hx,
          y: hy,
          title: `${sample.application}`,
          subtitle:
            sample.direction === "outbound"
              ? "出站 · OUTBOUND"
              : sample.direction === "inbound"
                ? "入站 · INBOUND"
                : "内网 · INTERNAL",
          accent: directionColor(sample.direction),
          flowId: sample.id,
          rows: [
            ["源地址", `${sample.source.ip}:${sample.source.port}`],
            ["目标地址", `${sample.destination.ip}:${sample.destination.port}`],
            ["协议", sample.protocol.toUpperCase()],
            ["累计流量", formatBytes(bestAgg.bytes)],
            ["事件数", formatCount(bestAgg.packets)],
          ],
        };
      }
    }

    // 4) 省份 / 国家（含东西环绕副本拾取；悬停显示中文信息窗）
    if (!found && this.geoReady && this.view.scale < 6 && this.ctx) {
      const k = (this.width / BASE_W) * this.view.scale;
      const span = BASE_W * k;
      const offsets = span < this.width * 2 ? [-span, 0, span] : [0];
      const dx = mx * this.dpr;
      const dy = my * this.dpr;

      /** 统计端点落在指定多边形内的活动流（跨环绕副本合并） */
      const regionStats = (
        path: Path2D,
        off: number
      ): { hits: number; bytes: number } => {
        let hits = 0;
        let bytes = 0;
        for (const agg of this.aggs.values()) {
          for (const ep of [agg.from, agg.to]) {
            let hitEp = false;
            for (const eoff of offsets) {
              const sp = mapper.toScreen(ep.lng, ep.lat);
              if (
                this.ctx?.isPointInPath(path, (sp.x - off) * this.dpr, sp.y * this.dpr)
              ) {
                hitEp = true;
                break;
              }
            }
            if (hitEp) {
              hits += 1;
              bytes += agg.bytes;
              break;
            }
          }
        }
        return { hits, bytes };
      };

      const pickRegion = (
        entries: { title: string; subtitle: string; path: Path2D }[],
        kind: "country" | "province"
      ): boolean => {
        for (const off of offsets) {
          this.ctx.setTransform(
            this.dpr * k,
            0,
            0,
            this.dpr * k,
            this.dpr * (this.width / 2 - this.view.cx * k + off),
            this.dpr * (this.height / 2 - this.view.cy * k)
          );
          for (const entry of entries) {
            try {
              if (!this.ctx.isPointInPath(entry.path, dx, dy)) continue;
              const { hits, bytes } = regionStats(entry.path, off);
              found = {
                kind,
                x: mx,
                y: my,
                title: entry.title,
                subtitle: entry.subtitle,
                accent: kind === "province" ? "#5EC8F2" : cyber.cyan,
                rows: [
                  ["活跃链路", formatCount(hits)],
                  ["累计流量", formatBytes(bytes)],
                  ["状态", hits > 0 ? "已连接" : "监控中"],
                ],
              };
              return true;
            } catch {
              // 拾取失败不影响渲染
            }
          }
        }
        return false;
      };

      // 中国区域视图：省级行政区优先于国家
      const provinceFirst =
        this.view.scale >= 2.2 && this.provinceMeta.length > 0;
      if (provinceFirst) {
        pickRegion(
          this.provinceMeta.map((p) => ({
            title: p.name,
            subtitle: "省级行政区 · PROVINCE",
            path: p.path,
          })),
          "province"
        );
      }
      if (!found) {
        pickRegion(
          this.countryPaths.map((c) => ({
            title: c.zh,
            subtitle: "国家 · COUNTRY",
            path: c.path,
          })),
          "country"
        );
      }
      this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    // 与上一帧对比去抖：内容变化或移动超过阈值才通知 React
    const prev = this.hoverTarget;
    let shouldEmit = false;
    if (!found) {
      shouldEmit = prev != null;
    } else if (
      !prev ||
      prev.kind !== found.kind ||
      prev.title !== found.title ||
      Math.abs(found.x - prev.x) + Math.abs(found.y - prev.y) > 3
    ) {
      shouldEmit = true;
    }
    this.hoverTarget = found;
    if (shouldEmit) this.cbs.onHover(found);

    this.canvas.style.cursor = found ? "pointer" : "crosshair";
  }
}

// ---------------------------------------------------------------- GeoJSON

function ringPath(ring: unknown, path: Path2D): boolean {
  if (!Array.isArray(ring) || ring.length < 2) return false;
  let started = false;
  let lastX = NaN;
  let lastY = NaN;
  for (const coord of ring as unknown[]) {
    if (!Array.isArray(coord)) continue;
    const lng = coord[0];
    const lat = coord[1];
    if (typeof lng !== "number" || typeof lat !== "number") continue;
    const x = projectX(lng);
    const y = projectY(lat);
    if (!started) {
      path.moveTo(x, y);
      started = true;
    } else if (x !== lastX || y !== lastY) {
      path.lineTo(x, y);
    }
    lastX = x;
    lastY = y;
  }
  return started;
}

function polygonPath(poly: unknown, path: Path2D): boolean {
  if (!Array.isArray(poly)) return false;
  let ok = false;
  for (const ring of poly) {
    if (ringPath(ring, path)) ok = true;
  }
  return ok;
}

interface GeoFeatureLike {
  type?: string;
  geometry?: {
    type?: string;
    coordinates?: unknown;
  } | null;
  properties?: Record<string, unknown> | null;
}

function featurePath(f: unknown): Path2D | null {
  const feat = f as GeoFeatureLike;
  const geomType = feat.geometry?.type;
  const coords = feat.geometry?.coordinates;
  if (!geomType || !coords) return null;
  const path = new Path2D();
  let ok = false;
  if (geomType === "Polygon") {
    ok = polygonPath(coords, path);
  } else if (geomType === "MultiPolygon") {
    if (Array.isArray(coords)) {
      for (const poly of coords) {
        if (polygonPath(poly, path)) ok = true;
      }
    }
  } else if (geomType === "LineString") {
    ok = ringPath(coords, path);
  } else if (geomType === "MultiLineString") {
    if (Array.isArray(coords)) {
      for (const line of coords) {
        if (ringPath(line, path)) ok = true;
      }
    }
  }
  return ok ? path : null;
}
