"""带宽序列：EWMA 平滑 + 采样降点（doc §8.2）。"""

import threading
from collections import deque


class BandwidthTracker:
    def __init__(self, alpha: float = 0.4, max_points: int = 3700) -> None:
        self._alpha = alpha
        self._points: deque[list[float]] = deque(maxlen=max_points)
        self._lock = threading.Lock()
        self._smoothed = (0.0, 0.0)

    def push(self, t: float, raw_up: float, raw_down: float) -> tuple[float, float]:
        """写入瞬时速率（B/s），返回平滑值。"""
        with self._lock:
            prev_up, prev_down = self._smoothed
            up = raw_up if prev_up == 0 else prev_up + self._alpha * (raw_up - prev_up)
            down = raw_down if prev_down == 0 else prev_down + self._alpha * (raw_down - prev_down)
            self._smoothed = (up, down)
            self._points.append([t, up, down])
        return up, down

    def latest(self) -> tuple[float, float]:
        with self._lock:
            return self._smoothed

    def series(self, window: int, now: float, max_points: int = 60) -> list[list[float]]:
        """按窗口取样 ≤ max_points 个点 [[t, up, down]]，时间升序。"""
        interval = max(1, window // max(1, max_points))
        with self._lock:
            points = [p for p in self._points if p[0] >= now - window - interval]
        if not points:
            return []
        points.sort(key=lambda p: p[0])
        buckets: dict[int, list[float]] = {}
        for t, up, down in points:
            slot = int(t) // interval * interval
            agg = buckets.setdefault(slot, [0.0, 0.0, 0.0])
            agg[0] += 1
            agg[1] += up
            agg[2] += down
        out = []
        for slot in sorted(buckets):
            count, up_sum, down_sum = buckets[slot]
            out.append([slot, round(up_sum / count, 2), round(down_sum / count, 2)])
        return out[-max_points:]
