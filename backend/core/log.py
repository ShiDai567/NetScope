"""结构化日志：structlog 可用则用，否则回退 stdlib（kv 风格输出）。"""

import json
import logging

try:
    import structlog

    _HAS_STRUCTLOG = True
except ImportError:  # pragma: no cover
    _HAS_STRUCTLOG = False

_CONFIGURED = False


class _KvLogger:
    """stdlib 适配器：logger.info("event", key=value) 风格。"""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _emit(self, level: str, event: str, kwargs: dict) -> None:
        extra = " ".join(f"{k}={json.dumps(v, ensure_ascii=False, default=str)}" for k, v in kwargs.items())
        getattr(self._logger, level)(f"{event} {extra}".strip())

    def debug(self, event: str, **kwargs) -> None:
        self._emit("debug", event, kwargs)

    def info(self, event: str, **kwargs) -> None:
        self._emit("info", event, kwargs)

    def warning(self, event: str, **kwargs) -> None:
        self._emit("warning", event, kwargs)

    def error(self, event: str, **kwargs) -> None:
        self._emit("error", event, kwargs)


def configure_logging(level: str = "INFO") -> None:
    """进程级日志初始化（collector 等非 Django 入口调用）。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if _HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
    _CONFIGURED = True


def get_logger(name: str):
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return _KvLogger(name)
