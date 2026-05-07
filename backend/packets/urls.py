"""
packets/urls.py
===============
packets 模块的路由配置。

将数据包相关的视图函数映射到 URL 路径上。
"""

from django.urls import path

from .views import packet_view

urlpatterns = [
    # 生成并返回模拟数据包事件
    path("packet", packet_view),
]
