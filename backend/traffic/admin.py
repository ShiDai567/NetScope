from django.contrib import admin

from .models import NetworkNode, NetworkRoute, PacketEvent


@admin.register(NetworkNode)
class NetworkNodeAdmin(admin.ModelAdmin):
    list_display = ("node_id", "name", "ip_address", "node_type", "is_active")
    list_filter = ("node_type", "is_active")
    search_fields = ("node_id", "name", "ip_address")


@admin.register(NetworkRoute)
class NetworkRouteAdmin(admin.ModelAdmin):
    list_display = ("id", "source_node", "destination_node", "is_active")
    list_filter = ("is_active",)


@admin.register(PacketEvent)
class PacketEventAdmin(admin.ModelAdmin):
    list_display = ("packet_id", "protocol", "status", "payload_size", "event_timestamp")
    list_filter = ("protocol", "status")
    search_fields = ("packet_id",)

# Register your models here.
