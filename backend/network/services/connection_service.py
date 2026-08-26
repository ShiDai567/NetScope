"""连接生命周期与速率差分（doc §5.3）。"""

import threading
from dataclasses import dataclass, field

from core.log import get_logger
from core.utils.network import conn_key as make_conn_key
from core.utils.network import is_public_ip
from core.utils.timeutil import now_ts
from network.adapters.direction import resolve_direction

log = get_logger("network.services.connection")


@dataclass
class _ConnState:
    born: float
    last_seen: float
    total_up: float = 0.0
    total_down: float = 0.0
    up_bps: float = 0.0
    down_bps: float = 0.0
    status: str | None = None
    status_since: float | None = None
    application: str = ""
    protocol: str = ""
    interface: str | None = None
    domain: str | None = None
    direction: str = "outbound"
    sweeps: int = 0
    emits: int = 0
    changed: bool = False
    flow_key: str = ""
    geo_src: dict | None = None
    geo_dst: dict | None = None
    peer_ip: str | None = None
    peer_domain: str | None = None
    peer_port: int = 0
    src_ip: str | None = None
    src_port: int = 0
    dst_ip: str | None = None
    dst_port: int = 0
    nat_info: dict | None = None


@dataclass
class SweepResult:
    new_packets: list[dict] = field(default_factory=list)
    closed_keys: list[str] = field(default_factory=list)
    dropped_invalid: int = 0
    dropped_external: int = 0
    conn_up_bps: float = 0.0
    conn_down_bps: float = 0.0


