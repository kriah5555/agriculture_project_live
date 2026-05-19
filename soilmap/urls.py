from django.urls import path
from . import views

urlpatterns = [
    path('soil-map-dashboard/',         views.SoilMapDashboard.as_view(), name='soil-map-dashboard'),
    path('soil-map/<int:device_id>/',   views.soil_map_view,              name='soil-map-view'),
    path('soil-map-admin/<int:device_id>/', views.soil_map_admin_view,    name='soil-map-admin-view'),
]