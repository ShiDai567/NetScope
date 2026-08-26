"""DeviceService：终端表维护、速率差分、LAN 布局坐标。"""

import threading

from core import lan_layout
from core.log import get_logger
from core.utils.timeutil import now_ts
from network.adapters.device import adapt_terminal

log = get_logger("network.services.device")


class DeviceService:
    def __init__(self, store, gateway_ip: str | None) -> None:
        self._store = store
        self._gateway_ip = gateway_ip
        self._lock = threading.Lock()
        # ip → {prev_up, prev_down, prev_ts, up_rate, down_rate}
        self._rate_state: dict[str, dict] = {}
        self._devices: list[dict] = []
        self._coords: dict[str, tuple[float, float]] = {}
        self._dirty = False

    def set_gateway_ip(self, ip: str | None) -> None:
        """网关 IP 动态更新：iface 任务探测路由器 LAN IP 后调用。

        终端列表不含路由器自身（monitor_lanip 只列被管理终端），
        因此在设备表中合成网关条目，确保 LAN 场景中心有真实节点。
        """
        if not ip or ip == self._gateway_ip:
            return
        self._gateway_ip = ip
        with self._lock:
            found = False
            for dev in self._devices:
                dev["is_gateway"] = dev["ip"] == ip
                if dev["is_gateway"]:
                    found = True
            if not found:
                self._devices.append(
                    {
                        "ip": ip,
                        "mac": None,
                        "hostname": "iKuai Router",
                        "vendor": None,
                        "interface": None,
                        "is_gateway": True,
                        "connections": 0,
                        "up_rate": 0.0,
                        "down_rate": 0.0,
                        "ring_index": None,
                        "lat": None,
                        "lng": None,
                    }
                )
            self._dirty = True

    _GATEWAY_HOSTNAME = "iKuai Router"

    def _synth_gateway(self) -> dict:
        """合成网关条目（终端列表不含路由器自身）。"""
        return {
            "ip": self._gateway_ip,
            "mac": None,
            "hostname": self._GATEWAY_HOSTNAME,
            "vendor": None,
            "interface": None,
            "is_gateway": True,
            "connections": 0,
            "up_rate": 0.0,
            "down_rate": 0.0,
            "ring_index": None,
            "lat": None,
            "lng": None,
        }

    def update(self, terminal_rows: list[dict], center: tuple[float, float] | None) -> list[dict]:
        rows = [r for r in (adapt_terminal(row, self._gateway_ip) for row in terminal_rows) if r]
        now = now_ts()
        with self._lock:
            if self._gateway_ip:
                prev_gw = next(
                    (d for d in self._devices if d.get("is_gateway")), None
                )
                gw = self._synth_gateway()
                if prev_gw:
                    # 保留上一轮速率（由 set_gateway_rates 注入的 WAN 口速率）
                    gw["up_rate"] = prev_gw.get("up_rate", 0.0)
                    gw["down_rate"] = prev_gw.get("down_rate", 0.0)
                    gw["connections"] = prev_gw.get("connections", 0)
                if not any(d["ip"] == self._gateway_ip for d in rows):
                    rows.append(gw)
            for dev in rows:
                if dev.get("is_gateway") and "upload_total" not in dev:
                    continue  # 合成网关无终端计数，速率由 set_gateway_rates 注入
                state = self._rate_state.setdefault(
                    dev["ip"],
                    {"prev_up": None, "prev_down": None, "prev_ts": None, "up_rate": 0.0, "down_rate": 0.0},
                )
                if state["prev_ts"] is not None:
                    dt = now - state["prev_ts"]
                    if dt > 0.5:
                        d_up = dev["upload_total"] - state["prev_up"]
                        d_down = dev["download_total"] - state["prev_down"]
                        if d_up >= 0 and d_down >= 0:
                            new_up = d_up / dt
                            new_down = d_down / dt
                            state["up_rate"] = state["up_rate"] * 0.5 + new_up * 0.5
                            state["down_rate"] = state["down_rate"] * 0.5 + new_down * 0.5
                state["prev_up"] = dev["upload_total"]
                state["prev_down"] = dev["download_total"]
                state["prev_ts"] = now
                dev.pop("upload_total", None)
                dev.pop("download_total", None)
                dev["up_rate"] = round(state["up_rate"], 2)
                dev["down_rate"] = round(state["down_rate"], 2)

            lan_layout.assign_positions(rows, center)
            if self._devices != rows:
                self._dirty = True
            self._devices = rows
            self._coords = {d["ip"]: (d["lat"], d["lng"]) for d in rows if d["lat"] is not None}
            return rows

    def set_gateway_rates(self, up_bps: float, down_bps: float) -> None:
        """网关（路由器自身）速率 = WAN 口总速率（iface 任务注入）。"""
        with self._lock:
            for dev in self._devices:
                if dev["is_gateway"]:
                    dev["up_rate"] = round(up_bps, 2)
                    dev["down_rate"] = round(down_bps, 2)
                    self._dirty = True
                    return

    def set_center(self, center: tuple[float, float]) -> None:
        """核心位置变更：围绕新中心立即重排全部设备坐标。"""
        with self._lock:
            lan_layout.assign_positions(self._devices, center)
            self._coords = {
                d["ip"]: (d["lat"], d["lng"])
                for d in self._devices
                if d["lat"] is not None
            }
            self._dirty = True

    def flush(self, force: bool = False) -> bool:
        """设备表写入 Redis；变更或强制时执行。"""
        with self._lock:
            if not (self._dirty or force):
                return False
            devices = [dict(d) for d in self._devices]
            self._dirty = False
        if devices:
            self._store.put_devices(devices)
        return True

    def flush_and_get(self) -> list[dict] | None:
        """设备表写入 Redis；有变更返回最新列表，无变更返回 None。"""
        if not self.flush():
            return None
        return self.snapshot()

    def coords(self) -> dict[str, tuple[float, float]]:
        with self._lock:
            return dict(self._coords)

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(d) for d in self._devices]
