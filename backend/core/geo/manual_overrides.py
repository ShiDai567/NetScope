"""手工覆盖表：优先级最高的 Geo 来源（doc §7.1）。

- env `MANUAL_GEO_JSON`：JSON 字符串或 json 文件路径
- 运行期 register()：Mock 场景注入文档保留 IP 的固定坐标
"""

import json
from pathlib import Path

from core.geo.provider import GeoInfo, GeoProvider
from core.log import get_logger

log = get_logger("core.geo.overrides")


class ManualOverrides(GeoProvider):
    name = "manual"

    def __init__(self) -> None:
        self._entries: dict[str, GeoInfo] = {}

    def load_env(self, raw: str | None) -> None:
        """从 env 值加载：JSON 字符串或文件路径。"""
        raw = (raw or "").strip()
        if not raw:
            return
        data = None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            path = Path(raw)
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    data = None
        if not isinstance(data, dict):
            if raw:
                log.warning("manual_geo_overrides.invalid", raw=raw[:80])
            return
        self.register(data)

    def register(self, mapping: dict) -> None:
        """mapping: {ip: {country, code?, region?, city?, lat, lng}}"""
        for ip, info in mapping.items():
            if not isinstance(info, dict):
                continue
            lat, lng = info.get("lat"), info.get("lng")
            if lat is None or lng is None:
                continue
            self._entries[str(ip)] = GeoInfo(
                country=info.get("country") or "Unknown",
                code=info.get("code"),
                region=info.get("region") or "",
                city=info.get("city") or "",
                lat=float(lat),
                lng=float(lng),
                source="manual",
            )

    def lookup(self, ip: str) -> GeoInfo | None:
        return self._entries.get(ip)

    @property
    def size(self) -> int:
        return len(self._entries)
