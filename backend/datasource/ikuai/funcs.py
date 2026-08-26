"""iKuai /Action/call 常量表（doc §5.1.1）。

不同固件版本字段可能有差异，全部集中在 funcs 便于联调时调整。
"""

FUNC_TERMINAL_LIST = {
    "func_name": "monitor_lanip",
    "action": "show",
    "param": {
        "TYPE": "data,total",
        "ORDER_BY": "ip_addr_int",
        "orderType": "IP",
        "limit": "0,200",
        "ORDER": "",
    },
}


def func_conn_details(ip: str, maxnum: int = 500) -> dict:
    """单终端连接详询（与 sdk 默认 payload 保持一致，实测可用）。"""
    return {
        "func_name": "monitor_lanip",
        "action": "show",
        "param": {
            "TYPE": "conn,conn_num",
            "ip": ip,
            "interface": "all",
            "proto": "all",
            "maxnum": maxnum,
            "limit": "0,100",
            "ORDER_BY": "",
            "ORDER": "",
        },
    }


FUNC_SYSTEM = {
    "func_name": "monitor_system",
    "action": "show",
    "param": {},
}

FUNC_IFACE = {
    "func_name": "monitor_iface",
    "action": "show",
    "param": {"TYPE": "all"},
}

FUNC_WAN = {
    "func_name": "monitor_wan",
    "action": "show",
    "param": {"TYPE": "total,data", "limit": "0,20", "ORDER_BY": "", "ORDER": ""},
}

IKUAI_OK = 10000
IKUAI_AUTH_FAIL = 10001
