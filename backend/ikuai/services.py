from ikuai_sdk import IKuaiClient, IKuaiNetworkError, IKuaiValidationError

from .models import IKuaiSession


def serialize_session(session):
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
        return {"error": str(exc)}, 400
    except IKuaiNetworkError as exc:
        return {
            "error": "failed to reach iKuai router",
            "message": str(exc),
        }, 502

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

    if result.result_code == 10000:
        return serialize_session(session), 200
    if result.result_code == 10001:
        return serialize_session(session), 401
    return serialize_session(session), 502
