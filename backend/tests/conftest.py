import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

LISTEN_PORTS = frozenset({22, 80, 443, 445, 8080, 8443, 5001})


@pytest.fixture(autouse=True)
def _disable_throttling(settings):
    """测试环境放宽 DRF 限流（保留 scope 注册避免 ImproperlyConfigured）。"""
    settings.REST_FRAMEWORK = {
        "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
        "DEFAULT_AUTHENTICATION_CLASSES": [],
        "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
        "EXCEPTION_HANDLER": "core.api_errors.exception_handler",
        "DEFAULT_THROTTLE_RATES": {"packets": "1000/s", "api": "1000/s"},
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "UNAUTHENTICATED_USER": None,
    }


@pytest.fixture
def ikuai_rows():
    """真实 iKuai conn 行样本（来自 sdk/demo_result.json 实测）。"""
    return json.loads((FIXTURES_DIR / "ikuai_rows.json").read_text(encoding="utf-8"))


@pytest.fixture
def terminal_rows():
    return json.loads((FIXTURES_DIR / "terminal_rows.json").read_text(encoding="utf-8"))
