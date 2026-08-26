"""hiofd IP 归属地 Provider（Playwright 驱动真实页面查询）。

逆向结论（tool.hiofd.com/ip/）：
  - 接口 POST toola.hiofd.com/router/rest (IpQuery)，归属地中文 + 区县级坐标
  - 请求含混淆 JS 生成的签名（k/t/x/r），服务端有 WAF 风控
    （直连重放/urllib 指纹会被 444 拦截）
  - 因此不直连 API，而是无头浏览器加载页面后驱动其原生查询：
    签名/风控由真实浏览器环境天然满足

成本控制：
  - 浏览器按需启动，空闲 N 分钟自动关闭
  - 每次查询结果写回 SQL GeoLookup 表，同 IP 永不二次查询
  - 查询串行 + 节流，避免页面级频控
"""

import threading
import time

from core.geo.provider import GeoInfo, GeoProvider
from core.log import get_logger

log = get_logger("core.geo.hiofd")

_PAGE_URL = "https://tool.hiofd.com/ip/"
_IDLE_EXIT_SEC = 300.0  # 浏览器空闲 5 分钟退出
_QUERY_INTERVAL = 3.0  # 页面查询节流（真实点击）
_PARSE_TIMEOUT = 12000  # 结果渲染等待（ms）


class HiofdProvider(GeoProvider):
    name = "hiofd"

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        self._pw = None
        self._browser = None
        self._page = None
        self._last_used = 0.0
        self._broken = False

    # ------------------------------------------------------------ 生命周期

    def _ensure_page(self):
        if self._page is not None and not self._broken:
            return self._page
        self._close_quiet()
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        self._page = ctx.new_page()
        self._page.goto(_PAGE_URL, wait_until="domcontentloaded", timeout=30000)
        self._page.wait_for_timeout(3000)  # 等本机 IP 初次查询结束
        self._broken = False
        log.info("hiofd.browser_ready")
        return self._page

    def _close_quiet(self) -> None:
        for closer in (
            lambda: self._page and self._page.close(),
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        self._page = self._browser = self._pw = None

    def maybe_gc(self) -> None:
        """空闲浏览器回收（由 collector 周期调用）。"""
        with self._lock:
            if self._page is not None and time.monotonic() - self._last_used > _IDLE_EXIT_SEC:
                self._close_quiet()
                log.info("hiofd.browser_idle_closed")

    # ------------------------------------------------------------ 查询

    def lookup(self, ip: str) -> GeoInfo | None:
        with self._lock:
            try:
                page = self._ensure_page()
                # 节流：模拟真实用户操作间隔
                since = time.monotonic() - self._last_used
                if 0 < since < _QUERY_INTERVAL:
                    time.sleep(_QUERY_INTERVAL - since)
                result = self._drive_query(page, ip)
                self._last_used = time.monotonic()
                self._broken = False
            except Exception as exc:
                self._broken = True
                self._close_quiet()
                log.warning("hiofd.query_failed", ip=ip, error=str(exc))
                return None
        return self._parse_text(ip, result)

    def _drive_query(self, page, ip: str) -> str:
        """页内填 IP → 点击查询 → 读结果容器文本。"""
        return page.evaluate(
            """async (ip) => {
                const input = document.getElementById('queryIp');
                const btn = document.getElementById('queryBtn');
                if (!input || !btn) return 'NO_DOM';
                input.value = ip;
                btn.click();
                for (let i = 0; i < 24; i++) {
                    await new Promise(r => setTimeout(r, 500));
                    const box = document.getElementById('resultIpAddress');
                    if (box && box.textContent.trim() === ip) {
                        const loc = document.getElementById('resultLocation');
                        const lng = document.getElementById('resultLongitude');
                        const lat = document.getElementById('resultLatitude');
                        return [
                            loc ? loc.textContent.trim() : '',
                            lng ? lng.textContent.trim() : '',
                            lat ? lat.textContent.trim() : '',
                        ].join('|');
                    }
                }
                return 'TIMEOUT';
            }""",
            ip,
        )

    def _parse_text(self, ip: str, result: str) -> GeoInfo | None:
        if not result or result in ("TIMEOUT", "NO_DOM"):
            return None
        parts = result.split("|")
        if len(parts) != 3:
            return None
        location, lng_s, lat_s = parts
        try:
            lat = float(lat_s)
            lng = float(lng_s)
        except ValueError:
            return None
        if not location or location == "-":
            return None
        # location 形如 "中国 · 上海 · 上海" / "美国 · California · Mountain View"
        segments = [s.strip() for s in location.split("·") if s.strip() and s.strip() != "-"]
        if not segments:
            return None
        country = segments[0]
        region = segments[1] if len(segments) > 1 else ""
        city = segments[2] if len(segments) > 2 else (segments[1] if len(segments) > 1 else "")
        return GeoInfo(
            country=country,
            code=None,
            region=region,
            city=city,
            lat=lat,
            lng=lng,
            source="hiofd",
        )

    def close(self) -> None:
        with self._lock:
            self._close_quiet()
