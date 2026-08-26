"""hiofd IP 归属地 Provider（Playwright 驱动真实页面查询）。

数据源（按序自动切换）：
  1. tool.hiofd.com/ip/ —— 区县级精度，接口有混淆签名 + WAF 风控，
     由真实浏览器加载页面后驱动其原生查询满足签名
  2. ip-api.com/json/?lang=zh-CN —— 无签名公开 JSON 接口，浏览器直连，
     作为 hiofd 风控（IP 级封禁）时的降级源

线程模型：
  - Playwright Sync API 不能在 asyncio 环境调用
  - 内建专属工作线程，浏览器启动/查询/关闭全部在该线程执行

成本控制：
  - 浏览器按需启动，空闲自动退出（工作线程 queue 超时）
  - 查询结果写回 SQL GeoLookup 表，同 IP 永不二次查询
"""

import queue
import threading
import time

from core.geo.provider import GeoInfo, GeoProvider
from core.log import get_logger

log = get_logger("core.geo.hiofd")

_HIOFD_PAGE = "https://tool.hiofd.com/ip/"
_IPAPI_URL = "http://ip-api.com/json/{ip}?lang=zh-CN&fields=status,message,country,countryCode,regionName,city,district,isp,lat,lon"
_IDLE_EXIT_SEC = 300.0
_QUERY_INTERVAL = 2.0

_STOP = object()
_FAILS_BEFORE_FALLBACK = 2  # hiofd 连续失败 N 次后本会话切 ip-api


