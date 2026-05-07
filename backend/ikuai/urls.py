"""
ikuai/urls.py
=============
ikuai 模块的路由配置。

将 iKuai 登录和会话查询相关的视图函数映射到 URL 路径上。
"""

from django.urls import path

from .views import ikuai_login_view, ikuai_sessions_view

urlpatterns = [
    # iKuai 路由器登录接口
    path("ikuai/login", ikuai_login_view),
    # iKuai 登录会话历史列表接口
    path("ikuai/sessions", ikuai_sessions_view),
]
