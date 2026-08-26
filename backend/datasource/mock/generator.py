"""MockSource：字段级模拟 iKuai monitor_lanip 行结构（doc §12）。

输出行与真实 SDK 完全同构（protocol/status/dst_addr/src_port/dst_port/
forward_addr/app_name/interface/total_up/total_down/domain），
并按剧本权重注入脏数据（"--"/空串/非法 IP），持续验证前端容错。
"""

import random

from core.utils.timeutil import now_ts
from datasource.mock.scenarios import (
    _STATUS_CYCLE,
    MOCK_TERMINALS,
    MOCK_WAN_IP,
    PEER_POOL,
    SCENARIO_SPAWN_WEIGHTS,
)


class _MockConn:
    __slots__ = (
        "terminal_ip",
        "peer",
        "kind",
        "src_port",
        "total_up",
        "total_down",
        "status",
        "born",
        "age",
        "dirty",
    )

    def __init__(self, terminal_ip: str, peer: dict, kind: str, rng: random.Random) -> None:
        self.terminal_ip = terminal_ip
        self.peer = peer
        self.kind = kind
        self.src_port = rng.randint(30000, 62000)
        self.total_up = rng.randint(40, 400)
        self.total_down = rng.randint(0, 2000)
        self.status = "请求连接"
        self.born = now_ts()
        self.age = 0
        self.dirty = rng.random() < 0.08


class MockSource:
    """与 IKuaiGateway 同构的数据源接口：terminals/connections/system/wan_ip。"""

    def __init__(self, scenario: str = "mixed", seed: int | None = None) -> None:
        self.scenario = scenario if scenario in SCENARIO_SPAWN_WEIGHTS else "mixed"
        self._rng = random.Random(seed)
        self._conns: dict[str, _MockConn] = {}
        self._totals = {t["ip"]: {"up": 0, "down": 0} for t in MOCK_TERMINALS}
        self._spawn_budget = 4
        self._sys = {"cpu": 18.0, "mem": 52.0}

    # ------------------------------------------------------------ 数据源接口

    def get_terminals(self) -> list[dict]:
        rows = []
        for term in MOCK_TERMINALS:
            stats = self._totals[term["ip"]]
            conn_num = sum(1 for c in self._conns.values() if c.terminal_ip == term["ip"])
            rows.append(
                {
                    "ip_addr": term["ip"],
                    "ip_addr_int": 0,
                    "mac": term["mac"],
                    "comment": term["comment"],
                    "interface": term["interface"],
                    "connect_num": conn_num,
                    "upload": stats["up"],
                    "download": stats["down"],
                    "total_up": stats["up"],
                    "total_down": stats["down"],
                    "client_type": "mock",
                    "ppptype": "",
                    "signal": 0,
                    "webid": 0,
                }
            )
        return rows

    def get_connections(self, ip: str) -> list[dict]:
        self._age_and_close(ip)
        for _ in range(self._spawn_budget):
            self._spawn(ip)
        rows = []
        for conn in list(self._conns.values()):
            if conn.terminal_ip != ip:
                continue
            conn.total_up += self._rng.randint(0, 900)
            conn.total_down += self._rng.randint(0, 6000)
            if self._rng.random() < 0.25:
                conn.status = self._rng.choice(_STATUS_CYCLE)
            rows.append(self._row(conn))
            self._totals[ip]["up"] = conn.total_up
            self._totals[ip]["down"] = conn.total_down
        return rows

    def get_system_info(self) -> dict:
        self._sys["cpu"] = min(95.0, max(5.0, self._sys["cpu"] + self._rng.uniform(-6, 6)))
        self._sys["mem"] = min(95.0, max(20.0, self._sys["mem"] + self._rng.uniform(-3, 3)))
        return {"cpuStatus": round(self._sys["cpu"], 1), "memStatus": round(self._sys["mem"], 1)}

    def get_wan_ip(self) -> str | None:
        return MOCK_WAN_IP

    # ------------------------------------------------------------ 内部

    def _spawn(self, terminal_ip: str) -> None:
        weights = SCENARIO_SPAWN_WEIGHTS[self.scenario]
        roll = self._rng.random()
        if roll < weights["outbound"]:
            kind = "outbound"
        elif roll < weights["outbound"] + weights["inbound"]:
            kind = "inbound"
        elif roll < weights["outbound"] + weights["inbound"] + weights["internal"]:
            kind = "internal"
        else:
            kind = "dirty"

        key = f"{terminal_ip}:{self._rng.randint(1, 10**9)}"
        peer = self._rng.choice(PEER_POOL)

        if kind == "internal":
            target = self._rng.choice([t["ip"] for t in MOCK_TERMINALS])
            conn = _MockConn(
                terminal_ip,
                {
                    "ip": target,
                    "port": self._rng.choice([53, 80, 445, 8080]),
                    "proto": "tcp",
                    "app": "内网服务",
                    "domain": "--",
                },
                kind,
                self._rng,
            )
        else:
            conn = _MockConn(terminal_ip, peer, kind, self._rng)
            if kind == "inbound":
                conn.src_port = self._rng.choice([22, 80, 443, 445, 8080])
                conn.status = "已连接"
        if kind == "dirty":
            conn.dirty = True
        self._conns[key] = conn

    def _age_and_close(self, terminal_ip: str) -> None:
        for key in list(self._conns):
            conn = self._conns[key]
            if conn.terminal_ip != terminal_ip:
                continue
            conn.age += 1
            if conn.age > 40 or (conn.status == "关闭连接" and conn.age > 4):
                if self._rng.random() < 0.5:
                    del self._conns[key]

    def _row(self, conn: _MockConn) -> dict:
        terminal_ip = conn.terminal_ip
        if conn.kind == "internal":
            dst = conn.peer["ip"]
            forward = terminal_ip
            src_port = self._rng.randint(30000, 62000)
            dst_port = conn.peer["port"]
        elif conn.kind == "inbound":
            dst = conn.peer["ip"]
            forward = terminal_ip
            src_port = conn.src_port
            dst_port = self._rng.randint(30000, 62000)
        else:
            dst = conn.peer["ip"]
            forward = "192.168.2.100" if self._rng.random() < 0.5 else terminal_ip
            src_port = conn.src_port
            dst_port = conn.peer["port"]

        row = {
            "protocol": conn.peer["proto"],
            "status": conn.status,
            "dst_addr": dst,
            "src_port": src_port,
            "dst_port": dst_port,
            "forward_addr": forward,
            "app_name": conn.peer["app"],
            "interface": "wan1" if conn.kind != "internal" else "lan1",
            "total_up": conn.total_up,
            "total_down": conn.total_down,
            "domain": conn.peer.get("domain") or "--",
        }
        if conn.dirty:
            row = self._mutate_dirty(row)
        return row

    def _mutate_dirty(self, row: dict) -> dict:
        """注入 §61 的各种脏值，持续验证前后端容错。"""
        choice = self._rng.choice(("domain", "status", "ip", "port", "app"))
        if choice == "domain":
            row["domain"] = self._rng.choice(["--", "", None])
        elif choice == "status":
            row["status"] = self._rng.choice(["--", "", None])
        elif choice == "ip":
            row["dst_addr"] = self._rng.choice(["not-an-ip", "", None, "999.1.1.1"])
        elif choice == "port":
            row["dst_port"] = self._rng.choice(["-1", "abc", None])
        elif choice == "app":
            row["app_name"] = self._rng.choice(["", None, "  "])
        return row
