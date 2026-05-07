"""
system/apps.py
==============
system 模块的 Django App 配置类。

Django 启动时会根据 INSTALLED_APPS 中注册的 AppConfig 类加载应用。
"""

from django.apps import AppConfig


class SystemConfig(AppConfig):
    """
    SystemConfig 是 system 应用的配置入口。

    属性说明
    --------
    default_auto_field : str
        默认使用 BigAutoField 作为模型主键类型，避免整数溢出。
    name : str
        应用标识名称，必须与 apps.py 所在目录名一致（即 'system'）。
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'system'
