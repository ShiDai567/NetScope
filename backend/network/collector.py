"""CollectorRuntime：采集全链路装配（doc §5）。

datasource → adapters → services → analytics → Redis/EventBus → WebSocket
由 collect_network 命令或进程内线程（RUN_COLLECTOR_IN_PROCESS=1）启动。
"""

import asyncio
import os

# Playwright evaluate 会在工作线程留下事件循环标记，使 Django ORM 的
# async 安全检测误报（SynchronousOnlyOperation）。collector 内所有 ORM
# 调用均在 to_thread 串行执行，无并发风险，显式放行。
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from analytics.aggregators import RollingCounters
from analytics.bandwidth import BandwidthTracker
from analytics.services import NetworkStatisticsService
from core.event_bus import EventBus
from core.geo.hiofd_provider import HiofdProvider
from core.geo.manual_overrides import ManualOverrides
from core.geo.service import GeoService
from core.log import configure_logging, get_logger
from core.redis_store import RedisStore, get_store
from core.utils.network import host_of
from core.utils.timeutil import now_ts
from datasource.ikuai.gateway import IKuaiGateway, parse_iface_info, parse_lan_ip
from datasource.ikuai.scheduler import PollScheduler, TaskSpec
from network.adapters.systeminfo import extract_system_metrics
from network.services.connection_service import ConnectionService
from network.services.device_service import DeviceService
from network.services.packet_service import PacketService
from network.services.status_service import StatusService

log = get_logger("network.collector")


def build_geo_service(store, settings) -> GeoService:
    """Geo 装配：SQL GeoLookup 表为主源，hiofd API 兜底（查得即落库）。"""
    providers = []
    manual = ManualOverrides()
    manual.load_env(getattr(settings, "MANUAL_GEO_JSON", None))
    if getattr(settings, "DATA_SOURCE", "ikuai") == "mock":
        from datasource.mock.scenarios import MOCK_GEO_OVERRIDES

        manual.register(MOCK_GEO_OVERRIDES)
    providers.append(manual)
    hiofd = None
    if getattr(settings, "GEO_API_ENABLED", True):
        hiofd = HiofdProvider(timeout=getattr(settings, "GEO_API_TIMEOUT", 6.0))
        providers.append(hiofd)
    return GeoService(store, providers), hiofd


def build_source(settings):
    """按 DATA_SOURCE 构造数据源：ikuai | mock。"""
    if getattr(settings, "DATA_SOURCE", "ikuai") == "mock":
        from datasource.mock.generator import MockSource

        return MockSource(getattr(settings, "MOCK_SCENARIO", "mixed"))
    from datasource.ikuai.session_manager import SessionManager

    session = SessionManager(
        router_url=settings.IKUAI_ROUTER_URL,
        username=settings.IKUAI_USERNAME,
        password=settings.IKUAI_PASSWORD,
        timeout=settings.IKUAI_REQUEST_TIMEOUT,
        verify_ssl=getattr(settings, "IKUAI_SSL_VERIFY", True),
    )
    return IKuaiGateway(session)


