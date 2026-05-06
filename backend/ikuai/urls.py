from django.urls import path

from .views import ikuai_login_view, ikuai_sessions_view

urlpatterns = [
    path("ikuai/login", ikuai_login_view),
    path("ikuai/sessions", ikuai_sessions_view),
]
