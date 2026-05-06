from django.urls import path

from .views import nodes_view, routes_view

urlpatterns = [
    path("nodes", nodes_view),
    path("routes", routes_view),
]
