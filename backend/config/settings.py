"""
config/settings.py
==================
NetScope 后端项目的 Django 全局配置文件。

该文件集中管理数据库连接、已安装应用、中间件、安全策略等核心配置。
所有与环境相关的敏感信息（如 SECRET_KEY、数据库路径）均通过环境变量读取，
支持 .env 文件注入，便于不同环境（开发/测试/生产）灵活切换。
"""

import os
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# 工具函数：环境变量解析
# ─────────────────────────────────────────────────────────────

def load_dotenv(dotenv_path: Path) -> None:
    """
    手动解析 .env 文件并将键值对写入 os.environ。

    说明
    ----
    不依赖第三方 python-dotenv 库，减少项目依赖。
    使用 os.environ.setdefault，确保已存在的环境变量不会被覆盖，
    方便在 CI/CD 或容器环境中通过外部注入优先覆盖 .env 配置。

    参数
    ----
    dotenv_path : Path
        .env 文件的绝对路径。
    """
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # 跳过空行和注释行
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def get_bool(name: str, default: bool) -> bool:
    """
    从环境变量读取布尔值。

    支持的真值字符串："1", "true", "yes", "on"（不区分大小写）。
    其他任意值均视为 False。
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_list(name: str, default: list[str]) -> list[str]:
    """
    从环境变量读取逗号分隔的字符串列表。

    示例
    ----
    DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,example.com
    → ["127.0.0.1", "localhost", "example.com"]
    """
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


# ─────────────────────────────────────────────────────────────
# 路径与 SDK 配置
# ─────────────────────────────────────────────────────────────

# BASE_DIR 指向 backend/ 目录（即 manage.py 所在目录）。
BASE_DIR = Path(__file__).resolve().parent.parent

# 将项目根目录的 sdk/ 文件夹加入 Python 模块搜索路径，
# 以便导入 ikuai_sdk 等本地包。
SDK_DIR = BASE_DIR.parent / "sdk"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

# 加载 .env 文件中的环境变量（如果存在）。
load_dotenv(BASE_DIR / ".env")


# ─────────────────────────────────────────────────────────────
# 安全与调试配置
# ─────────────────────────────────────────────────────────────

# SECRET_KEY：用于会话签名、密码哈希等加密操作。
# 生产环境必须通过环境变量注入，严禁使用默认值。
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-_talxny^bzztza_-l-)qp13zikt6p^9m9ll_nd6^xx%4sr^ja&",
)

# DEBUG：开启后会显示详细错误页面，生产环境必须设为 False。
DEBUG = get_bool("DJANGO_DEBUG", True)

# ALLOWED_HOSTS：Django 只处理列表中的 Host 头，防止 HTTP Host 头攻击。
ALLOWED_HOSTS = get_list(
    "DJANGO_ALLOWED_HOSTS",
    ["127.0.0.1", "localhost"],
)

# CSRF_TRUSTED_ORIGINS：跨域 POST 请求时信任的源地址列表。
CSRF_TRUSTED_ORIGINS = get_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# 反向代理相关：当 Django 位于 Nginx/Traefik 等反向代理后方时，
# 通过这些设置正确识别原始客户端协议和端口。
USE_X_FORWARDED_HOST = get_bool("DJANGO_USE_X_FORWARDED_HOST", True)
USE_X_FORWARDED_PORT = get_bool("DJANGO_USE_X_FORWARDED_PORT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ─────────────────────────────────────────────────────────────
# 应用配置
# ─────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    # Django 内置应用
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # NetScope 业务应用（按功能模块拆分）
    'system',      # 系统健康检查
    'topology',    # 网络节点与路由拓扑
    'packets',     # 数据包事件生成与查询
    'ikuai',       # iKuai 路由器集成
]


# ─────────────────────────────────────────────────────────────
# 中间件配置
# ─────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 自定义 CORS 中间件：允许前端跨域访问（开发环境使用）。
    'config.middleware.SimpleCorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ─────────────────────────────────────────────────────────────
# URL 与模板配置
# ─────────────────────────────────────────────────────────────

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ─────────────────────────────────────────────────────────────
# 数据库配置
# ─────────────────────────────────────────────────────────────

# 默认使用 SQLite，适合开发和轻量部署。
# 生产环境可通过环境变量 DJANGO_DB_NAME 切换到 PostgreSQL/MySQL。
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DJANGO_DB_NAME', str(BASE_DIR / 'db.sqlite3')),
    }
}


# ─────────────────────────────────────────────────────────────
# 认证与密码校验
# ─────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ─────────────────────────────────────────────────────────────
# 国际化与时区
# ─────────────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ─────────────────────────────────────────────────────────────
# 静态文件与默认主键
# ─────────────────────────────────────────────────────────────

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