class ConnectionService:
    """活跃连接登记、差分速率、事件发射（new/update/closed）。"""

    def __init__(
        self,
        store,
        packets,
        geo_service,
        listen_ports: frozenset[int],
        wan_ip_provider,
        lan_coords_provider,
        update_every: int = 3,
        close_gap_sweeps: int = 2,
        sweep_interval: float = 5.0,
    ) -> None:
        self._store = store
        self._packets = packets
        self._geo = geo_service
        self._listen_ports = listen_ports
        self._wan_ip_provider = wan_ip_provider
        self._lan_coords = lan_coords_provider
        self._update_every = max(1, update_every)
        self._close_gap = max(1, close_gap_sweeps)
        self._sweep_interval = sweep_interval
        self._lock = threading.Lock()
        self.active: dict[str, _ConnState] = {}
        # 公网对端聚合：ip → {bytes, domain, port, kind, direction}
        self._peer_stats: dict[str, dict] = {}
        self._last_emit_seq = 0

    # ------------------------------------------------------------ 每轮处理

    def process_rows(self, rows: list[dict], terminal_ip: str | None) -> dict:
        """处理一个终端的全部 conn 行。返回 SweepResult。"""
        result = SweepResult()
        now = now_ts()
        seen_keys: set[str] = set()

        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                result.dropped_invalid += 1
                continue
            resolved = resolve_direction(row, terminal_ip, self._wan_ip_provider(), self._listen_ports)
            if resolved is None:
                result.dropped_invalid += 1
                continue
            if resolved.direction == "external":
                result.dropped_external += 1
                continue

            key = make_conn_key(
                resolved.local_ip,
                resolved.local_port,
                resolved.remote_ip,
                resolved.remote_port,
                row.get("protocol") or "",
            )
            seen_keys.add(key)

            total_up = _to_num(row.get("total_up"))
            total_down = _to_num(row.get("total_down"))
            status = _to_str(row.get("status"))
            domain = _to_str(row.get("domain"))
            app_name = _to_str(row.get("app_name"))
            interface = _to_str(row.get("interface"))

            with self._lock:
                state = self.active.get(key)
                if state is None:
                    state = self._create(
                        key,
                        resolved,
                        now,
                        total_up,
                        total_down,
                        status,
                        domain,
                        app_name,
                        interface,
                        row,
                    )
                    self.active[key] = state
                    packet = self._emit(key, state, now, kind="new")
                    if packet:
                        result.new_packets.append(packet)
                else:
                    self._update(
                        key,
                        state,
                        now,
                        total_up,
                        total_down,
                        status,
                        domain,
                        app_name,
                        interface,
                    )
                    state.sweeps += 1
                    if state.changed or (state.sweeps % self._update_every == 0):
                        packet = self._emit(key, state, now, kind="update")
                        if packet:
                            result.new_packets.append(packet)

        result.conn_up_bps, result.conn_down_bps = self._rates_snapshot()
        return result

    def _create(
        self, key, resolved, now, total_up, total_down, status, domain, app_name, interface, row
    ) -> _ConnState:
        geo_src = None
        geo_dst = None
        if resolved.direction == "inbound":
            geo_src = self._geo.lookup(resolved.remote_ip)
            peer_ip = resolved.remote_ip
            src_ip, src_port = resolved.remote_ip, resolved.remote_port
            dst_ip, dst_port = resolved.local_ip, resolved.local_port
        else:
            geo_dst = self._geo.lookup(resolved.remote_ip)
            peer_ip = resolved.remote_ip if resolved.direction != "internal" else None
            src_ip, src_port = resolved.local_ip, resolved.local_port
            dst_ip, dst_port = resolved.remote_ip, resolved.remote_port

        state = _ConnState(
            born=now,
            last_seen=now,
            total_up=total_up,
            total_down=total_down,
            status=status,
            status_since=now,
            application=app_name or "未知应用",
            protocol=str(row.get("protocol") or "unknown").lower(),
            interface=interface,
            domain=domain,
            direction=resolved.direction,
            sweeps=1,
            changed=True,
            flow_key=key,
            geo_src=geo_src,
            geo_dst=geo_dst,
            peer_ip=peer_ip,
            peer_domain=domain,
            peer_port=dst_port if resolved.direction != "inbound" else src_port,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
        )
        self._register_peer(state, total_up + total_down)
        self._store.upsert_conn(key, self._conn_hash(state), now)
        return state

    def _update(self, key, state, now, total_up, total_down, status, domain, app_name, interface) -> None:
        dt = now - state.last_seen
        if dt <= 0:
            dt = self._sweep_interval
        d_up = total_up - state.total_up
        d_down = total_down - state.total_down
        if d_up < 0 or d_down < 0:
            # 计数回卷（路由器重启/会话重建）：丢弃差分
            d_up = d_down = 0.0
        state.up_bps = d_up / dt
        state.down_bps = d_down / dt
        state.total_up = total_up
        state.total_down = total_down

        changed = False
        if status != state.status:
            state.status = status
            state.status_since = now
            changed = True
        if app_name and app_name != state.application:
            state.application = app_name
            changed = True
        if domain and domain != state.domain:
            state.domain = domain
            changed = True
        if interface and interface != state.interface:
            state.interface = interface
            changed = True
        state.changed = changed
        state.last_seen = now
        self._register_peer(state, max(0, d_up) + max(0, d_down))
        if changed:
            self._store.upsert_conn(key, self._conn_hash(state), now)
        else:
            self._store.touch_conns([key], now)

    def _conn_hash(self, state: _ConnState) -> dict:
        return {
            "flow_key": state.flow_key,
            "direction": state.direction,
            "application": state.application,
            "protocol": state.protocol,
            "status": state.status or "",
            "interface": state.interface or "",
            "src_ip": state.src_ip or "",
            "src_port": state.src_port,
            "dst_ip": state.dst_ip or "",
            "dst_port": state.dst_port,
            "domain": state.domain or "",
            "bytes_up": int(state.total_up),
            "bytes_down": int(state.total_down),
            "up_bps": round(state.up_bps, 2),
            "down_bps": round(state.down_bps, 2),
            "first_seen": state.born,
            "last_seen": state.last_seen,
        }

    # ------------------------------------------------------------ 过期清理

    def close_stale(self) -> list[dict]:
        """连续 N 轮未见的连接 → 关闭事件 + 移除。返回 closed packets。"""
        now = now_ts()
        gap = self._close_gap * self._sweep_interval
        threshold = now - gap
        closed_packets: list[dict] = []
        stale_keys: list[str] = []
        with self._lock:
            for key, state in list(self.active.items()):
                if state.last_seen < threshold:
                    stale_keys.append(key)
            for key in stale_keys:
                state = self.active.pop(key)
                packet = self._emit(key, state, now, kind="closed")
                if packet:
                    closed_packets.append(packet)
        if stale_keys:
            self._store.drop_conns(stale_keys)
        return closed_packets

    # ------------------------------------------------------------ 对端统计（nodes 用）

    def _register_peer(self, state: _ConnState, delta_bytes: float) -> None:
        if not state.peer_ip or not is_public_ip(state.peer_ip):
            return
        entry = self._peer_stats.setdefault(
            state.peer_ip,
            {"bytes": 0.0, "domain": None, "port": 0, "direction": state.direction},
        )
        entry["bytes"] += max(0.0, delta_bytes)
        if state.peer_domain and state.peer_domain != "--":
            entry["domain"] = state.peer_domain
        if state.peer_port:
            entry["port"] = state.peer_port

    def top_peers(self, limit: int = 64) -> list[dict]:
        with self._lock:
            entries = sorted(self._peer_stats.items(), key=lambda kv: kv[1]["bytes"], reverse=True)[:limit]
        return [{"ip": ip, **info} for ip, info in entries if info["bytes"] > 0]

    # ------------------------------------------------------------ 事件发射

    def _emit(self, key: str, state: _ConnState, now: float, kind: str) -> dict | None:
        flag = None
        if kind == "closed" and state.status == "关闭连接" and (now - state.born) < 5:
            flag = "failed"

        packet = self._packets.build_packet(
            state,
            key,
            now,
            kind=kind,
            flag=flag,
            lan_coords=self._lan_coords(),
        )
        return packet

    def _lan_coords(self) -> dict[str, tuple[float, float]]:
        provider = self._lan_coords_provider
        try:
            return provider() or {}
        except Exception:
            return {}

    def _rates_snapshot(self) -> tuple[float, float]:
        with self._lock:
            up = sum(s.up_bps for s in self.active.values())
            down = sum(s.down_bps for s in self.active.values())
        return up, down

    def active_count(self) -> int:
        with self._lock:
            return len(self.active)

    # ------------------------------------------------------------ 审计落库数据

    def take_closed_records(self) -> list[dict]:
        """收集待落库 FlowRecord（由 runtime 批量执行）。"""
        records = []
        with self._lock:
            for state in self.active.values():
                if state.status == "关闭连接":
                    continue
            # 由 close_stale 返回后单独入列，此处返回空（占位）
        return records


def _to_num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_str(value) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw in ("", "--", "null", "None"):
        return None
    return raw
