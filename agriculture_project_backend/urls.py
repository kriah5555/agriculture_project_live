import authapp
import agriapp
import map
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('agriapp.urls')),
    path('', include('map.urls')),
    path('api/', include('devise_apis.urls')),
    path('api/mobile/', include('devise_apis.mobile_urls')),
    path('', include('predicter.urls')),
    path('', include('versions.urls')),
    path('pay/', include('razorpay_app.urls')),

    # ── Interactive API documentation (Swagger & ReDoc) ───────────────────────
    # OpenAPI schema JSON:  /api/schema/
    # Swagger UI:           /api/swagger/
    # ReDoc:                /api/redoc/
    path('api/schema/',  SpectacularAPIView.as_view(),                              name='api_schema'),
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='api_schema'),     name='api_swagger'),
    path('api/redoc/',   SpectacularRedocView.as_view(url_name='api_schema'),       name='api_redoc'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)