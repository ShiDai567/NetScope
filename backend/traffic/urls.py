from django.urls import path

from . import views

app_name = "traffic"

urlpatterns = [
    path("health", views.health, name="health"),
    path("packets", views.packets, name="packets"),
    path("history", views.history, name="history"),
    path("devices", views.devices, name="devices"),
    path("nodes", views.nodes, name="nodes"),
    path("stats", views.stats, name="stats"),
    path("mode", views.mode, name="mode"),
    path("ikuai/connect", views.ikuai_connect, name="ikuai-connect"),
    path("ikuai/disconnect", views.ikuai_disconnect, name="ikuai-disconnect"),
]
