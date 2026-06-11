from django.urls import path
from . import views

urlpatterns = [
    path('soil-map-dashboard/',                         views.SoilMapDashboard.as_view(), name='soil-map-dashboard'),
    path('soil-map/<int:device_id>/',                   views.soil_map_view,              name='soil-map-view'),
    path('soil-map-admin/<int:device_id>/',             views.soil_map_admin_view,        name='soil-map-admin-view'),
    path('api/soil-map/data/<int:device_id>/',          views.list_soil_data,             name='soil-map-data'),
    path('api/soil-map/data/<int:device_id>/export/',   views.export_soil_data_csv,       name='soil-map-data-export'),
    path('api/soil-map/climate-zone/',                  views.classify_climate_zone,      name='soil-map-climate-zone'),
]