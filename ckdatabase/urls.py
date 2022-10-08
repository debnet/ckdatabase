from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = []

# Debug
if settings.DEBUG:
    # Static and media files
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Django Debug Toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns += [path("debug/", include(debug_toolbar.urls))]

urlpatterns += [
    path('api/auth/', include('rest_framework.urls', namespace='rest_framework')),
    path("api/", include("database.api", namespace="database-api")),
    path("common/", include("common.urls", namespace="common")),
    path("api/common/", include("common.api.urls", namespace="common-api")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("", admin.site.urls),
]
