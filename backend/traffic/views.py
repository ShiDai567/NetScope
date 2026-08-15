"""NetScope JSON API。"""
from __future__ import annotations

import json
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .hub import hub

_STARTED_AT = time.time()


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


@require_GET
def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "uptime": round(time.time() - _STARTED_AT, 3),
            "service": "netscope-backend",
        }
    )


@require_GET
def packets(request):
    """增量数据包事件。?since=<seq> 返回 seq 之后的事件。"""
    hub.ensure_started()
    try:
        since = int(request.GET.get("since", "0"))
    except ValueError:
        since = 0
    return JsonResponse(hub.events_since(max(0, since)))


@require_GET
def history(request):
    """历史事件，用于时间轴回放。?minutes=5 默认 10 分钟。"""
    hub.ensure_started()
    try:
        minutes = float(request.GET.get("minutes", "10"))
    except ValueError:
        minutes = 10.0
    minutes = max(0.5, min(minutes, 30.0))
    return JsonResponse(hub.history(minutes))


@require_GET
def devices(request):
    hub.ensure_started()
    return JsonResponse({"devices": hub.devices()})


@require_GET
def nodes(request):
    hub.ensure_started()
    return JsonResponse({"nodes": hub.nodes()})


@require_GET
def stats(request):
    hub.ensure_started()
    return JsonResponse(hub.stats_snapshot())


@require_GET
def mode(request):
    hub.ensure_started()
    return JsonResponse(hub.status())


@csrf_exempt
@require_POST
def ikuai_connect(request):
    """连接真实 iKuai 路由器并切换到真实数据源。"""
    hub.ensure_started()
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _bad_request("请求体必须是 JSON")

    router_url = str(body.get("routerUrl") or "").strip()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "").strip()
    if not router_url or not username or not password:
        return _bad_request("routerUrl / username / password 均为必填")

    try:
        from ikuai_sdk.exceptions import IKuaiError

        result = hub.connect_ikuai(router_url, username, password)
        return JsonResponse({"ok": True, **result})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)


@csrf_exempt
@require_POST
def ikuai_disconnect(request):
    hub.ensure_started()
    return JsonResponse({"ok": True, **hub.disconnect_ikuai()})
