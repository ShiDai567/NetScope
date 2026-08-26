"""方向判定规则（doc §6，系统正确性核心）。

纯函数、确定性输入输出；tests/test_direction.py 黄金用例全量覆盖。
判定结果即权威：前端、统计、聚合全部信任该值，不得重复猜测。
"""

from dataclasses import dataclass

from core.utils.network import (
    is_private_ip,
    valid_ip,
    valid_port,
)


@dataclass(frozen=True)
class Resolved:
    direction: str  # outbound | inbound | internal | external | invalid
    local_ip: str | None
    local_port: int
    remote_ip: str
    remote_port: int
    nat_forward_addr: str | None
    original_dst: str | None
    reason: str


def resolve_direction(
    row: dict,
    terminal_ip: str | None,
    wan_ip: str | None = None,
    listen_ports: frozenset[int] | set[int] = frozenset(),
) -> Resolved | None:
    """iKuai conn 行 → Resolved。返回 None 表示完全无法解析（D5 丢弃）。

    语义约定（doc §20.1）：
      dst_addr  = 远端地址（无论谁发起）
      src_port  = 本地端口
      dst_port  = 远端端口
      forward_addr = NAT 后本地出口（私有则视为本地端）
    """
    remote_ip = valid_ip(row.get("dst_addr"))
    if remote_ip is None:
        return None

    local_port = valid_port(row.get("src_port"), default=-1)
    remote_port = valid_port(row.get("dst_port"), default=-1)
    if local_port < 0 or remote_port < 0:
        return None

    forward_addr = valid_ip(row.get("forward_addr"))
    terminal = valid_ip(terminal_ip)
    local_ip = forward_addr if (forward_addr and is_private_ip(forward_addr)) else terminal
    if local_ip is None:
        return None

    local_private = is_private_ip(local_ip)
    remote_private = is_private_ip(remote_ip)

    # D1 内网 → 内网
    if local_private and remote_private:
        return Resolved(
            direction="internal",
            local_ip=local_ip,
            local_port=local_port,
            remote_ip=remote_ip,
            remote_port=remote_port,
            nat_forward_addr=forward_addr,
            original_dst=None,
            reason="D1",
        )

    # D2/D3 内网 → 公网：src_port 命中 LISTEN_PORTS 则为端口映射入站
    if local_private and not remote_private:
        if local_port in listen_ports:
            original_dst = f"{wan_ip}:{local_port}" if wan_ip else None
            return Resolved(
                direction="inbound",
                local_ip=local_ip,
                local_port=local_port,
                remote_ip=remote_ip,
                remote_port=remote_port,
                nat_forward_addr=forward_addr,
                original_dst=original_dst,
                reason="D3",
            )
        return Resolved(
            direction="outbound",
            local_ip=local_ip,
            local_port=local_port,
            remote_ip=remote_ip,
            remote_port=remote_port,
            nat_forward_addr=forward_addr,
            original_dst=None,
            reason="D2",
        )

    # D4 公网 ↔ 公网（透传/异常）：不产生地图事件
    if not local_private and not remote_private:
        return Resolved(
            direction="external",
            local_ip=local_ip,
            local_port=local_port,
            remote_ip=remote_ip,
            remote_port=remote_port,
            nat_forward_addr=forward_addr,
            original_dst=None,
            reason="D4",
        )

    # 本地公网 → 远端私有（罕见回流）：按 internal 归类便于 LAN 呈现
    return Resolved(
        direction="internal",
        local_ip=local_ip,
        local_port=local_port,
        remote_ip=remote_ip,
        remote_port=remote_port,
        nat_forward_addr=forward_addr,
        original_dst=None,
        reason="local-public-remote-private",
    )
