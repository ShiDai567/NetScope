"""network 应用路由。"""

from django.urls import path

from network import views

urlpatterns = [
    # v1：与前端 client.ts 契约逐字节兼容（doc §10.2）
    path("mode", views.ModeView.as_view(), name="mode"),
    path("packets", views.PacketsView.as_view(), name="packets"),
    path("stats", views.StatsView.as_view(), name="stats"),
    path("devices", views.DevicesView.as_view(), name="devices"),
    path("nodes", views.NodesView.as_view(), name="nodes"),
    path("health", views.HealthView.as_view(), name="health"),
    # v2 扩展（doc §10.3）
    path("network/countries", views.RankingView.as_view(dim="countries"), name="v2-countries"),
    path("network/protocols", views.RankingView.as_view(dim="protocols"), name="v2-protocols"),
    path(
        "network/applications",
        views.RankingView.as_view(dim="applications"),
        name="v2-applications",
    ),
    path("network/ports", views.RankingView.as_view(dim="ports"), name="v2-ports"),
    path("network/ips", views.RankingView.as_view(dim="ips"), name="v2-ips"),
    path("network/connections", views.ConnectionsView.as_view(), name="v2-connections"),
    path("network/events", views.EventsView.as_view(), name="v2-events"),
    path("network/history", views.HistoryView.as_view(), name="v2-history"),
]
