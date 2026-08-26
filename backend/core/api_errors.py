"""API 统一错误信封与限流类（doc §10.1）。"""

import logging

from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger("core.api_errors")

CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def exception_handler(exc, context):
    """DRF/Django 异常 → {"error": {"code", "message"}} 信封。"""
    if isinstance(exc, Http404):
        return Response(
            error_body("not_found", "资源不存在"),
            status=status.HTTP_404_NOT_FOUND,
        )
    response = drf_exception_handler(exc, context)
    if response is None:
        log.exception("unhandled_api_error", exc_info=exc)
        return Response(
            error_body("internal_error", "服务器内部错误"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(response.data, dict) and "error" in response.data:
        return response
    detail = response.data.get("detail") if isinstance(response.data, dict) else response.data
    if isinstance(detail, (list, dict)):
        message = "请求参数错误"
        code = "validation_error"
    else:
        message = str(detail) if detail is not None else "请求错误"
        code = CODE_BY_STATUS.get(response.status_code, "error")
    response.data = error_body(code, message)
    return response


class PacketsThrottle(AnonRateThrottle):
    scope = "packets"


class ApiThrottle(AnonRateThrottle):
    scope = "api"


def handler404(request, exception=None):
    """Django URL 404 → JSON 错误信封（仅 /api/ 下；其余返回默认文本）。"""
    from django.http import HttpResponseNotFound, JsonResponse

    if request.path.startswith("/api/"):
        return JsonResponse(error_body("not_found", "资源不存在"), status=status.HTTP_404_NOT_FOUND)
    return HttpResponseNotFound("Not Found")


def handler500(request):
    from django.http import HttpResponseServerError, JsonResponse

    if request.path.startswith("/api/"):
        return JsonResponse(
            error_body("internal_error", "服务器内部错误"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return HttpResponseServerError("Server Error")
