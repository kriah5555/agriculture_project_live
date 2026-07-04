import authapp
import agriapp
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from soilmap import views as soilmap_views
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/predict/', soilmap_views.predict_soil, name='soil-predict'),
    path('', include('agriapp.urls')),
    path('api/', include('devise_apis.urls')),
    path('api/mobile/', include('devise_apis.mobile_urls')),
    path('', include('reports.urls')),
    path('', include('versions.urls')),
    path('', include('soilmap.urls')),
    path('', include('leaflenz.urls')),
    path('pay/', include('razorpay_app.urls')),

    # ── Interactive API documentation (Swagger & ReDoc) ───────────────────────
    # OpenAPI schema JSON:  /api/schema/
    # Swagger UI:           /api/swagger/
    # ReDoc:                /api/redoc/
    path('api/schema/',  SpectacularAPIView.as_view(),                              name='api_schema'),
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='api_schema'),     name='api_swagger'),
    path('api/redoc/',   SpectacularRedocView.as_view(url_name='api_schema'),       name='api_redoc'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)