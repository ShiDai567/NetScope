"""NetScope backend settings.

轻量级 API 服务：不启用 admin / session / auth / staticfiles，
只保留提供 JSON API 所需的最小配置。
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# 让仓库根目录下的 sdk/ikuai_sdk 可以被直接 import
SDK_DIR = REPO_ROOT / "sdk"
if SDK_DIR.exists() and str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "netscope-dev-only-secret-key-change-me"
)
DEBUG = _env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0"
    ).split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "traffic",
]

MIDDLEWARE = [
    "traffic.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = []

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# 不使用数据库（运行态数据全部在内存中），保留 sqlite 仅为满足 Django 默认要求
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 网关（内网）地理位置，用于内网节点在地图上的聚簇中心
GATEWAY_LAT = float(os.environ.get("NETSCOPE_GATEWAY_LAT", "39.9042"))
GATEWAY_LNG = float(os.environ.get("NETSCOPE_GATEWAY_LNG", "116.4074"))
