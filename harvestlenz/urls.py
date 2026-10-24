from django.urls import path
from . import views

urlpatterns = [
    path('harvestlenz-dashboard/',             views.HarvestLenzDashboard.as_view(), name='harvestlenz-dashboard'),
    path('harvestlenz/<int:device_id>/',       views.harvestlenz_scan_view,          name='harvestlenz-scan-view'),
    path('harvestlenz-admin/<int:device_id>/', views.harvestlenz_admin_scan_view,    name='harvestlenz-admin-scan-view'),
]