class CollectorRuntime:
    def __init__(self, source, settings, store: RedisStore | None = None) -> None:
        self.settings = settings
        self.source = source
        self.store = store or get_store()
        self.bus = EventBus()
        self.counters = RollingCounters()
        self.bandwidth = BandwidthTracker()
        self.geo, self._hiofd = build_geo_service(self.store, settings)

        gateway_ip = getattr(settings, "GATEWAY_IP", None) or host_of(
            getattr(settings, "IKUAI_ROUTER_URL", "")
        )
        self.status = StatusService(
            self.store,
            self.bus,
            self.geo,
            server_lat=getattr(settings, "SERVER_LAT", None),
            server_lng=getattr(settings, "SERVER_LNG", None),
            server_location=getattr(settings, "SERVER_LOCATION", None),
            on_geo_change=self._on_geo_change,
        )
        self.packets = PacketService(self.store, self.bus, self.counters)
        self._devices = DeviceService(self.store, gateway_ip)
        self.conns = ConnectionService(
            self.store,
            self.packets,
            self.geo,
            listen_ports=getattr(settings, "LISTEN_PORTS", frozenset()),
            wan_ip_provider=lambda: self._wan_ip,
            lan_coords_provider=self._devices.coords,
            update_every=getattr(settings, "CONN_UPDATE_EVERY_SWEEPS", 3),
            close_gap_sweeps=getattr(settings, "CONN_CLOSE_GAP_SWEEPS", 2),
            sweep_interval=getattr(settings, "IKUAI_CONN_POLL_INTERVAL", 5.0),
        )
        self.stats_svc = NetworkStatisticsService(
            self.counters,
            self.bandwidth,
            self.store,
            self.status.mode_info,
            self.conns.active_count,
        )
        self._wan_ip: str | None = None
        self._wan_up_bps: float | None = None
        self._wan_down_bps: float | None = None
        self._iface_stats: dict = {}
        self._last_session_error: str | None = None
        self._stats_bcast_timer = 0.0
        self._node_rebuild_counter = 0
        self._pending_geo_epoch: tuple[float, float, int] | None = None
        self._scheduler = PollScheduler()
        self._register_tasks()

    # ------------------------------------------------------------ 任务注册

    def _register_tasks(self) -> None:
        s = self.settings
        self._scheduler.register(TaskSpec("terminals", s.IKUAI_TERMINAL_POLL_INTERVAL, self._task_terminals))
        self._scheduler.register(TaskSpec("connections", s.IKUAI_CONN_POLL_INTERVAL, self._task_connections))
        self._scheduler.register(TaskSpec("system", s.IKUAI_SYSTEM_POLL_INTERVAL, self._task_system))
        self._scheduler.register(
            TaskSpec("iface", getattr(s, "IKUAI_IFACE_POLL_INTERVAL", 10.0), self._task_iface)
        )
        self._scheduler.register(TaskSpec("wan", s.IKUAI_WAN_POLL_INTERVAL, self._task_wan))
        self._scheduler.register(
            TaskSpec("aggregate", getattr(s, "AGG_TICK_INTERVAL", 1.0), self._task_aggregate)
        )
        self._scheduler.register(
            TaskSpec("broadcast", s.BROADCAST_INTERVAL_MS / 1000.0, self._task_broadcast)
        )
        self._scheduler.register(
            TaskSpec("heartbeat", getattr(s, "HEARTBEAT_INTERVAL", 15.0), self._task_heartbeat)
        )
        self._scheduler.register(
            TaskSpec("persist", getattr(s, "PERSIST_INTERVAL", 60.0), self._task_persist)
        )

    # ------------------------------------------------------------ 数据源任务

    async def _task_terminals(self) -> None:
        rows = await asyncio.to_thread(self.source.get_terminals)
        center = self.status.gateway_center()
        self._devices.update(rows, center)
        devices = await asyncio.to_thread(self._devices.flush_and_get)
        if devices is not None:
            await self.bus.send_immediate("devices", {"devices": devices})

    async def _task_connections(self) -> None:
        packets = []
        for dev in self._devices.snapshot():
            try:
                rows = await asyncio.to_thread(self.source.get_connections, dev["ip"])
            except Exception as exc:
                await self._record_source_error(exc)
                continue
            result = await asyncio.to_thread(self.conns.process_rows, rows, dev["ip"])
            packets.extend(result.new_packets)
        closed_packets = await asyncio.to_thread(self.conns.close_stale)
        packets.extend(closed_packets)
        if packets:
            await asyncio.to_thread(self.packets.publish, packets)
        await asyncio.to_thread(
            self._record_source_ok,
        )

    async def _task_system(self) -> None:
        try:
            raw = await asyncio.to_thread(self.source.get_system_info)
        except Exception as exc:
            await self._record_source_error(exc)
            return
        cpu, mem = extract_system_metrics(raw)
        await asyncio.to_thread(self.store.set_sys_metrics, cpu, mem)
        conn_num = raw.get("conn_num") if isinstance(raw, dict) else None
        if conn_num is not None:
            await asyncio.to_thread(self.store.set_sys_metrics_extra, conn_num=int(conn_num))

    async def _task_iface(self) -> None:
        """monitor_iface：权威 WAN 带宽 + 线路质量（rtt/丢包）+ WAN IP + 网关 LAN IP。"""
        try:
            raw = await asyncio.to_thread(self.source.get_iface_info)
        except Exception as exc:
            await self._record_source_error(exc)
            return
        info = parse_iface_info(raw)
        self._iface_stats = info
        if info["up_bps"] or info["down_bps"]:
            self._wan_up_bps = info["up_bps"]
            self._wan_down_bps = info["down_bps"]
        if info["wan_ip"]:
            self._wan_ip = info["wan_ip"]
        lan_ip = parse_lan_ip(raw)
        if lan_ip:
            self._devices.set_gateway_ip(lan_ip)
        if info["up_bps"] or info["down_bps"]:
            self._devices.set_gateway_rates(info["up_bps"], info["down_bps"])
        await asyncio.to_thread(self.store.set_line_quality, info["avg_rtt_ms"], info["loss_rate"])

    # ------------------------------------------------------------ 核心位置变更联动

    def _on_geo_change(self, lat: float, lng: float, epoch: int) -> None:
        """SERVER_LOCATION 变化：设备立即围绕新中心重排落库（广播由 wan 任务异步补发）。"""
        self._devices.set_center((lat, lng))
        self._devices.flush(force=True)
        self._pending_geo_epoch = (lat, lng, epoch)

    async def _task_wan(self) -> None:
        wan_ip = await asyncio.to_thread(self.source.get_wan_ip)
        if wan_ip:
            self._wan_ip = wan_ip
        await asyncio.to_thread(self.status.update_gateway_from_wan, self._wan_ip)
        pending = self._pending_geo_epoch
        if pending:
            self._pending_geo_epoch = None
            lat, lng, epoch = pending
            await self.bus.send_immediate(
                "status",
                {"state": "geo_changed", "geo_epoch": epoch, "lat": lat, "lng": lng,
                 "t": now_ts()},
            )

    # ------------------------------------------------------------ 聚合/广播

    async def _task_aggregate(self) -> None:
        now = now_ts()
        if self._wan_up_bps is not None:
            up, down = self._wan_up_bps, self._wan_down_bps or 0.0
        else:
            up, down = await asyncio.to_thread(self.conns._rates_snapshot)
        self.bandwidth.push(now, up, down)

        ops = await asyncio.to_thread(self.counters.flush_ops)
        if ops:
            await asyncio.to_thread(self.store.flush_counter_ops, ops)
        await asyncio.to_thread(self.store.push_bw, now, up, down)

        for window in getattr(self.settings, "STATS_WINDOWS", (300,)):
            snapshot = await asyncio.to_thread(self.stats_svc.build, window, now)
            await asyncio.to_thread(self.store.set_stats, window, snapshot)

        if now - self._stats_bcast_timer >= 2.0:
            self._stats_bcast_timer = now
            snapshot = await asyncio.to_thread(self.store.get_stats, self._default_window())
            if snapshot:
                self.bus.enqueue("stats", snapshot)
        self.bus.enqueue(
            "traffic",
            {"t": round(now, 3), "up_bps": round(up, 2), "down_bps": round(down, 2)},
        )

    async def _task_broadcast(self) -> None:
        await self.bus.broadcast_batch()
        self._node_rebuild_counter += 1
        if self._node_rebuild_counter >= 3:
            self._node_rebuild_counter = 0
            peers = await asyncio.to_thread(self.conns.top_peers)
            if peers:
                await asyncio.to_thread(self.status.rebuild_nodes, peers)
                nodes = await asyncio.to_thread(self.store.get_nodes)
                self.bus.enqueue("nodes", {"nodes": nodes})

    async def _task_heartbeat(self) -> None:
        await asyncio.to_thread(self.store.heartbeat)
        self.bus.enqueue("heartbeat", {"t": now_ts()})
        # Geo 浏览器空闲回收（hiofd provider 常驻内存控制）
        geo_provider = self._hiofd
        if geo_provider is not None:
            await asyncio.to_thread(geo_provider.maybe_gc)

    async def _task_persist(self) -> None:
        await asyncio.to_thread(self._persist_snapshot)

    def _persist_snapshot(self) -> None:
        """TrafficSnapshot 分钟级落库（失败只告警不影响实时链路）。"""
        try:
            from datetime import UTC

            from django.db import close_old_connections
            from django.utils import timezone as dj_tz

            from analytics.models import TrafficSnapshot

            close_old_connections()
            now = now_ts()
            up_bps, down_bps = self.bandwidth.latest()
            totals = self.store.get_totals()
            TrafficSnapshot.objects.update_or_create(
                ts=dj_tz.datetime.fromtimestamp(int(now // 60 * 60), tz=UTC),
                bucket_s=60,
                defaults={
                    "up_bytes": int(up_bps * 60),
                    "down_bytes": int(down_bps * 60),
                    "up_bps": round(up_bps, 2),
                    "down_bps": round(down_bps, 2),
                    "pkts_total": totals.get("total", 0),
                    "conn_active_max": self.conns.active_count(),
                },
            )
        except Exception as exc:
            log.warning("persist.snapshot_failed", error=str(exc))

    def _default_window(self) -> int:
        windows = getattr(self.settings, "STATS_WINDOWS", (300,))
        return windows[len(windows) // 2] if windows else 300

    # ------------------------------------------------------------ 数据源健康

    def _record_source_ok(self) -> None:
        router_url = getattr(self.settings, "IKUAI_ROUTER_URL", None)
        session = getattr(self.source, "session", None)
        self.status.record_poll_ok(
            router_url=router_url,
            connected_at=session.connected_at if session else now_ts(),
            last_poll_at=now_ts(),
        )
        self._last_session_error = None

    async def _record_source_error(self, exc: Exception) -> None:
        message = str(exc)[:200]
        if message != self._last_session_error:
            self._last_session_error = message
            log.warning("collector.source_error", error=message)
        session = getattr(self.source, "session", None)
        self.status.record_error(
            router_url=getattr(self.settings, "IKUAI_ROUTER_URL", None),
            error=message,
            last_poll_at=session.last_poll_at if session else None,
            connected_at=session.connected_at if session else None,
        )

    # ------------------------------------------------------------ 生命周期

    async def run(self) -> None:
        configure_logging(getattr(self.settings, "LOG_LEVEL", "INFO"))
        mode = "mock" if getattr(self.settings, "DATA_SOURCE", "ikuai") == "mock" else "ikuai"
        self.status.ensure_started(mode)
        log.info(
            "collector.start",
            mode=mode,
            source=type(self.source).__name__,
            windows=list(getattr(self.settings, "STATS_WINDOWS", ())),
        )
        try:
            await self._scheduler.run(asyncio.Event())
        finally:
            log.info("collector.stop")
