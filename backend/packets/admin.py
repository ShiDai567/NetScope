from django.contrib import admin

from .models import PacketEvent


@admin.register(PacketEvent)
class PacketEventAdmin(admin.ModelAdmin):
    list_display = ("packet_id", "protocol", "status", "payload_size", "event_timestamp")
    list_filter = ("protocol", "status")
    search_fields = ("packet_id",)
