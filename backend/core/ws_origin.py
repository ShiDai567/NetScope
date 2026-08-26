"""WebSocket Origin 校验（doc §13.2）。

与 channels.security.websocket.OriginValidator 的差异：
- 显式 Origin：必须命中 ALLOWED_HOSTS / CORS 白名单（含子域通配）
- 无 Origin（非浏览器客户端 / 内网工具）：默认放行，可用 WS_REQUIRE_ORIGIN=1 收紧
"""

from channels.security.websocket import OriginValidator
from django.conf import settings


def NetScopeOriginValidator(application):
    """工厂：无 Origin 放行 + 白名单校验。"""
    allowed = list(settings.ALLOWED_HOSTS) + list(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
    if settings.DEBUG:
        allowed += ["localhost", "127.0.0.1", "[::1]"]
    return _OptionalOriginValidator(application, allowed)


class _OptionalOriginValidator(OriginValidator):
    def valid_origin(self, parsed_origin) -> bool:
        if parsed_origin is None:
            return not getattr(settings, "WS_REQUIRE_ORIGIN", False)
        return super().valid_origin(parsed_origin)
