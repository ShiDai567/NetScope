"""WebSocket 路由。"""

from django.urls import path

from network.consumers import NetworkConsumer

websocket_urlpatterns = [
    path("ws/network/", NetworkConsumer.as_asgi()),
]
