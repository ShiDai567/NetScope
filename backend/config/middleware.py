"""
config/middleware.py
====================
NetScope 自定义中间件。

提供 SimpleCorsMiddleware，用于在开发环境快速解决前端跨域问题。
生产环境建议替换为 django-cors-headers 库，并配置严格的允许源列表。
"""


class SimpleCorsMiddleware:
    """
    简易 CORS 跨域中间件。

    功能说明
    --------
    为所有响应添加 Access-Control-Allow-Origin: * 头，允许任意域名访问。
    同时支持处理 OPTIONS 预检请求（Preflight），返回 204 No Content。

    使用场景
    --------
    - 本地开发时前端（如 localhost:3000）调用后端 API（localhost:8000）。
    - 快速原型验证，无需配置复杂的反向代理。

    安全警告
    --------
    生产环境切勿直接使用 * 通配符，应限定为具体域名，
    并配合 django-cors-headers 的 CORS_ALLOW_CREDENTIALS 等安全策略。
    """

    def __init__(self, get_response):
        """
        Django 中间件标准初始化方法。

        参数
        ----
        get_response : callable
            下一个中间件或视图的处理函数。
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        处理每个进入的 HTTP 请求。

        对 OPTIONS 预检请求直接返回 204，其他请求正常流转并在响应头追加 CORS 字段。
        """
        if request.method == "OPTIONS":
            response = self._build_preflight_response()
        else:
            response = self.get_response(request)

        # 为所有响应添加 CORS 头
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @staticmethod
    def _build_preflight_response():
        """
        构建 OPTIONS 预检请求的响应。

        返回
        ----
        HttpResponse
            状态码 204 No Content，表示服务器允许该跨域请求。
        """
        from django.http import HttpResponse
        return HttpResponse(status=204)
