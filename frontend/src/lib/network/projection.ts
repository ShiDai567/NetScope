/**
 * 等距圆柱投影（equirectangular）+ 相机视图数学。
 * 世界坐标：lng [-180,180] → x [0,BASE_W]，lat [90,-90] → y [0,BASE_H]
 * 所有地理 Path2D 均以 BASE 尺度预构建，渲染时通过 ctx.transform 缩放平移。
 */

export const BASE_W = 2048;
export const BASE_H = 1024;

export interface LngLat {
  lng: number;
  lat: number;
}

export function projectX(lng: number): number {
  return ((lng + 180) / 360) * BASE_W;
}

export function projectY(lat: number): number {
  return ((90 - lat) / 180) * BASE_H;
}

/** 相机视图：世界坐标中的注视点 + 缩放倍率 */
export interface ViewTransform {
  /** 注视点（base 像素坐标） */
  cx: number;
  cy: number;
  /** 相对 base 的缩放；1 = 全球铺满宽度 */
  scale: number;
}

export interface ScreenMapper {
  toScreen(lng: number, lat: number): { x: number; y: number };
  toWorld(x: number, y: number): { wx: number; wy: number };
  view: ViewTransform;
}

export function createMapper(
  view: ViewTransform,
  width: number,
  height: number
): ScreenMapper {
  // 覆盖策略：scale 定义为「视口宽 = BASE_W / scale」，保持纵横比
  const k = (width / BASE_W) * view.scale;
  const tx = width / 2 - view.cx * k;
  const ty = height / 2 - view.cy * k;
  return {
    view,
    toScreen(lng, lat) {
      return { x: projectX(lng) * k + tx, y: projectY(lat) * k + ty };
    },
    toWorld(x, y) {
      return { wx: (x - tx) / k, wy: (y - ty) / k };
    },
  };
}

/** 当前缩放下 1 屏幕像素对应的世界经度数 */
export function screenLngPerPx(view: ViewTransform, width: number): number {
  return 360 / ((width / BASE_W) * view.scale * BASE_W);
}

const easeInOutStrong = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

/** 视图插值动画（场景切换的平滑 Zoom，AGENTS.md §55） */
export class ViewAnimator {
  private from: ViewTransform;
  private to: ViewTransform;
  private start: number;
  private duration: number;

  constructor(from: ViewTransform, to: ViewTransform, duration = 1100) {
    this.from = from;
    this.to = to;
    this.start = performance.now();
    this.duration = duration;
  }

  get done(): boolean {
    return performance.now() - this.start >= this.duration;
  }

  sample(now: number): ViewTransform {
    const raw = Math.min(1, (now - this.start) / this.duration);
    const t = easeInOutStrong(raw);
    return {
      cx: this.from.cx + (this.to.cx - this.from.cx) * t,
      cy: this.from.cy + (this.to.cy - this.from.cy) * t,
      scale: Math.exp(
        Math.log(this.from.scale) +
          (Math.log(this.to.scale) - Math.log(this.from.scale)) * t
      ),
    };
  }
}

// ---------------------------------------------------------------- 曲线

export interface ArcGeometry {
  ax: number;
  ay: number;
  bx: number;
  by: number;
  cx: number;
  cy: number;
  /** 二次贝塞尔总长的近似值 */
  length: number;
}

/**
 * Great-circle 感的大圆弧：控制点取中垂线方向抬升，
 * 抬升量与两点距离成正比 —— 长航线更高更弯。
 */
export function buildArc(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  lift = 0.28
): ArcGeometry {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.hypot(dx, dy);
  // 垂直方向抬升（取向上为负 y）
  const nx = -dy / (dist || 1);
  const ny = dx / (dist || 1);
  const sign = ny > 0 ? -1 : 1; // 让弧总是向屏幕上方隆起
  const h = dist * lift * sign;
  const cxp = mx + nx * h;
  const cyp = my + ny * h;
  return { ax: x1, ay: y1, bx: x2, by: y2, cx: cxp, cy: cyp, length: dist };
}

/** 二次贝塞尔取点 */
export function arcPoint(a: ArcGeometry, t: number): { x: number; y: number } {
  const u = 1 - t;
  return {
    x: u * u * a.ax + 2 * u * t * a.cx + t * t * a.bx,
    y: u * u * a.ay + 2 * u * t * a.cy + t * t * a.by,
  };
}

/** 弧上切线角（用于粒子朝向） */
export function arcAngle(a: ArcGeometry, t: number): number {
  const u = 1 - t;
  const dx = 2 * u * (a.cx - a.ax) + 2 * t * (a.bx - a.cx);
  const dy = 2 * u * (a.cy - a.ay) + 2 * t * (a.by - a.cy);
  return Math.atan2(dy, dx);
}
