#!/usr/bin/env python
"""Django 管理入口。默认使用 dev 配置，可用 DJANGO_SETTINGS_MODULE 覆盖。"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("未找到 Django，请先激活虚拟环境并安装 requirements.txt") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
