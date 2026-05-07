"""
topology/tests.py
=================
topology 模块的单元测试文件。

当前模块以数据驱动为主，核心逻辑为简单的查询和序列化。
后续如需测试路由约束（如 client->client 禁止）、节点坐标计算等，可在此补充用例。
"""

from django.test import TestCase

# 占位示例：
# class NetworkRouteConstraintTests(TestCase):
#     def test_client_to_client_route_is_blocked(self):
#         """验证 client -> client 路由在 clean() 阶段被拦截。"""
#         pass
