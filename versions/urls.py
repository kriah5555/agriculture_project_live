from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path('versions/', views.version_list, name='version_list'),
    path('versions/add/', views.version_create, name='version_add'),
    path('versions/<int:pk>/edit/', views.version_update, name='version_edit'),
    path('versions/<int:pk>/delete/', views.version_delete, name='version_delete'),

    # API endpoints
    path('versions/api/check-active-version/', api_views.check_active_version, name='api_check_active_version'),
    path('versions/api/download-version/', api_views.download_active_version, name='api_download_version'),

    # API documentation
    path('api/docs/', views.api_docs, name='api_docs'),
]
