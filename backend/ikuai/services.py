"""
ikuai/services.py
=================
iKuai 路由器集成模块业务逻辑层。

封装与 iKuai SDK 的交互、登录结果解析和序列化逻辑。
该层负责屏蔽 SDK 细节，向上层视图提供统一的登录入口和数据格式。

外部依赖
--------
ikuai_sdk : 第三方 SDK，位于项目根目录的 sdk/ 文件夹中。
    提供 IKuaiClient、IKuaiNetworkError、IKuaiValidationError。
"""

from ikuai_sdk import IKuaiClient, IKuaiNetworkError, IKuaiValidationError

from .models import IKuaiSession


def serialize_session(session):
    """
    完整序列化 IKuaiSession 实例。

    返回包含所有字段的字典，适用于登录成功/失败后的详细响应。
    """
    return {
        "id": session.id,
        "routerUrl": session.router_url,
        "loginUrl": session.login_url,
        "username": session.username,
        "requestMode": session.request_mode,
        "requestPayload": session.request_payload,
        "upstreamStatus": session.upstream_status,
        "upstreamResponse": session.upstream_response,
        "cookies": session.cookies,
        "sess_key": session.sess_key or None,
        "cookieHeader": session.cookie_header or None,
        "createdAt": session.created_at.isoformat().replace("+00:00", "Z"),
    }


def serialize_session_summary(session):
    """
    精简序列化 IKuaiSession 实例。

    仅返回列表展示所需的关键字段，减少网络传输量。
    """
    return {
        "id": session.id,
        "routerUrl": session.router_url,
        "username": session.username,
        "requestMode": session.request_mode,
        "resultCode": session.result_code,
        "resultMessage": session.result_message,
        "sessKey": session.sess_key or None,
        "cookieHeader": session.cookie_header or None,
        "createdAt": session.created_at.isoformat().replace("+00:00", "Z"),
    }


def login_to_ikuai(payload):
    """
    调用 iKuai SDK 执行登录，并将结果持久化到数据库。

    参数
    ----
    payload : dict
        前端传来的登录参数，支持多种 key 别名以提升兼容性：
        - routerUrl / router_url / baseUrl / base_url / host → 路由器地址
        - username → 用户名
        - password → 密码
        - remember_password / rememberPassword → 是否记住密码

    返回
    ----
    tuple[dict, int]
        (response_data, http_status_code)

    状态码映射
    ----------
    200 : result_code == 10000，登录成功。
    401 : result_code == 10001，用户名或密码错误。
    400 : SDK 参数校验失败（IKuaiValidationError）。
    502 : 路由器网络不可达（IKuaiNetworkError）或未知业务码。
    """
    # 兼容多种前端传参风格，优先使用驼峰命名，回退到下划线命名。
    try:
        result = IKuaiClient().login(
            router_url=(
                payload.get("routerUrl")
                or payload.get("router_url")
                or payload.get("baseUrl")
                or payload.get("base_url")
                or payload.get("host")
                or ""
            ),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            remember_password=payload.get("remember_password", payload.get("rememberPassword", "")),
        )
    except IKuaiValidationError as exc:
        # SDK 层参数校验失败（如 URL 格式非法、必填字段缺失）。
        return {"error": str(exc)}, 400
    except IKuaiNetworkError as exc:
        # 无法连接到路由器（超时、拒绝连接、DNS 失败等）。
        return {
            "error": "failed to reach iKuai router",
            "message": str(exc),
        }, 502

    # 将 SDK 返回的结果持久化到数据库，便于审计和后续会话复用。
    session = IKuaiSession.objects.create(
        router_url=result.router_url,
        login_url=result.login_url,
        username=result.username,
        request_mode=result.request_mode,
        request_payload=result.request_payload,
        upstream_status=result.upstream_status,
        result_code=result.result_code,
        result_message=result.result_message,
        cookies=result.cookies,
        sess_key=result.sess_key or "",
        cookie_header=result.cookie_header or "",
        response_headers=result.response_headers,
        upstream_response=result.upstream_response,
    )

    # 根据 iKuai 业务状态码映射 HTTP 状态码。
    if result.result_code == 10000:
        return serialize_session(session), 200
    if result.result_code == 10001:
        return serialize_session(session), 401
    # 其他未知业务码统一视为上游异常。
    return serialize_session(session), 502
