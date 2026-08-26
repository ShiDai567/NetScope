"""RedisStore：全部实时 key 的唯一读写入口（doc §8）。

key 清单、TTL、环形缓冲淘汰都集中在此，其他模块禁止自行拼 key。
同步客户端：web 直接调用；异步上下文（collector/consumer）用 asyncio.to_thread 包装。
"""

import json
import threading

from core.log import get_logger
from core.utils.timeutil import now_ts

log = get_logger("core.redis_store")

PACKET_BODY_TTL = 900
CONN_TTL = 120
BW_MAX_POINTS = 3700
STATS_TTL = 10
HB_TTL = 60


class Keys:
    SEQ = "net:seq"
    PACKETS = "net:packets"
    TOTALS = "net:totals"
    CONN_INDEX = "net:conn:index"
    BW_1S = "net:bw:1s"
    DEVICES = "net:devices"
    NODES = "net:nodes"
    GATEWAY = "net:gateway"
    MODE = "net:mode"
    IKUAI_HEALTH = "net:ikuai:health"
    SYS_METRICS = "net:sys:metrics"
    HB = "net:collector:hb"

    @staticmethod
    def packet(pid: str) -> str:
        return f"net:packet:{pid}"

    @staticmethod
    def conn(key: str) -> str:
        return f"net:conn:{key}"

    @staticmethod
    def cnt(granularity: int, dim: str, bucket: int) -> str:
        return f"net:cnt:{granularity}:{dim}:{bucket}"

    @staticmethod
    def stats(window: int) -> str:
        return f"net:stats:{window}"

    @staticmethod
    def geo(ip: str) -> str:
        return f"net:geo:{ip}"

    @staticmethod
    def drop_counters(dim: str, kind: str) -> str:
        return f"net:drop:{dim}:{kind}"


_GRAN_TTL = {5: 7200, 60: 3840}


