from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('system.urls')),
    path('api/', include('topology.urls')),
    path('api/', include('packets.urls')),
    path('api/', include('ikuai.urls')),
]
