"""
ikuai/models.py
===============
iKuai 路由器集成模块的数据模型。

定义 IKuaiSession 表，用于持久化每次尝试登录 iKuai 路由器时的请求参数、
上游响应状态、返回的会话信息（cookies、sess_key 等）。

设计目的
--------
- 审计追踪：记录谁在什么时间尝试连接了哪台路由器。
- 故障排查：保存上游原始响应，便于分析登录失败原因。
- 会话复用：后续可基于 sess_key 和 cookie_header 发起免密二次请求。
"""

from django.db import models


class IKuaiSession(models.Model):
    """
    iKuai 登录会话记录模型。

    字段说明
    --------
    router_url : str
        路由器管理地址（如 http://192.168.1.1）。
    login_url : str
        实际发起登录请求的 URL（SDK 内部可能拼接而成）。
    username : str
        登录用户名。
    request_mode : str
        SDK 内部使用的请求模式标识（如 'json'、'form' 等）。
    request_payload : dict
        发送给路由器的完整请求体（JSON 格式），便于审计。
    upstream_status : int
        HTTP 状态码（如 200、502），None 表示未收到响应。
    result_code : int
        iKuai 业务状态码（如 10000 表示成功，10001 表示密码错误）。
    result_message : str
        iKuai 返回的文本描述信息。
    cookies : dict
        路由器返回的 Set-Cookie 字典形式。
    sess_key : str
        iKuai 会话标识 key，后续请求可能需要携带。
    cookie_header : str
        可直接用于 HTTP 请求头的 Cookie 字符串。
    response_headers : dict
        上游返回的完整响应头。
    upstream_response : dict
        上游返回的完整响应体（JSON 格式）。
    created_at : datetime
        记录创建时间，自动维护。
    """

    router_url = models.TextField(db_index=True)
    login_url = models.TextField()
    username = models.CharField(max_length=255, db_index=True)
    request_mode = models.CharField(max_length=16)
    request_payload = models.JSONField(default=dict)
    upstream_status = models.PositiveIntegerField(null=True, blank=True)
    result_code = models.PositiveIntegerField(null=True, blank=True)
    result_message = models.CharField(max_length=255, blank=True)
    cookies = models.JSONField(default=dict)
    sess_key = models.CharField(max_length=255, blank=True, db_index=True)
    cookie_header = models.TextField(blank=True)
    response_headers = models.JSONField(default=dict)
    upstream_response = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 按时间倒序排列，最新会话排在最前。
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.router_url} [{self.username}]"
