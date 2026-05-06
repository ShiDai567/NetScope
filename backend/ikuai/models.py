from django.db import models


class IKuaiSession(models.Model):
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
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.router_url} [{self.username}]"
