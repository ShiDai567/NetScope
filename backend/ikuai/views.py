"""
ikuai/views.py
==============
iKuai 路由器集成模块视图。

提供两个接口：
1. iKuai 登录接口：接收路由器地址、用户名、密码，调用 SDK 尝试登录并持久化结果。
2. 会话列表接口：查询最近的历史登录记录，便于前端展示或审计。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import IKuaiSession
from .services import login_to_ikuai, serialize_session_summary


@csrf_exempt
@require_POST
def ikuai_login_view(request):
    """
    iKuai 路由器登录接口 (POST /api/ikuai/login)。

    请求体 (JSON)
    -------------
    {
        "routerUrl": "http://192.168.1.1",  // 或 router_url / baseUrl / base_url / host
        "username": "admin",
        "password": "admin",
        "remember_password": true           // 或 rememberPassword
    }

    响应格式 (JSON)
    ---------------
    成功 (200):
        { "id": 1, "routerUrl": "...", "username": "...", "sessKey": "...", ... }
    参数校验失败 (400):
        { "error": "routerUrl is required" }
    认证失败 (401):
        { "error": "invalid credentials", "resultCode": 10001, ... }
    网络不可达 (502):
        { "error": "failed to reach iKuai router", "message": "..." }

    安全说明
    --------
    使用 @csrf_exempt 豁免 CSRF 校验，因为该接口通常由第三方系统或前端跨域调用。
    生产环境建议配合 IP 白名单或 API Token 使用。
    """
    # 解析请求体，处理空 body 或非法 JSON。
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    # 委托服务层执行登录逻辑，服务层返回 (data, status_code) 元组。
    response_payload, status_code = login_to_ikuai(payload)
    return JsonResponse(response_payload, status=status_code)


@require_GET
def ikuai_sessions_view(request):
    """
    获取 iKuai 登录会话历史列表 (GET /api/ikuai/sessions)。

    查询参数
    --------
    limit : int, optional, default=20
        返回记录数量上限，范围 1~100。

    返回格式 (JSON)
    ---------------
    [
        {
            "id": 1,
            "routerUrl": "http://192.168.1.1",
            "username": "admin",
            "requestMode": "json",
            "resultCode": 10000,
            "resultMessage": "success",
            "sessKey": "abc123",
            "cookieHeader": "sess=abc123; ...",
            "createdAt": "2026-05-06T13:45:00Z"
        },
        ...
    ]

    错误响应
    --------
    400 Bad Request
        - limit 不是有效整数
        - limit 超出 1~100 范围
    """
    # 解析并校验 limit 参数。
    try:
        limit = int(request.GET.get("limit", "20") or 20)
    except ValueError:
        return JsonResponse({"error": "limit must be an integer"}, status=400)
    if limit < 1 or limit > 100:
        return JsonResponse({"error": "limit must be between 1 and 100"}, status=400)

    # 按创建时间倒序取前 limit 条记录。
    sessions = IKuaiSession.objects.all()[:limit]
    return JsonResponse([serialize_session_summary(session) for session in sessions], safe=False)
