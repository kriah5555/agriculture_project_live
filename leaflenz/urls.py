from django.urls import path
from . import views

urlpatterns = [
    path('leaflenz-dashboard/',        views.LeafLenzDashboard.as_view(),  name='leaflenz-dashboard'),
    path('leaflenz/<int:device_id>/',       views.leaflenz_scan_view,       name='leaflenz-scan-view'),
    path('leaflenz-admin/<int:device_id>/', views.leaflenz_admin_scan_view, name='leaflenz-admin-scan-view'),
]
