"""
packets/admin.py
================
数据包模块的 Django Admin 配置。

在管理后台中注册 PacketEvent 模型，便于运维人员查看历史数据包事件、
排查异常传输记录或进行数据分析。
"""

from django.contrib import admin

from .models import PacketEvent


@admin.register(PacketEvent)
class PacketEventAdmin(admin.ModelAdmin):
    """
    PacketEvent 的后台管理配置。

    列表页展示字段：packet_id、protocol、status、payload_size、event_timestamp
    筛选器：按 protocol（协议类型）和 status（传输状态）筛选
    搜索字段：支持按 packet_id 精确或模糊搜索
    """
    list_display = ("packet_id", "protocol", "status", "payload_size", "event_timestamp")
    list_filter = ("protocol", "status")
    search_fields = ("packet_id",)
