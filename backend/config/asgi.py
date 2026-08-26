"""ASGI 入口：HTTP 走 Django，WebSocket 走 Channels 路由。"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

import config.routing  # noqa: E402
from core.ws_origin import NetScopeOriginValidator  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": NetScopeOriginValidator(
            AuthMiddlewareStack(URLRouter(config.routing.websocket_urlpatterns))
        ),
    }
)
