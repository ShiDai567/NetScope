"""方向快照：从连接状态重建 Resolved（packet 组装需要）。"""

from network.adapters.direction import Resolved


def _resolved_from_state(state, kind: str) -> Resolved:
    """连接状态 → Resolved 视图（inbound 已交换端点语义）。"""
    if state.direction == "inbound":
        return Resolved(
            direction="inbound",
            local_ip=state.dst_ip,
            local_port=state.dst_port,
            remote_ip=state.src_ip,
            remote_port=state.src_port,
            nat_forward_addr=state.dst_ip,
            original_dst=None,
            reason="state-inbound",
        )
    return Resolved(
        direction=state.direction,
        local_ip=state.src_ip,
        local_port=state.src_port,
        remote_ip=state.dst_ip,
        remote_port=state.dst_port,
        nat_forward_addr=None,
        original_dst=None,
        reason="state",
    )
