"""时间工具：统一秒级时间戳。"""

import time


def now_ts() -> float:
    return time.time()


def bucket_ts(ts: float, granularity: int) -> int:
    """时间对齐到桶起点。"""
    return int(ts) // granularity * granularity
