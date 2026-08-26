"""monitor_system 响应 → CPU / 内存百分比（容错提取，doc §5.1.1 脚注）。"""

import re

_KEY_RE = re.compile(r"cpu|mem", re.IGNORECASE)


def extract_system_metrics(raw: dict) -> tuple[float | None, float | None]:
    """递归扫描 key 含 cpu/mem 的数值（0~100 视为百分比）。"""
    found: dict[str, float] = {}

    def _walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_l = str(key).lower()
                pct = _as_percent(value)
                if pct is not None:
                    if "cpu" in key_l and "cpu" not in found:
                        found["cpu"] = pct
                    elif "mem" in key_l and "mem" not in found:
                        found["mem"] = pct
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    def _as_percent(value) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            num = float(value)
        else:
            try:
                num = float(str(value).strip().rstrip("%"))
            except (TypeError, ValueError):
                return None
        if 0 <= num <= 100:
            return round(num, 1)
        return None

    if not isinstance(raw, dict):
        return None, None
    _walk(raw)
    return found.get("cpu"), found.get("mem")
