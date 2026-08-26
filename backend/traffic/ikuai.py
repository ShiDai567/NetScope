"""iKuai 路由器集成：基于仓库内 sdk/ikuai_sdk 拉取真实连接数据。

工作流程：
1. 通过 SDK 登录路由器面板，获得 cookie_header
2. 周期拉取接口实时速率（monitor_iface iface_stream）作为权威上下行带宽
3. 周期拉取终端列表（monitor_lanip data）作为内网设备
4. 对连接数最多的前 N 个终端拉取连接明细（monitor_lanip conn）
5. 按 AGENTS.md 规则转换为标准数据包，并做快照 diff 发射事件

主地址被 WAF 拦截或不可达时自动轮换到备用地址（如内网 http://10.0.1.1:6301）。
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any, Callable, Optional

from ikuai_sdk import IKuaiClient
from ikuai_sdk.exceptions import IKuaiError

from .geo import internal_ring_position
from .packets import TCP_STATUS_CLOSED, build_packet

MAX_DETAIL_DEVICES = 8
POLL_INTERVAL = 2.0
URL_ROTATE_AFTER_FAILURES = 4
SYSTEM_SAMPLE_INTERVAL = 10.0


class IKuaiPoller(threading.Thread):
    def __init__(
        self,
        *,
        router_url: str,
        username: str,
        password: str,
        emit: Callable[[dict[str, Any]], None],
        device_snapshot: Callable[[list[dict[str, Any]]], None],
        gateway: tuple[float, float],
        on_error: Callable[[str], None],
        bandwidth_sample: Optional[Callable[[float, float], None]] = None,
        system_sample: Optional[Callable[[float, float], None]] = None,
        fallback_url: str = "",
    ):
        super().__init__(name="netscope-ikuai-poller", daemon=True)
        self._urls = [u.strip().rstrip("/") for u in (router_url, fallback_url) if u and u.strip()]
        if not self._urls:
            raise ValueError("router_url is required")
        self.username = username
        self.password = password
        self._emit = emit
        self._device_snapshot = device_snapshot
        self.gateway = gateway
        self._on_error = on_error
        self._bandwidth_sample = bandwidth_sample
        self._system_sample = system_sample
        self._client = IKuaiClient(timeout=8)
        self._cookie_header: Optional[str] = None
        self._stop_event = threading.Event()
        self._prev: dict[str, dict[str, Any]] = {}
        self._lan_positions: dict[str, tuple[float, float]] = {}
        self.last_error: Optional[str] = None
        self.last_poll_at: Optional[float] = None
        self._url_pos = 0
        self._fail_count = 0
        self._last_system_at = 0.0
        self._last_system: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------------
    @property
    def current_url(self) -> str:
        return self._urls[self._url_pos]

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:  # pragma: no cover - 线程循环
        while not self._stop_event.is_set():
            try:
                self._poll_once()
                self.last_error = None
                self._fail_count = 0
            except IKuaiError as exc:
                self._register_failure(f"iKuai 接口错误: {exc}")
            except Exception as exc:  # 任何异常都不杀死线程
                self._register_failure(f"轮询异常: {exc}")
            self._stop_event.wait(POLL_INTERVAL)

    def _register_failure(self, message: str) -> None:
        """记录失败；连续多次失败且配置了备用地址时自动切换。"""
        self.last_error = message
        self._on_error(message)
        self._fail_count += 1
        if (
            len(self._urls) > 1
            and self._fail_count >= URL_ROTATE_AFTER_FAILURES
        ):
            self._url_pos = (self._url_pos + 1) % len(self._urls)
            self._fail_count = 0
            self._cookie_header = None  # 新地址需要重新登录

    # ------------------------------------------------------------------
    def test_connection(self) -> dict[str, Any]:
        """供 /api/ikuai/connect 调用：验证登录可用。"""
        result = self._client.login(
            router_url=self.current_url,
            username=self.username,
            password=self.password,
        )
        if result.result_code not in {0, 10000} or not result.cookie_header:
            raise IKuaiError(result.result_message or "登录失败")
        self._cookie_header = result.cookie_header
        return {
            "sess_key": result.sess_key,
            "message": result.result_message,
            "mode": result.request_mode,
            "router_url": self.current_url,
        }

    def _ensure_login(self) -> str:
        if not self._cookie_header:
            self.test_connection()
        assert self._cookie_header
        return self._cookie_header

    def _call(self, func, **kwargs):
        """统一调用 SDK，登录态失效时自动重登一次。"""
        cookie = self._ensure_login()
        result = func(router_url=self.current_url, cookie_header=cookie, **kwargs)
        if result.result_code in {10004, 40001, None} and result.upstream_status in {
            401,
            403,
            None,
        }:
            self._cookie_header = None
            cookie = self._ensure_login()
            result = func(router_url=self.current_url, cookie_header=cookie, **kwargs)
        return result

    # ------------------------------------------------------------------
    def _poll_once(self) -> None:
        now = time.time()

        # 1) 权威上下行带宽（接口实时速率，B/s）
        try:
            self._poll_bandwidth()
        except Exception as exc:  # 带宽失败不影响连接明细采集
            self.last_error = f"带宽采样失败: {exc}"

        # 1.5) 系统负载（CPU / 内存），低频采样即可
        try:
            self._poll_system(now)
        except Exception as exc:
            self.last_error = f"系统负载采样失败: {exc}"

        # 2) 内网设备列表
        list_result = self._call(self._client.get_terminal_list, limit="0,100")
        terminals = self._extract_rows(list_result)
        devices = self._convert_devices(terminals)
        self._device_snapshot(devices)

        # 3) 连接数最多的前 N 个终端的连接明细
        terminals.sort(key=lambda r: -(r.get("connect_num") or 0))
        targets = [
            r for r in terminals[:MAX_DETAIL_DEVICES] if r.get("ip_addr")
        ]

        current: dict[str, dict[str, Any]] = {}
        for row in targets:
            ip = row["ip_addr"]
            detail = self._call(
                self._client.get_terminal_connection_details,
                ip=ip,
                maxnum=200,
                limit="0,80",
            )
            for conn_row in self._extract_conn_rows(detail):
                packet = self._convert_conn(ip, conn_row, now)
                if packet:
                    current[packet["id"]] = packet

        # diff：新增 / 变更发射；消失的连接补一条关闭事件（TCP）便于前端淡出
        for pid, packet in current.items():
            prev = self._prev.get(pid)
            if prev is None or self._meaningful_change(prev, packet):
                self._emit(packet)
        for pid, prev in self._prev.items():
            if pid not in current and prev.get("protocol") == "tcp":
                closing = dict(prev)
                closing["status"] = TCP_STATUS_CLOSED
                closing["timestamp"] = round(now, 3)
                self._emit(closing)

        self._prev = current
        self.last_poll_at = now

    # ------------------------------------------------------------------
    def _poll_bandwidth(self) -> None:
        """拉取接口实时速率，汇总所有 WAN 口作为权威上下行带宽（B/s）。"""
        if self._bandwidth_sample is None:
            return
        result = self._call(self._client.get_interface_stream)
        data = result.data
        if not isinstance(data, dict):
            return
        rows = data.get("iface_stream") or []
        wan_names = {
            w.get("interface")
            for w in (data.get("snapshoot_wan") or [])
            if isinstance(w, dict) and w.get("interface")
        }
        up_bytes = down_bytes = 0.0
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("interface")
            # 仅统计真实 WAN 口；识别不到时回退到 wan* 前缀约定，
            # 避免把 LAN 口重复计入（同一流量会同时出现在 lan/wan 上）
            is_wan = (
                name in wan_names
                if wan_names
                else str(name or "").startswith("wan")
            )
            if not is_wan:
                continue
            try:
                up_bytes += float(row.get("upload") or 0)
                down_bytes += float(row.get("download") or 0)
            except (TypeError, ValueError):
                continue
        self._bandwidth_sample(up_bytes, down_bytes)

    # ------------------------------------------------------------------
    def _poll_system(self, now: float) -> None:
        """拉取系统负载（monitor_system 历史采样的最新一条），10s 缓存。"""
        if self._system_sample is None:
            return
        if self._last_system_at and now - self._last_system_at < SYSTEM_SAMPLE_INTERVAL:
            self._system_sample(*self._last_system)
            return
        result = self._call(self._client.get_system_monitor)
        data = result.data
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            return
        latest = rows[-1]
        cpu = float(latest.get("cpu") or 0)
        mem = float(latest.get("memory_use") or 0)
        self._last_system = (cpu, mem)
        self._last_system_at = now
        self._system_sample(cpu, mem)

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_rows(result) -> list[dict[str, Any]]:
        data = result.data
        if isinstance(data, dict):
            rows = data.get("data") or data.get("Data") or []
            return [r for r in rows if isinstance(r, dict)]
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []

    @staticmethod
    def _extract_conn_rows(result) -> list[dict[str, Any]]:
        data = result.data
        if isinstance(data, dict):
            rows = data.get("conn") or data.get("data") or []
            return [r for r in rows if isinstance(r, dict)]
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []

    # ------------------------------------------------------------------
    def _convert_devices(
        self, terminals: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        devices = [
            {
                "ip": "10.0.1.1",
                "mac": "--",
                "hostname": "iKuai 主路由",
                "vendor": "iKuai",
                "interface": "lan1",
                "is_gateway": True,
                "lat": self.gateway[0],
                "lng": self.gateway[1],
                "connections": 0,
                "up_rate": 0.0,
                "down_rate": 0.0,
            }
        ]
        self._lan_positions = {}
        for idx, row in enumerate(terminals):
            ip = str(row.get("ip_addr") or "").strip()
            if not ip:
                continue
            lat, lng = internal_ring_position(idx, self.gateway)
            self._lan_positions[ip] = (lat, lng)
            hostname = (
                row.get("comment")
                or row.get("termname")
                or row.get("mac_gnames")
                or ip
            )
            devices.append(
                {
                    "ip": ip,
                    "mac": row.get("mac") or "--",
                    "hostname": hostname,
                    "vendor": row.get("client_vendor") or row.get("uplink_dev") or "--",
                    "interface": row.get("interface") or "lan1",
                    "is_gateway": False,
                    "lat": lat,
                    "lng": lng,
                    "connections": int(row.get("connect_num") or 0),
                    "up_rate": float(row.get("upload") or 0),
                    "down_rate": float(row.get("download") or 0),
                    "total_up": int(row.get("total_up") or 0),
                    "total_down": int(row.get("total_down") or 0),
                }
            )
        return devices

    # ------------------------------------------------------------------
    def _convert_conn(
        self, device_ip: str, row: dict[str, Any], now: float
    ) -> Optional[dict[str, Any]]:
        dst_addr = str(row.get("dst_addr") or "").strip()
        forward_addr = str(row.get("forward_addr") or "").strip()
        if not dst_addr or not forward_addr:
            return None
        proto = str(row.get("protocol") or "tcp").lower()
        src_port = int(row.get("src_port") or 0)
        dst_port = int(row.get("dst_port") or 0)
        key = f"{device_ip}|{proto}|{src_port}|{dst_addr}|{dst_port}|{forward_addr}"
        pid = "ik_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

        born = now
        prev = self._prev.get(pid)
        if prev is not None:
            born = prev.get("born", now)

        packet = build_packet(
            packet_id=pid,
            timestamp=now,
            device_ip=device_ip,
            protocol=proto,
            status=row.get("status"),
            dst_addr=dst_addr,
            forward_addr=forward_addr,
            src_port=src_port,
            dst_port=dst_port,
            app_name=row.get("app_name"),
            total_up=int(row.get("total_up") or 0),
            total_down=int(row.get("total_down") or 0),
            gateway=self.gateway,
            domain=row.get("domain"),
            original_dst=row.get("original_dst"),
            interface=row.get("interface"),
            lan_positions=self._lan_positions,
        )
        packet["born"] = round(born, 3)
        packet["latency_ms"] = 0.0
        packet["status_since"] = round(now, 3)
        return packet

    @staticmethod
    def _meaningful_change(prev: dict[str, Any], cur: dict[str, Any]) -> bool:
        return (
            prev.get("status") != cur.get("status")
            or prev.get("total_up") != cur.get("total_up")
            or prev.get("total_down") != cur.get("total_down")
        )
