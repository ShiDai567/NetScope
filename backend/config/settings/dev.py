"""开发环境：宽松安全策略，允许调试工具。"""

from .base import *  # noqa: F401,F403,F405
from .base import BASE_DIR  # noqa: F401

DEBUG = True
if "testserver" not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, "testserver"]  # noqa: F405

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "kv": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "kv"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},  # noqa: F405
    "loggers": {
        "django.server": {"level": "WARNING"},
        "datasource": {"propagate": True},
        "network": {"propagate": True},
        "analytics": {"propagate": True},
    },
}
