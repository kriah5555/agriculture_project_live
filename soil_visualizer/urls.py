from django.urls import path
from . import views

urlpatterns = [
    path('<int:device_id>/',                          views.dashboard_view,       name='soil-visualizer-dashboard'),
    path('<int:device_id>/readings/',                  views.api_device_readings, name='soil-visualizer-readings'),
    path('<int:device_id>/points/',                    views.api_all_points,      name='soil-visualizer-all-points'),
    path('<int:device_id>/plots/',                     views.api_plots,           name='soil-visualizer-plots'),
    path('<int:device_id>/plots/<int:plot_id>/',        views.api_plot_detail,     name='soil-visualizer-plot-detail'),
    path('<int:device_id>/plots/<int:plot_id>/points/', views.api_points,         name='soil-visualizer-points'),
    path('<int:device_id>/plots/<int:plot_id>/raster/', views.api_raster,         name='soil-visualizer-raster'),
    path('<int:device_id>/points/<int:point_id>/',      views.api_point_detail,    name='soil-visualizer-point-detail'),
]
