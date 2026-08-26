"""iKuai 会话管理：登录态、自动重登、失败退避（doc §5.1.2）。"""

import random
import time

from core.log import get_logger
from core.utils.timeutil import now_ts
from datasource.ikuai.funcs import IKUAI_AUTH_FAIL, IKUAI_OK
from datasource.ikuai.sdk_loader import BackoffError, GatewayError, import_ikuai_sdk

log = get_logger("datasource.ikuai.session")

_FAILS_BEFORE_BACKOFF = 3
_BACKOFF_BASE = 5.0
_BACKOFF_CAP = 30.0


class SessionManager:
    """持有 sess_key Cookie；call() 统一走这里。"""

    def __init__(
        self,
        router_url: str,
        username: str,
        password: str,
        timeout: int = 8,
        verify_ssl: bool = True,
        on_state_change=None,
    ) -> None:
        self.router_url = router_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._on_state = on_state_change
        from datasource.ikuai.sdk_loader import install_ssl_bypass

        install_ssl_bypass(verify_ssl)
        sdk = import_ikuai_sdk()
        self._client = sdk.IKuaiClient(timeout=timeout)
        self._cookie_header: str | None = None
        self._connected = False
        self._fail_streak = 0
        self._next_allowed_at = 0.0
        self.last_poll_at: float | None = None
        self.connected_at: float | None = None

    # ------------------------------------------------------------ 状态

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------ 登录

    def ensure_login(self, force: bool = False) -> None:
        if self._cookie_header and not force:
            return
        result = self._client.login(
            router_url=self.router_url,
            username=self.username,
            password=self.password,
        )
        if result.result_code == IKUAI_OK and result.cookie_header:
            self._cookie_header = result.cookie_header
            if not self.connected:
                self.connected_at = now_ts()
            self._set_state(True)
            log.info("ikuai.login_ok", request_mode=result.request_mode)
        else:
            self._set_state(False, result.result_message)
            raise GatewayError(f"iKuai 登录失败: {result.result_code} {result.result_message}")

    # ------------------------------------------------------------ 调用

    def call(self, payload: dict) -> dict:
        """发起 /Action/call，返回 Data 部分；认证失效自动重登一次。"""
        if time.monotonic() < self._next_allowed_at:
            raise BackoffError("iKuai 会话处于退避期")

        self.ensure_login()
        result = None
        for attempt in (1, 2):
            try:
                result = self._client.call(
                    router_url=self.router_url,
                    payload=payload,
                    cookie_header=self._cookie_header or "",
                )
            except Exception as exc:
                self._record_failure(str(exc))
                raise GatewayError(f"iKuai 调用网络异常: {exc}") from exc

            if result.result_code in (IKUAI_OK, 0) or result.result_message == "Success":
                self._record_success()
                return result.data or {}

            if result.result_code == IKUAI_AUTH_FAIL or result.upstream_status in (401, 403):
                if attempt == 1:
                    log.warning("ikuai.relogin", status=result.upstream_status)
                    self._cookie_header = None
                    self.ensure_login(force=True)
                    continue
            self._record_failure(f"{result.result_code} {result.result_message}")
            raise GatewayError(f"iKuai 调用失败: {result.result_code} {result.result_message}")
        raise GatewayError("iKuai 调用失败：未知状态")

    # ------------------------------------------------------------ 成败记录

    def _record_success(self) -> None:
        self.last_poll_at = now_ts()
        self._fail_streak = 0
        self._next_allowed_at = 0.0
        self._set_state(True)

    def _record_failure(self, reason: str) -> None:
        self._fail_streak += 1
        self._set_state(False, reason)
        if self._fail_streak >= _FAILS_BEFORE_BACKOFF:
            backoff = min(_BACKOFF_CAP, _BACKOFF_BASE * (2 ** (self._fail_streak - _FAILS_BEFORE_BACKOFF)))
            self._next_allowed_at = time.monotonic() + backoff * (1 + random.random() * 0.2)
            log.warning("ikuai.backoff", fails=self._fail_streak, seconds=round(backoff, 1))

    def health_snapshot(self) -> dict:
        return {
            "router_url": self.router_url,
            "error": None if self.connected else self._last_error(),
            "last_poll_at": self.last_poll_at,
            "connected_at": self.connected_at,
        }

    def _last_error(self) -> str:
        return getattr(self, "_last_error_text", None) or "iKuai 会话未建立"

    def _set_state(self, connected: bool, error: str | None = None) -> None:
        if error:
            self._last_error_text = error
        if connected == self._connected:
            return
        self._connected = connected
        log.info("ikuai.state", connected=connected, error=error)
        if self._on_state:
            try:
                self._on_state(connected, error)
            except Exception:
                pass
