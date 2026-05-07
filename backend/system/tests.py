"""
system/tests.py
===============
system 模块的单元测试文件。

目前该模块逻辑简单（仅一个健康检查视图），核心逻辑已在 Django 框架层充分测试。
后续如需扩展系统级功能（如磁盘空间检查、依赖服务探测等），可在此补充测试用例。
"""

from django.test import TestCase

# 占位：如需测试 health_view，可继承 TestCase 编写如下用例：
# class HealthViewTests(TestCase):
#     def test_health_returns_ok(self):
#         response = self.client.get("/api/health")
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response.json()["status"], "ok")
