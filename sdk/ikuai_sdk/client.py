import hashlib
import json
import secrets
from http.cookies import SimpleCookie
from urllib import error, parse, request

from .exceptions import IKuaiNetworkError, IKuaiValidationError
from .models import IKuaiCallResult, IKuaiLoginResult


def normalize_router_url(router_url: str) -> str:
    return str(router_url or "").strip().rstrip("/")


def extract_cookie_values(set_cookie_headers: list[str]) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for header in set_cookie_headers:
        jar = SimpleCookie()
        jar.load(header)
        for key, morsel in jar.items():
            cookies[key] = morsel.value
    return cookies


def build_cookie_header(username: str, cookie_values: dict[str, str]) -> str | None:
    sess_key = cookie_values.get("sess_key")
    if not sess_key:
        return None
    return f"sess_key={sess_key}; username={username}; login=1"


class IKuaiClient:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def login(
        self,
        *,
        router_url: str,
        username: str,
        password: str,
        remember_password: str = "",
    ) -> IKuaiLoginResult:
        normalized_router_url = normalize_router_url(router_url)
        username = str(username or "").strip()
        password = str(password or "").strip()
        remember_password = "" if remember_password is None else str(remember_password)

        if not normalized_router_url or not username or not password:
            raise IKuaiValidationError("routerUrl, username, password are required")

        login_url = f"{normalized_router_url}/Action/login"
        request_payload = {
            "username": username,
            "passwd": hashlib.md5(password.encode("utf-8")).hexdigest(),
            "pass": secrets.token_hex(10),
            "remember_password": remember_password,
        }

        last_result = None
        for request_mode, use_json in (("json", True), ("form", False)):
            upstream_status, response_body, response_headers, cookies = self._post_login(
                login_url=login_url,
                payload=request_payload,
                use_json=use_json,
            )
            # 防暴力登录 WAF：首次请求返回 403 并下发挑战 cookie，
            # 携带该 cookie 重试一次才是真正的登录请求
            if upstream_status == 403 and cookies and "sess_key" not in cookies:
                challenge = "; ".join(f"{k}={v}" for k, v in cookies.items())
                (
                    upstream_status,
                    response_body,
                    response_headers,
                    cookies,
                ) = self._post_login(
                    login_url=login_url,
                    payload=request_payload,
                    use_json=use_json,
                    extra_cookie_header=challenge,
                )
            try:
                upstream_response = json.loads(response_body) if response_body else {}
            except json.JSONDecodeError:
                upstream_response = {"raw": response_body}

            last_result = IKuaiLoginResult(
                router_url=normalized_router_url,
                login_url=login_url,
                username=username,
                request_mode=request_mode,
                request_payload=request_payload,
                upstream_status=upstream_status,
                upstream_response=upstream_response,
                response_headers=response_headers,
                cookies=cookies,
                sess_key=cookies.get("sess_key"),
                cookie_header=build_cookie_header(username, cookies),
            )

            if last_result.result_code in {10000, 10001}:
                return last_result

        if last_result is None:
            raise IKuaiNetworkError("unexpected iKuai response")
        return last_result

    def call(
        self,
        *,
        router_url: str,
        path: str = "/Action/call",
        payload: dict,
        cookie_header: str,
    ) -> IKuaiCallResult:
        normalized_router_url = normalize_router_url(router_url)
        if not normalized_router_url:
            raise IKuaiValidationError("router_url is required")
        if not cookie_header:
            raise IKuaiValidationError("cookie_header is required")

        endpoint = f"{normalized_router_url}{path}"
        upstream_status, response_body, response_headers = self._post_json(
            url=endpoint,
            payload=payload,
            cookie_header=cookie_header,
        )
        try:
            upstream_response = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            upstream_response = {"raw": response_body}

        return IKuaiCallResult(
            path=path,
            payload=payload,
            upstream_status=upstream_status,
            upstream_response=upstream_response,
            response_headers=response_headers,
        )

    def get_terminal_list(
        self,
        *,
        router_url: str,
        cookie_header: str,
        limit: str = "0,100",
        order_by: str = "ip_addr_int",
        order: str = "",
        order_type: str = "IP",
    ) -> IKuaiCallResult:
        payload = {
            "func_name": "monitor_lanip",
            "action": "show",
            "param": {
                "TYPE": "data,total",
                "ORDER_BY": order_by,
                "orderType": order_type,
                "limit": limit,
                "ORDER": order,
            },
        }
        return self.call(
            router_url=router_url,
            path="/Action/call",
            payload=payload,
            cookie_header=cookie_header,
        )

    def get_terminal_connection_details(
        self,
        *,
        router_url: str,
        cookie_header: str,
        ip: str,
        interface: str = "all",
        proto: str = "all",
        maxnum: int = 500,
        limit: str = "0,100",
        order_by: str = "",
        order: str = "",
    ) -> IKuaiCallResult:
        if not str(ip or "").strip():
            raise IKuaiValidationError("ip is required")

        payload = {
            "func_name": "monitor_lanip",
            "action": "show",
            "param": {
                "TYPE": "conn,conn_num",
                "ip": str(ip).strip(),
                "interface": interface,
                "proto": proto,
                "maxnum": maxnum,
                "limit": limit,
                "ORDER_BY": order_by,
                "ORDER": order,
            },
        }
        return self.call(
            router_url=router_url,
            path="/Action/call",
            payload=payload,
            cookie_header=cookie_header,
        )

    def get_interface_stream(
        self,
        *,
        router_url: str,
        cookie_header: str,
    ) -> IKuaiCallResult:
        """接口实时速率（iface_stream，upload/download 单位 B/s）。

        返回同时包含 snapshoot_wan（权威 WAN 口列表），
        两者求交集即可得到真实公网上下行带宽。
        """
        payload = {
            "func_name": "monitor_iface",
            "action": "show",
            "param": {"TYPE": "all"},
        }
        return self.call(
            router_url=router_url,
            path="/Action/call",
            payload=payload,
            cookie_header=cookie_header,
        )

    def get_system_monitor(
        self,
        *,
        router_url: str,
        cookie_header: str,
    ) -> IKuaiCallResult:
        """系统负载历史采样（cpu / memory_use 百分比等），最后一条为最新样本。"""
        payload = {
            "func_name": "monitor_system",
            "action": "show",
            "param": {},
        }
        return self.call(
            router_url=router_url,
            path="/Action/call",
            payload=payload,
            cookie_header=cookie_header,
        )

    def login_and_get_terminal_list(
        self,
        *,
        router_url: str,
        username: str,
        password: str,
        remember_password: str = "",
        limit: str = "0,100",
    ) -> tuple[IKuaiLoginResult, IKuaiCallResult]:
        login_result = self.login(
            router_url=router_url,
            username=username,
            password=password,
            remember_password=remember_password,
        )
        if not login_result.cookie_header:
            raise IKuaiNetworkError("login succeeded but cookie_header is empty")
        terminal_result = self.get_terminal_list(
            router_url=router_url,
            cookie_header=login_result.cookie_header,
            limit=limit,
        )
        return login_result, terminal_result

    def login_and_get_terminal_connection_details(
        self,
        *,
        router_url: str,
        username: str,
        password: str,
        ip: str,
        remember_password: str = "",
        limit: str = "0,100",
        interface: str = "all",
        proto: str = "all",
        maxnum: int = 500,
    ) -> tuple[IKuaiLoginResult, IKuaiCallResult]:
        login_result = self.login(
            router_url=router_url,
            username=username,
            password=password,
            remember_password=remember_password,
        )
        if not login_result.cookie_header:
            raise IKuaiNetworkError("login succeeded but cookie_header is empty")
        connection_result = self.get_terminal_connection_details(
            router_url=router_url,
            cookie_header=login_result.cookie_header,
            ip=ip,
            interface=interface,
            proto=proto,
            maxnum=maxnum,
            limit=limit,
        )
        return login_result, connection_result

    def _post_login(
        self,
        *,
        login_url: str,
        payload: dict[str, str],
        use_json: bool,
        extra_cookie_header: str | None = None,
    ):
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{login_url.rsplit('/', 1)[0]}/",
        }
        if extra_cookie_header:
            headers["Cookie"] = extra_cookie_header
        if use_json:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        else:
            body = parse.urlencode(payload).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"

        req = request.Request(login_url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return (
                    response.status,
                    response.read().decode("utf-8", errors="replace"),
                    dict(response.headers.items()),
                    extract_cookie_values(response.headers.get_all("Set-Cookie") or []),
                )
        except error.HTTPError as exc:
            return (
                exc.code,
                exc.read().decode("utf-8", errors="replace"),
                dict(exc.headers.items()),
                extract_cookie_values(exc.headers.get_all("Set-Cookie") or []),
            )
        except error.URLError as exc:
            raise IKuaiNetworkError(str(exc.reason)) from exc

    def _post_json(self, *, url: str, payload: dict, cookie_header: str):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{url.rsplit('/', 1)[0]}/",
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return (
                    response.status,
                    response.read().decode("utf-8", errors="replace"),
                    dict(response.headers.items()),
                )
        except error.HTTPError as exc:
            return (
                exc.code,
                exc.read().decode("utf-8", errors="replace"),
                dict(exc.headers.items()),
            )
        except error.URLError as exc:
            raise IKuaiNetworkError(str(exc.reason)) from exc
