"""
config/wsgi.py
==============
NetScope 后端项目的 WSGI 配置入口。

WSGI（Web Server Gateway Interface）是 Python Web 应用与 Web 服务器之间的标准接口。
本文件暴露名为 ``application`` 的模块级变量，供 Gunicorn、uWSGI 等生产服务器加载。

部署参考
--------
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# 设置默认的 Django 配置模块路径。
# 生产环境启动命令示例：gunicorn config.wsgi:application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
