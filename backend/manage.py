#!/usr/bin/env python
"""
manage.py
=========
Django 命令行管理工具入口。

提供 runserver、migrate、shell、createsuperuser 等所有 Django 内置管理命令。
开发环境直接运行：python manage.py runserver
"""

import os
import sys


def main():
    """
    设置 DJANGO_SETTINGS_MODULE 并执行 Django 命令行工具。

    如果 Django 未安装或虚拟环境未激活，会抛出 ImportError 并给出友好提示。
    """
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
