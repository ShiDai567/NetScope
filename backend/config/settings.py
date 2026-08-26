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


def _load_env_file(path: Path) -> None:
    """极简 .env 加载器（KEY=VALUE），不覆盖已存在的环境变量。"""
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_env_file(REPO_ROOT / ".env")
_load_env_file(BASE_DIR / ".env")


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

# 无数据库：运行态数据全部在内存（事件环形日志 / 统计聚合 / GeoIP 缓存）
DATABASES = {}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 网关（内网）地理位置，用于内网节点在地图上的聚簇中心
GATEWAY_LAT = float(os.environ.get("NETSCOPE_GATEWAY_LAT", "39.9042"))
GATEWAY_LNG = float(os.environ.get("NETSCOPE_GATEWAY_LNG", "116.4074"))

# iKuai 真实数据源：三项齐全时服务启动即自动连接（无需手动调 /api/ikuai/connect）
IKUAI_URL = os.environ.get("NETSCOPE_IKUAI_URL", "").strip().rstrip("/")
IKUAI_USERNAME = os.environ.get("NETSCOPE_IKUAI_USERNAME", "").strip()
IKUAI_PASSWORD = os.environ.get("NETSCOPE_IKUAI_PASSWORD", "")
# 备用地址：主地址被 WAF 拦截 / 不可达时自动轮换（如内网 http://10.0.1.1:6301）
IKUAI_FALLBACK_URL = os.environ.get("NETSCOPE_IKUAI_FALLBACK_URL", "").strip().rstrip("/")
