"""IKuaiGateway：面向采集层的高层接口。

基于实测验证的字段：monitor_lanip（终端/连接）、monitor_system（系统负载）、
monitor_iface（接口实时速率 + WAN 快照 + 线路质量历史）。
"""

import socket

from core.log import get_logger
from core.utils.network import host_of, is_public_ip, valid_ip
from datasource.ikuai.funcs import (
    FUNC_IFACE,
    FUNC_SYSTEM,
    FUNC_TERMINAL_LIST,
    func_conn_details,
)
from datasource.ikuai.sdk_loader import GatewayError

log = get_logger("datasource.ikuai.gateway")


class IKuaiGateway:
    def __init__(self, session) -> None:
        self.session = session

    # ------------------------------------------------------------ 采集接口

    def get_terminals(self) -> list[dict]:
        data = self.session.call(dict(FUNC_TERMINAL_LIST))
        rows = data.get("data")
        return rows if isinstance(rows, list) else []

    def get_connections(self, ip: str) -> list[dict]:
        data = self.session.call(func_conn_details(ip))
        rows = data.get("conn")
        return rows if isinstance(rows, list) else []

    def get_system_info(self) -> dict:
        """monitor_system：Data["data"] 列表最后一条为最新样本。"""
        data = self.session.call(dict(FUNC_SYSTEM))
        rows = data.get("data") if isinstance(data, dict) else None
        if isinstance(rows, list) and rows:
            last = rows[-1]
            return last if isinstance(last, dict) else {}
        return {}

    def get_iface_info(self) -> dict:
        """monitor_iface 原始响应（带宽/WAN/线路质量解析交给 iface 模块）。"""
        data = self.session.call(dict(FUNC_IFACE))
        return data if isinstance(data, dict) else {}

    def get_wan_ip(self) -> str | None:
        """公网出口 IP：snapshoot_wan 优先，其次解析面板域名（面板经端口映射暴露）。"""
        try:
            data = self.get_iface_info()
        except GatewayError:
            data = {}
        wan_ip = parse_wan_ip(data)
        if wan_ip:
            return wan_ip
        host = host_of(self.session.router_url)
        if host and not valid_ip(host):
            try:
                infos = socket.getaddrinfo(host, None, socket.AF_INET)
                for info in infos:
                    candidate = info[4][0]
                    if is_public_ip(candidate):
                        return candidate
            except OSError:
                return None
        elif host and is_public_ip(host):
            return host
        return None


def parse_lan_ip(iface_data: dict) -> str | None:
    """从 snapshoot_lan 提取路由器自身 LAN IP（网关识别用）。"""
    for row in iface_data.get("snapshoot_lan") or []:
        if not isinstance(row, dict):
            continue
        ip = valid_ip(row.get("ip_addr"))
        if ip:
            return ip
    return None


def parse_wan_ip(iface_data: dict) -> str | None:
    for row in iface_data.get("snapshoot_wan") or []:
        if not isinstance(row, dict):
            continue
        if row.get("internet") in (1, "1", True):
            ip = row.get("ip_addr")
            if is_public_ip(ip):
                return valid_ip(ip)
    return None


def parse_iface_info(iface_data: dict) -> dict:
    """iface 响应 → 权威带宽 / WAN IP / 线路质量（rtt/丢包率）。

    实测结构：
      iface_stream:      [{interface, upload(B/s), download(B/s), ...}]
      snapshoot_wan:     [{interface, ip_addr, internet, ...}]
      wans_stat_history: [{avg_rtt, drop_rate, ...}] 最后一条最新
    """
    wan_names = {
        row.get("interface")
        for row in iface_data.get("snapshoot_wan") or []
        if isinstance(row, dict) and row.get("internet") in (1, "1", True)
    }
    up = 0.0
    down = 0.0
    for row in iface_data.get("iface_stream") or []:
        if not isinstance(row, dict) or row.get("interface") not in wan_names:
            continue
        up += _num(row.get("upload"))
        down += _num(row.get("download"))

    avg_rtt = 0.0
    loss_rate = 0.0
    history = iface_data.get("wans_stat_history") or []
    if history and isinstance(history[-1], dict):
        avg_rtt = _num(history[-1].get("avg_rtt"))
        loss_rate = _num(history[-1].get("drop_rate"))

    return {
        "up_bps": up,
        "down_bps": down,
        "wan_ip": parse_wan_ip(iface_data),
        "avg_rtt_ms": avg_rtt,
        "loss_rate": loss_rate,
    }


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
