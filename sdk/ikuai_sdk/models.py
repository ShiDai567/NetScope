from dataclasses import dataclass


@dataclass(slots=True)
class IKuaiLoginResult:
    router_url: str
    login_url: str
    username: str
    request_mode: str
    request_payload: dict
    upstream_status: int | None
    upstream_response: dict
    response_headers: dict
    cookies: dict
    sess_key: str | None
    cookie_header: str | None

    @property
    def result_code(self) -> int | None:
        # 兼容旧版（大写）和新版（小写）字段名
        for key in ("Result", "code"):
            value = self.upstream_response.get(key)
            if isinstance(value, int):
                return value
        return None

    @property
    def result_message(self) -> str:
        # 兼容旧版（ErrMsg）和新版（message）字段名
        for key in ("ErrMsg", "message"):
            value = self.upstream_response.get(key)
            if value is not None:
                return str(value)
        return ""


@dataclass(slots=True)
class IKuaiCallResult:
    path: str
    payload: dict
    upstream_status: int | None
    upstream_response: dict
    response_headers: dict

    @property
    def result_code(self) -> int | None:
        # 兼容旧版（大写）和新版（小写）字段名
        for key in ("Result", "code"):
            value = self.upstream_response.get(key)
            if isinstance(value, int):
                return value
        return None

    @property
    def result_message(self) -> str:
        # 兼容旧版（ErrMsg）和新版（message）字段名
        for key in ("ErrMsg", "message"):
            value = self.upstream_response.get(key)
            if value is not None:
                return str(value)
        return ""

    @property
    def data(self):
        # 兼容旧版（大写 Data）和新版（小写 results）字段名
        for key in ("Data", "results"):
            value = self.upstream_response.get(key)
            if value is not None:
                return value
        return None
