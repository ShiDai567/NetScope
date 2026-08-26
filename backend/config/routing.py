"""WebSocket 路由注册（供 config.asgi 引用）。"""

from network.routing import websocket_urlpatterns

__all__ = ["websocket_urlpatterns"]

websocket_urlpatterns = websocket_urlpatterns
