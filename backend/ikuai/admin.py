"""
ikuai/admin.py
==============
iKuai 路由器集成模块的 Django Admin 配置。

在管理后台中注册 IKuaiSession 模型，便于运维人员查看登录历史、
排查连接故障或审计用户行为。
"""

from django.contrib import admin

from .models import IKuaiSession


@admin.register(IKuaiSession)
class IKuaiSessionAdmin(admin.ModelAdmin):
    """
    IKuaiSession 的后台管理配置。

    列表页展示字段：id、router_url、username、request_mode、result_code、created_at
    筛选器：按 request_mode（请求模式）、result_code（结果码）、created_at（时间）筛选
    搜索字段：支持按 router_url、username、sess_key 模糊搜索
    """
    list_display = ("id", "router_url", "username", "request_mode", "result_code", "created_at")
    list_filter = ("request_mode", "result_code", "created_at")
    search_fields = ("router_url", "username", "sess_key")
