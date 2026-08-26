"""公共配置。所有可调参数均来自环境变量（doc/backend-design.md §16）。"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(str, "localhost,127.0.0.1"),
    DJANGO_CORS_ORIGINS=(str, "http://localhost:3000"),
    REDIS_URL=(str, "redis://127.0.0.1:6379/0"),
    DATABASE_URL=(str, f"sqlite:///{BASE_DIR / 'netscope.db'}"),
    DATA_SOURCE=(str, "ikuai"),
    RUN_COLLECTOR_IN_PROCESS=(bool, False),
    MOCK_SCENARIO=(str, "mixed"),
    LOG_LEVEL=(str, "INFO"),
)
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = env("DJANGO_DEBUG")

_allowed_hosts = env("DJANGO_ALLOWED_HOSTS")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(",") if h.strip()]
CORS_ALLOWED_ORIGINS = [o.strip() for o in env("DJANGO_CORS_ORIGINS").split(",") if o.strip()]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "channels",
    "network.apps.NetworkConfig",
    "analytics.apps.AnalyticsConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {"default": env.db_url("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 30
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"].setdefault("OPTIONS", {})
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            "capacity": 2000,
            "expiry": 30,
        },
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "EXCEPTION_HANDLER": "core.api_errors.exception_handler",
    "DEFAULT_THROTTLE_RATES": {"packets": "10/s", "api": "5/s"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NetScope API",
    "DESCRIPTION": "GLOBAL NETWORK INTELLIGENCE CENTER REST API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------- 网络采集域


def _float_or_none(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


DATA_SOURCE = env("DATA_SOURCE").strip().lower()
if DATA_SOURCE not in ("ikuai", "mock"):
    raise RuntimeError(f"DATA_SOURCE 必须是 ikuai|mock，当前为 {DATA_SOURCE!r}")

RUN_COLLECTOR_IN_PROCESS = env("RUN_COLLECTOR_IN_PROCESS")
MOCK_SCENARIO = env("MOCK_SCENARIO")

IKUAI_ROUTER_URL = env("IKUAI_ROUTER_URL", default="http://10.1.1.1")
IKUAI_USERNAME = env("IKUAI_USERNAME", default="admin")
IKUAI_PASSWORD = env("IKUAI_PASSWORD", default="")
IKUAI_TERMINAL_POLL_INTERVAL = env.float("IKUAI_TERMINAL_POLL_INTERVAL", default=10.0)
IKUAI_CONN_POLL_INTERVAL = env.float("IKUAI_CONN_POLL_INTERVAL", default=5.0)
IKUAI_SYSTEM_POLL_INTERVAL = env.float("IKUAI_SYSTEM_POLL_INTERVAL", default=5.0)
IKUAI_IFACE_POLL_INTERVAL = env.float("IKUAI_IFACE_POLL_INTERVAL", default=10.0)
IKUAI_WAN_POLL_INTERVAL = env.float("IKUAI_WAN_POLL_INTERVAL", default=300.0)
IKUAI_REQUEST_TIMEOUT = env.int("IKUAI_REQUEST_TIMEOUT", default=8)
IKUAI_SSL_VERIFY = env.bool("IKUAI_SSL_VERIFY", default=False)

GATEWAY_IP = env("GATEWAY_IP", default="").strip() or None
SERVER_LAT = _float_or_none(env("SERVER_LAT", default=""))
SERVER_LNG = _float_or_none(env("SERVER_LNG", default=""))
# 核心服务器定位：填域名或 IP（如 example.com / 1.2.3.4），后端解析后 GeoIP 定位；
# 优先级：SERVER_LAT/LNG 显式坐标 > SERVER_LOCATION > WAN 出口 IP 自动探测
SERVER_LOCATION = env("SERVER_LOCATION", default="").strip() or None

_listen_raw = env("LISTEN_PORTS", default="22,80,443,445,8080,8443,5001")
LISTEN_PORTS = frozenset(int(p) for p in (s.strip() for s in _listen_raw.split(",")) if p.isdigit())

# ---- Geo（SQL GeoLookup 表为主源 + hiofd API 兜底）----
GEO_API_ENABLED = env.bool("GEO_API_ENABLED", default=True)
GEO_API_TIMEOUT = env.float("GEO_API_TIMEOUT", default=6.0)
MANUAL_GEO_JSON = env("MANUAL_GEO_JSON", default=None)

PACKET_BUFFER_MAX = env.int("PACKET_BUFFER_MAX", default=10000)
_stats_windows_raw = env("STATS_WINDOWS", default="5,30,60,300,900,3600")
STATS_WINDOWS: tuple[int, ...] = tuple(
    sorted({int(w) for w in _stats_windows_raw.split(",") if w.strip().isdigit()})
)
BROADCAST_INTERVAL_MS = env.float("BROADCAST_INTERVAL_MS", default=400.0)
FLOW_PERSIST = env.bool("FLOW_PERSIST", default=False)
SNAPSHOT_RETENTION_DAYS = env.int("SNAPSHOT_RETENTION_DAYS", default=30)
FLOW_RECORD_RETENTION_DAYS = env.int("FLOW_RECORD_RETENTION_DAYS", default=7)
LOG_LEVEL = env("LOG_LEVEL").upper()

# collector 内部节拍（秒）
AGG_TICK_INTERVAL = 1.0
PERSIST_INTERVAL = 60.0
HEARTBEAT_INTERVAL = 15.0
CONN_CLOSE_GAP_SWEEPS = 2
CONN_UPDATE_EVERY_SWEEPS = 3
