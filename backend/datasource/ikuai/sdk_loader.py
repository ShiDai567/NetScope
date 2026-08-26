"""iKuai SDK 导入助手与统一异常。

sdk/ 位于仓库根目录而非 backend/ 内，通过 sys.path 动态引入。
HTTPS 自签面板：IKUAI_SSL_VERIFY=0 时安装免校验 opener。
"""

import ssl
import sys
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SDK_DIR = _REPO_ROOT / "sdk"


class GatewayError(RuntimeError):
    """数据源调用失败（网络/认证/响应异常）。"""


class BackoffError(GatewayError):
    """处于退避期，调用被快速拒绝。"""


def import_ikuai_sdk():
    """导入仓库根目录 sdk/ 下的 iKuai SDK；失败抛 GatewayError。"""
    try:
        import ikuai_sdk  # noqa: F401

        return ikuai_sdk
    except ImportError:
        pass
    if _SDK_DIR.is_dir() and str(_SDK_DIR) not in sys.path:
        sys.path.insert(0, str(_SDK_DIR))
    try:
        import ikuai_sdk  # noqa: F401
    except ImportError as exc:
        raise GatewayError(f"无法加载 iKuai SDK（sdk/ 目录缺失）: {exc}") from exc
    return ikuai_sdk


def install_ssl_bypass(verify: bool) -> None:
    """verify=False 时全局安装跳过证书校验的 HTTPS opener（自签面板用）。"""
    if verify:
        return
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=context)))
