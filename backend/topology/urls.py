"""
topology/urls.py
================
topology 模块的路由配置。

将节点和路由相关的视图函数映射到 URL 路径上。
"""

from django.urls import path

from .views import nodes_view, routes_view

urlpatterns = [
    # 获取所有活跃网络节点列表
    path("nodes", nodes_view),
    # 获取所有活跃网络路由列表
    path("routes", routes_view),
]
