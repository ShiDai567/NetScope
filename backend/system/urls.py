"""
system/urls.py
==============
system 模块的路由配置。

将视图函数映射到 URL 路径上，供 config/urls.py 统一 include。
"""

from django.urls import path

from .views import health_view

# urlpatterns 是 Django 路由解析器查找的默认变量名。
# 这里将 /api/health 请求映射到 health_view 视图函数。
urlpatterns = [
    path("health", health_view),
]
