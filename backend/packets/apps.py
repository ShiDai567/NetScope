"""
packets/apps.py
===============
packets 模块的 Django App 配置类。

Django 启动时通过此类加载 packets 应用。
"""

from django.apps import AppConfig


class PacketsConfig(AppConfig):
    """
    PacketsConfig 是 packets 应用的配置入口。

    属性说明
    --------
    default_auto_field : str
        默认主键类型为 BigAutoField，防止大数据量下主键溢出。
    name : str
        应用包名，必须与目录名一致（'packets'）。
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'packets'
