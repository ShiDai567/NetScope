"""
system/views.py
===============
系统状态监控模块视图。

提供健康检查接口，用于负载均衡器、容器编排平台（如 Kubernetes）
或前端应用判断后端服务是否正常运行。
"""

import time

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

# 记录服务启动时刻，用于计算运行时长（uptime）。
# time.monotonic() 不受系统时间调整影响，适合用于计时。
START_TIME = time.monotonic()


@require_GET
def health_view(request):
    """
    健康检查接口 (GET /api/health)。

    功能说明
    --------
    1. 执行一次简单的数据库查询 ``SELECT 1``，验证数据库连接是否正常。
    2. 计算并返回当前服务的运行时长（uptime）。
    3. 返回当前服务器时间（ISO 8601 格式）。

    返回格式 (JSON)
    ---------------
    {
        "status": "ok",                // 服务状态
        "service": "netscope-backend", // 服务名称
        "uptime": 123.456,             // 运行秒数
        "database": "ok",              // 数据库连接状态
        "time": "2026-05-06T13:45:00Z" // 当前服务器时间
    }

    典型使用场景
    ------------
    - Kubernetes livenessProbe / readinessProbe
    - 前端页面加载时确认后端可用
    - 监控告警系统定时探测
    """
    # 使用原始 SQL 游标执行健康探测查询。
    # 如果数据库连接异常，这里会抛出 django.db.DatabaseError，
    # Django 中间件会将其转换为 500 响应。
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    return JsonResponse(
        {
            "status": "ok",
            "service": "netscope-backend",
            "uptime": round(time.monotonic() - START_TIME, 3),
            "database": "ok",
            "time": timezone.now().isoformat().replace("+00:00", "Z"),
        }
    )
