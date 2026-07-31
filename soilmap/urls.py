from django.urls import path
from . import views

urlpatterns = [
    path('soil-map-dashboard/',                         views.SoilMapDashboard.as_view(), name='soil-map-dashboard'),
    path('soil-map/<int:device_id>/',                   views.soil_map_view,              name='soil-map-view'),
    path('soil-map-admin/<int:device_id>/',             views.soil_map_admin_view,        name='soil-map-admin-view'),
    path('api/soil-map/data/<int:device_id>/',          views.list_soil_data,             name='soil-map-data'),
    path('api/soil-map/data/<int:device_id>/export/',   views.export_soil_data_csv,       name='soil-map-data-export'),
    path('api/soil-map/climate-zone/',                  views.classify_climate_zone,      name='soil-map-climate-zone'),
    path('api/soil-map/analyze-polygon/',               views.analyze_polygon,            name='soil-map-analyze-polygon'),
    path('api/soil-map/crop-coverage-map/',             views.crop_coverage_map,          name='soil-map-crop-coverage'),
    path('api/soil-map/gee-health/',                    views.gee_health,                 name='soil-map-gee-health'),
    path('api/soil-map/fertilizer-options/',            views.fertilizer_options,         name='soil-map-fertilizer-options'),
    path('api/soil-map/fertilizer-recommendation/',     views.fertilizer_recommendation,  name='soil-map-fertilizer-recommendation'),
]