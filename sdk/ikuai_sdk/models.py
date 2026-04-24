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
        value = self.upstream_response.get("Result")
        return value if isinstance(value, int) else None

    @property
    def result_message(self) -> str:
        return str(self.upstream_response.get("ErrMsg", ""))


@dataclass(slots=True)
class IKuaiCallResult:
    path: str
    payload: dict
    upstream_status: int | None
    upstream_response: dict
    response_headers: dict

    @property
    def result_code(self) -> int | None:
        value = self.upstream_response.get("Result")
        return value if isinstance(value, int) else None

    @property
    def result_message(self) -> str:
        return str(self.upstream_response.get("ErrMsg", ""))

    @property
    def data(self):
        return self.upstream_response.get("Data")
