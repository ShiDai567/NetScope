"""
topology/admin.py
=================
网络拓扑模块的 Django Admin 配置。

在 Django 管理后台中注册 NetworkNode 和 NetworkRoute 模型，
并提供列表展示、筛选、搜索等功能，方便运维人员查看和手动维护拓扑数据。
"""

from django.contrib import admin

from .models import NetworkNode, NetworkRoute


@admin.register(NetworkNode)
class NetworkNodeAdmin(admin.ModelAdmin):
    """
    NetworkNode 的后台管理配置。

    列表页展示字段：node_id、name、ip_address、node_type、is_active
    筛选器：按 node_type（服务器/客户端）和 is_active（是否启用）筛选
    搜索字段：支持按 node_id、name、ip_address 模糊搜索
    """
    list_display = ("node_id", "name", "ip_address", "node_type", "is_active")
    list_filter = ("node_type", "is_active")
    search_fields = ("node_id", "name", "ip_address")


@admin.register(NetworkRoute)
class NetworkRouteAdmin(admin.ModelAdmin):
    """
    NetworkRoute 的后台管理配置。

    列表页展示字段：id、source_node、destination_node、is_active
    筛选器：按 is_active 筛选
    """
    list_display = ("id", "source_node", "destination_node", "is_active")
    list_filter = ("is_active",)
