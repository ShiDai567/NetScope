"""
config/asgi.py
==============
NetScope 后端项目的 ASGI 配置入口。

ASGI（Asynchronous Server Gateway Interface）是支持异步的 Web 应用接口标准。
本文件暴露名为 ``application`` 的模块级变量，供 Daphne、Uvicorn 等异步服务器加载。

当前项目以同步视图为主，但保留 ASGI 入口以便未来扩展 WebSocket、SSE 等异步功能。

部署参考
--------
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# 设置默认的 Django 配置模块路径。
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