class RedisStore:
    def __init__(self, url: str | None = None, client=None) -> None:
        if client is not None:
            self.r = client
        else:
            import redis

            self.r = redis.Redis.from_url(
                url or "redis://127.0.0.1:6379/0",
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
        self._local = threading.local()

    # ------------------------------------------------------------ 基础

    def ping(self) -> bool:
        try:
            return bool(self.r.ping())
        except Exception:
            return False

    # ------------------------------------------------------------ seq / 事件

    def next_seq(self) -> int:
        return int(self.r.incr(Keys.SEQ))

    def last_seq(self) -> int:
        value = self.r.get(Keys.SEQ)
        return int(value or 0)

    def publish_packets(self, packets: list[dict], buffer_max: int = 10000) -> None:
        """批量写事件：zset(按 seq 排序) + body(TTL)，然后裁剪环形缓冲。"""
        if not packets:
            return
        pipe = self.r.pipeline(transaction=False)
        for pkt in packets:
            pid = pkt["id"]
            pipe.set(Keys.packet(pid), json.dumps(pkt, ensure_ascii=False), ex=PACKET_BODY_TTL)
            pipe.zadd(Keys.PACKETS, {pid: pkt["seq"]})
        pipe.zremrangebyrank(Keys.PACKETS, 0, -(buffer_max + 1))
        pipe.execute()

    def read_packets(self, since: int | None, limit: int = 500) -> tuple[list[dict], int]:
        """读取 (since, +inf) 升序事件；返回 (events, last_seq)。"""
        last = self.last_seq()
        if since is not None:
            try:
                since = int(since)
            except (TypeError, ValueError):
                since = None
        if since is None or since < 0:
            minimum = "-inf"
        else:
            minimum = f"({since}"
        ids = self.r.zrangebyscore(Keys.PACKETS, minimum, "+inf", start=0, num=max(1, limit))
        if ids:
            try:
                top = self.r.zscore(Keys.PACKETS, ids[-1])
                if top is not None:
                    last = max(last, int(top))
            except Exception:
                pass
        if not ids:
            return [], last
        blobs = self.r.mget([Keys.packet(pid) for pid in ids])
        events = []
        for blob in blobs:
            if not blob:
                continue
            try:
                events.append(json.loads(blob))
            except json.JSONDecodeError:
                continue
        return events, last

    def clear_packets(self) -> int:
        """清空事件环形缓冲（核心位置变更时旧坐标事件全部作废）。

        注意：net:seq 保持单调递增不清零，否则前端 since 游标会漏事件。
        """
        ids = self.r.zrange(Keys.PACKETS, 0, -1)
        pipe = self.r.pipeline(transaction=False)
        if ids:
            for pid in ids:
                pipe.delete(Keys.packet(pid))
        pipe.delete(Keys.PACKETS)
        pipe.execute()
        return len(ids)

    # ------------------------------------------------------------ 维度计数

    def flush_counter_ops(self, ops: list[tuple[str, int, int, str, int, int]]) -> None:
        """ops: [(dim, granularity, bucket, field, count_delta, bytes_delta)]"""
        if not ops:
            return
        grouped: dict[tuple[int, str, int], list[tuple[str, int, int]]] = {}
        for dim, gran, bucket, field, n, b in ops:
            grouped.setdefault((gran, dim, bucket), []).append((field, n, b))
        pipe = self.r.pipeline(transaction=False)
        for (gran, dim, bucket), fields in grouped.items():
            key = Keys.cnt(gran, dim, bucket)
            for field, n, b in fields:
                pipe.hincrby(key, f"{field}:n", n)
                pipe.hincrby(key, f"{field}:b", b)
            pipe.expire(key, _GRAN_TTL.get(gran, 3840))
        pipe.execute()

    def read_dim_window(self, dim: str, window: int, now: float | None = None) -> dict[str, list[int]]:
        """合并窗口内所有 bucket，返回 {field: [count, bytes]}。"""
        now = now or now_ts()
        gran = 5 if window <= 30 else 60
        buckets = (window // gran) + 2
        start_bucket = (int(now) // gran - buckets + 1) * gran
        keys = [Keys.cnt(gran, dim, start_bucket + i * gran) for i in range(buckets)]
        merged: dict[str, list[int]] = {}
        try:
            results = self.r.mget(keys)
        except Exception:
            return merged
        import json as _json

        for blob in results:
            if not blob:
                continue
            try:
                data = _json.loads(blob)
            except (_json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            for field, value in data.items():
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    continue
                merged.setdefault(field, [0, 0])
                merged[field][0] += v
        return merged

    # raw hash 版（真实 redis 用 hgetall）
    def read_dim_window_hashes(self, dim: str, window: int, now: float | None = None) -> dict[str, list[int]]:
        now = now or now_ts()
        gran = 5 if window <= 30 else 60
        buckets = (window // gran) + 2
        start_bucket = (int(now) // gran - buckets + 1) * gran
        keys = [Keys.cnt(gran, dim, start_bucket + i * gran) for i in range(buckets)]
        merged: dict[str, list[int]] = {}
        try:
            pipe = self.r.pipeline(transaction=False)
            for key in keys:
                pipe.hgetall(key)
            for data in pipe.execute():
                for field, value in data.items():
                    try:
                        v = int(value)
                    except (TypeError, ValueError):
                        continue
                    name = field[:-2] if field.endswith((":n", ":b")) else field
                    merged.setdefault(name, [0, 0])
                    if field.endswith(":n"):
                        merged[name][0] += v
                    elif field.endswith(":b"):
                        merged[name][1] += v
        except Exception:
            pass
        return merged

    # ------------------------------------------------------------ totals

    def incr_totals(self, **deltas: int) -> None:
        if not deltas:
            return
        pipe = self.r.pipeline(transaction=False)
        for field, delta in deltas.items():
            if delta:
                pipe.hincrby(Keys.TOTALS, field, delta)
        pipe.execute()

    def get_totals(self) -> dict[str, int]:
        raw = self.r.hgetall(Keys.TOTALS)
        out = {}
        for field, value in raw.items():
            try:
                out[field] = int(value)
            except (TypeError, ValueError):
                continue
        return out

    # ------------------------------------------------------------ 活跃连接

    def upsert_conn(self, key: str, mapping: dict, ts: float) -> None:
        pipe = self.r.pipeline(transaction=False)
        pipe.hset(Keys.conn(key), mapping=mapping)
        pipe.expire(Keys.conn(key), CONN_TTL)
        pipe.zadd(Keys.CONN_INDEX, {key: ts})
        pipe.execute()

    def drop_conns(self, keys: list[str]) -> None:
        if not keys:
            return
        pipe = self.r.pipeline(transaction=False)
        for key in keys:
            pipe.delete(Keys.conn(key))
            pipe.zrem(Keys.CONN_INDEX, key)
        pipe.execute()

    def count_conns(self) -> int:
        return int(self.r.zcard(Keys.CONN_INDEX))

    def conn_keys_before(self, ts: float) -> list[str]:
        return self.r.zrangebyscore(Keys.CONN_INDEX, "-inf", f"({ts}")

    def get_conn(self, key: str) -> dict | None:
        data = self.r.hgetall(Keys.conn(key))
        return data or None

    def list_conns(self, limit: int = 500) -> list[dict]:
        keys = self.r.zrange(Keys.CONN_INDEX, 0, max(1, limit) - 1)
        out = []
        for key in keys:
            data = self.r.hgetall(Keys.conn(key))
            if data:
                out.append(data)
        return out

    def touch_conns(self, keys: list[str], ts: float) -> None:
        if not keys:
            return
        mapping = {key: ts for key in keys}
        self.r.zadd(Keys.CONN_INDEX, mapping=mapping)

    # ------------------------------------------------------------ 带宽序列

    def push_bw(self, t: float, up_bps: float, down_bps: float) -> None:
        pipe = self.r.pipeline(transaction=False)
        pipe.lpush(Keys.BW_1S, json.dumps([t, up_bps, down_bps]))
        pipe.ltrim(Keys.BW_1S, 0, BW_MAX_POINTS - 1)
        pipe.execute()

    def read_bw(self, n: int = 60) -> list[list[float]]:
        raw = self.r.lrange(Keys.BW_1S, 0, max(1, n) - 1)
        points = []
        for blob in raw:
            try:
                points.append(json.loads(blob))
            except json.JSONDecodeError:
                continue
        return points

    # ------------------------------------------------------------ 统计快照

    def set_stats(self, window: int, snapshot: dict) -> None:
        self.r.set(Keys.stats(window), json.dumps(snapshot, ensure_ascii=False), ex=STATS_TTL)

    def get_stats(self, window: int) -> dict | None:
        blob = self.r.get(Keys.stats(window))
        if not blob:
            return None
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            return None

    # ------------------------------------------------------------ 设备/节点

    def put_devices(self, devices: list[dict]) -> None:
        pipe = self.r.pipeline(transaction=False)
        pipe.delete(Keys.DEVICES)
        for dev in devices:
            pipe.hset(Keys.DEVICES, dev["ip"], json.dumps(dev, ensure_ascii=False))
        pipe.execute()

    def get_devices(self) -> list[dict]:
        raw = self.r.hgetall(Keys.DEVICES)
        devices = []
        for blob in raw.values():
            try:
                devices.append(json.loads(blob))
            except json.JSONDecodeError:
                continue
        return devices

    def put_nodes(self, nodes: list[dict]) -> None:
        pipe = self.r.pipeline(transaction=False)
        pipe.delete(Keys.NODES)
        for node in nodes:
            pipe.hset(Keys.NODES, node["ip"], json.dumps(node, ensure_ascii=False))
        pipe.execute()

    def get_nodes(self) -> list[dict]:
        raw = self.r.hgetall(Keys.NODES)
        nodes = []
        for blob in raw.values():
            try:
                nodes.append(json.loads(blob))
            except json.JSONDecodeError:
                continue
        return nodes

    # ------------------------------------------------------------ 状态/健康

    def set_mode(self, mode: str, started_at: float | None = None) -> dict:
        if started_at is None:
            started_at = now_ts()
        mapping = {"mode": mode, "started_at": started_at}
        self.r.hset(Keys.MODE, mapping=mapping)
        return mapping

    def get_mode(self) -> dict:
        raw = self.r.hgetall(Keys.MODE)
        if not raw:
            return {"mode": "unknown", "started_at": now_ts(), "geo_epoch": 0}
        try:
            raw["started_at"] = float(raw.get("started_at") or now_ts())
        except (TypeError, ValueError):
            raw["started_at"] = now_ts()
        try:
            raw["geo_epoch"] = int(raw.get("geo_epoch") or 0)
        except (TypeError, ValueError):
            raw["geo_epoch"] = 0
        return raw

    def bump_geo_epoch(self) -> int:
        """核心位置变更：纪元 +1，前端据此清空本地流缓存。"""
        return int(self.r.hincrby(Keys.MODE, "geo_epoch", 1))

    def set_gateway(self, lat: float | None, lng: float | None, wan_ip: str | None = None) -> None:
        mapping = {
            "lat": "" if lat is None else float(lat),
            "lng": "" if lng is None else float(lng),
            "wan_ip": wan_ip or "",
            "updated_at": now_ts(),
        }
        self.r.hset(Keys.GATEWAY, mapping=mapping)

    def get_gateway(self) -> dict:
        raw = self.r.hgetall(Keys.GATEWAY)
        out = {"lat": None, "lng": None, "wan_ip": None}
        try:
            out["lat"] = float(raw.get("lat")) if raw.get("lat") not in (None, "") else None
        except (TypeError, ValueError):
            pass
        try:
            out["lng"] = float(raw.get("lng")) if raw.get("lng") not in (None, "") else None
        except (TypeError, ValueError):
            pass
        wan = raw.get("wan_ip")
        out["wan_ip"] = wan or None
        return out

    def set_ikuai_health(self, **kv) -> None:
        clean = {k: v for k, v in kv.items() if v is not None}
        if clean:
            self.r.hset(Keys.IKUAI_HEALTH, mapping=clean)

    def get_ikuai_health(self) -> dict:
        raw = self.r.hgetall(Keys.IKUAI_HEALTH)
        out = {
            "router_url": raw.get("router_url"),
            "error": None,
            "last_poll_at": None,
            "connected_at": None,
        }
        if raw.get("error"):
            out["error"] = raw["error"]
        for field in ("last_poll_at", "connected_at"):
            try:
                if raw.get(field):
                    out[field] = float(raw[field])
            except (TypeError, ValueError):
                continue
        return out

    def set_sys_metrics(self, cpu_percent: float | None, memory_percent: float | None) -> None:
        mapping = {
            "cpu_percent": "" if cpu_percent is None else cpu_percent,
            "memory_percent": "" if memory_percent is None else memory_percent,
        }
        self.r.hset(Keys.SYS_METRICS, mapping=mapping)

    def set_sys_metrics_extra(self, conn_num: int) -> None:
        self.r.hset(Keys.SYS_METRICS, "conn_num", int(conn_num))

    def set_line_quality(self, avg_rtt_ms: float, loss_rate: float) -> None:
        self.r.hset(
            Keys.SYS_METRICS,
            mapping={"avg_rtt_ms": round(float(avg_rtt_ms), 2), "loss_rate": round(float(loss_rate), 4)},
        )

    def get_sys_metrics(self) -> dict:
        raw = self.r.hgetall(Keys.SYS_METRICS)
        out = {"cpu_percent": None, "memory_percent": None}
        for field in out:
            try:
                if raw.get(field) not in (None, ""):
                    out[field] = float(raw[field])
            except (TypeError, ValueError):
                continue
        return out

    def heartbeat(self) -> None:
        self.r.set(Keys.HB, now_ts(), ex=HB_TTL)

    def collector_age(self) -> float | None:
        value = self.r.get(Keys.HB)
        if not value:
            return None
        try:
            return max(0.0, now_ts() - float(value))
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------ Geo 缓存

    def geo_get(self, ip: str) -> dict | None:
        raw = self.r.hgetall(Keys.geo(ip))
        return raw or None

    def geo_set(self, ip: str, info: dict, ttl: int) -> None:
        pipe = self.r.pipeline(transaction=False)
        pipe.hset(Keys.geo(ip), mapping=info)
        pipe.expire(Keys.geo(ip), ttl)
        pipe.execute()

    def incr_drop(self, dim: str, kind: str) -> None:
        try:
            self.r.hincrby(
                Keys.drop_counters(dim, kind),
                1,
            )
        except Exception:
            pass


_store: RedisStore | None = None


def get_store() -> RedisStore:
    global _store
    if _store is None:
        from django.conf import settings

        _store = RedisStore(url=settings.REDIS_URL)
    return _store


def set_store(store: RedisStore) -> None:
    """测试/特殊部署注入自定义实例。"""
    global _store
    _store = store