class HiofdProvider(GeoProvider):
    name = "hiofd"

    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout
        self._last_used = 0.0
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._thread_lock = threading.Lock()
        self._page_ready = False
        self._hiofd_fails = 0

    # ------------------------------------------------------------ 对外接口

    def lookup(self, ip: str) -> GeoInfo | None:
        """同步接口：投递查询到工作线程并等待结果。

        首次调用含浏览器冷启动，等待上限 60s；稳态查询 20s 级。
        """
        self._ensure_thread()
        result_queue: queue.Queue = queue.Queue(maxsize=1)
        self._queue.put((ip, result_queue))
        try:
            text = result_queue.get(timeout=self._wait_timeout())
        except queue.Empty:
            log.warning("hiofd.query_timeout", ip=ip)
            return None
        if text is None:
            return None
        return self._parse_text(ip, text)

    def _wait_timeout(self) -> float:
        return 60.0 if not self._page_ready else self._timeout + _QUERY_INTERVAL

    def maybe_gc(self) -> None:
        """空闲回收由工作线程 queue 超时自动完成（接口保留供心跳调用）。"""

    def close(self) -> None:
        with self._thread_lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread.is_alive():
            self._queue.put(_STOP)
            thread.join(timeout=10)

    # ------------------------------------------------------------ 工作线程

    def _ensure_thread(self) -> None:
        with self._thread_lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._worker, name="hiofd-browser", daemon=True
                )
                self._thread.start()

    def _worker(self) -> None:
        page = None
        pw = browser = None
        try:
            while True:
                try:
                    item = self._queue.get(timeout=_IDLE_EXIT_SEC)
                except queue.Empty:
                    log.info("hiofd.browser_idle_closed")
                    break
                if item is _STOP:
                    break
                ip, result_queue = item
                try:
                    if page is None:
                        page, pw, browser = self._launch()
                        self._page_ready = True
                    since = time.monotonic() - self._last_used
                    if 0 < since < _QUERY_INTERVAL:
                        time.sleep(_QUERY_INTERVAL - since)
                    text = self._query_via_page(page, ip)
                    self._last_used = time.monotonic()
                except Exception as exc:
                    log.warning("hiofd.query_failed", ip=ip, error=str(exc))
                    self._close_quiet(page, browser, pw)
                    page = pw = browser = None
                    self._page_ready = False
                    text = None
                try:
                    result_queue.put_nowait(text)
                except Exception:
                    pass
        finally:
            self._close_quiet(page, browser, pw)

    # ------------------------------------------------------------ 查询实现

    def _query_via_page(self, page, ip: str) -> str:
        """hiofd 页面查询；连续失败切换 ip-api 降级源（浏览器直接导航，无 CORS 限制）。"""
        if self._hiofd_fails < _FAILS_BEFORE_FALLBACK:
            text = self._drive_query(page, ip)
            if text not in (None, "TIMEOUT", "NO_DOM"):
                self._hiofd_fails = 0
                return f"hiofd|{text}"
            self._hiofd_fails += 1
            log.warning("hiofd.source_degraded", fails=self._hiofd_fails)
        # 降级：ip-api.com（浏览器直接导航到 JSON 端点）
        try:
            resp = page.goto(
                _IPAPI_URL.format(ip=ip),
                wait_until="domcontentloaded",
                timeout=self._timeout * 1000,
            )
            if resp is not None and resp.ok:
                body = resp.text()
                if body:
                    return f"ipapi|{body}"
        except Exception as exc:
            log.warning("hiofd.fallback_failed", ip=ip, error=str(exc))
        # 回到 hiofd 页面，下次主源继续可用
        try:
            page.goto(_HIOFD_PAGE, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1500)
        except Exception:
            self._page_ready = False
        return None

    def _launch(self):
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = ctx.new_page()
        page.goto(_HIOFD_PAGE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        log.info("hiofd.browser_ready")
        return page, pw, browser

    def _close_quiet(self, page, browser, pw) -> None:
        for closer in (
            lambda: page and page.close(),
            lambda: browser and browser.close(),
            lambda: pw and pw.stop(),
        ):
            try:
                closer()
            except Exception:
                pass

    def _drive_query(self, page, ip: str) -> str:
        """hiofd 页内查询：'location|lng|lat|isp|district|street'。"""
        return page.evaluate(
            """async (ip) => {
                const input = document.getElementById('queryIp');
                const btn = document.getElementById('queryBtn');
                if (!input || !btn) return 'NO_DOM';
                input.value = ip;
                btn.click();
                const get = (id) => {
                    const el = document.getElementById(id);
                    return el ? el.textContent.trim() : '';
                };
                for (let i = 0; i < 24; i++) {
                    await new Promise(r => setTimeout(r, 500));
                    const box = document.getElementById('resultIpAddress');
                    if (box && box.textContent.trim() === ip) {
                        return [
                            get('resultLocation'),
                            get('resultLongitude'),
                            get('resultLatitude'),
                            get('resultIsp'),
                            get('resultDistrict'),
                            get('resultStreet'),
                        ].join('|');
                    }
                }
                return 'TIMEOUT';
            }""",
            ip,
        )

    # ------------------------------------------------------------ 解析

    def _parse_text(self, ip: str, result: str) -> GeoInfo | None:
        if not result:
            return None
        source, _, payload = result.partition("|")
        if source == "ipapi":
            return self._parse_ipapi(payload)
        return self._parse_hiofd(payload)

    def _parse_hiofd(self, payload: str) -> GeoInfo | None:
        parts = payload.split("|")
        if len(parts) != 6:
            return None
        location, lng_s, lat_s, isp, district, street = parts
        try:
            lat = float(lat_s)
            lng = float(lng_s)
        except ValueError:
            return None
        if not location or location == "-":
            return None
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
            district=_clean(district),
            street=_clean(street),
            isp=_clean(isp),
        )

    def _parse_ipapi(self, payload: str) -> GeoInfo | None:
        import json

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or data.get("status") != "success":
            return None
        lat, lng = data.get("lat"), data.get("lon")
        if lat is None or lng is None:
            return None
        return GeoInfo(
            country=str(data.get("country") or "Unknown"),
            code=data.get("countryCode") or None,
            region=str(data.get("regionName") or ""),
            city=str(data.get("city") or ""),
            lat=float(lat),
            lng=float(lng),
            source="ip-api",
            district=_clean(str(data.get("district") or "")),
            street="",
            isp=_clean(str(data.get("isp") or "")),
        )


def _clean(v: str) -> str:
    v = (v or "").strip()
    return v if v and v != "-" else ""
