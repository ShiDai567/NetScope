"""
ikuai/apps.py
=============
ikuai 模块的 Django App 配置类。

Django 启动时通过此类加载 ikuai 应用。
"""

from django.apps import AppConfig


class IKuaiConfig(AppConfig):
    """
    IKuaiConfig 是 ikuai 应用的配置入口。

    属性说明
    --------
    default_auto_field : str
        默认主键类型为 BigAutoField，防止大数据量下主键溢出。
    name : str
        应用包名，必须与目录名一致（'ikuai'）。
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ikuai'
