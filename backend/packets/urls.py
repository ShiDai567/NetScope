from django.urls import path

from .views import packet_view

urlpatterns = [
    path("packet", packet_view),
]
