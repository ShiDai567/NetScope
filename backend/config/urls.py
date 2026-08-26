"""根 URL：/api/ 业务接口 + OpenAPI schema。"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

handler404 = "core.api_errors.handler404"
handler500 = "core.api_errors.handler500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("network.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
