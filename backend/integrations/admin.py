from django.contrib import admin

from .models import IKuaiSession


@admin.register(IKuaiSession)
class IKuaiSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "router_url", "username", "request_mode", "result_code", "created_at")
    list_filter = ("request_mode", "result_code", "created_at")
    search_fields = ("router_url", "username", "sess_key")

# Register your models here.
