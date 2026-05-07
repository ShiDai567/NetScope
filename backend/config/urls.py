"""
config/urls.py
==============
NetScope 后端项目的根路由配置。

作为 Django URL 解析的入口，将不同业务模块的子路由通过 include() 聚合到 /api/ 前缀下，
同时保留 Django 内置的 admin 管理后台路径。

路由结构
--------
/admin/          → Django 管理后台
/api/health      → system 模块（健康检查）
/api/nodes       → topology 模块（节点列表）
/api/routes      → topology 模块（路由列表）
/api/packet      → packets 模块（数据包生成）
/api/ikuai/login → ikuai 模块（iKuai 登录）
/api/ikuai/sessions → ikuai 模块（会话历史）
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django 内置管理后台
    path('admin/', admin.site.urls),
    # 各业务模块 API 路由（统一前缀 /api/）
    path('api/', include('system.urls')),
    path('api/', include('topology.urls')),
    path('api/', include('packets.urls')),
    path('api/', include('ikuai.urls')),
]
