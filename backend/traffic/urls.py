from django.urls import path

from .views import health_view, nodes_view, packet_view, routes_view


urlpatterns = [
    path("health", health_view),
    path("packet", packet_view),
    path("nodes", nodes_view),
    path("routes", routes_view),
]
