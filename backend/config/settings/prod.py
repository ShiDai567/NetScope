"""生产环境：强制安全基线。部署时 DJANGO_SETTINGS_MODULE=config.settings.prod。"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403,F405

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("dev-insecure"):  # noqa: F405
    raise ImproperlyConfigured("生产环境必须通过 DJANGO_SECRET_KEY 注入强随机密钥")

SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
