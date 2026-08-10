# TEMPORARY FEATURE — see the module docstring in channel_data_views.py for what
# this is and how to remove it later.
from django.urls import path
from . import channel_data_views as v

urlpatterns = [
    path('',                        v.channel_data_devices, name='channel-data-devices'),
    path('device/<int:pk>/',        v.channel_data_list,    name='channel-data-list'),
    path('device/<int:pk>/export/', v.channel_data_export,  name='channel-data-export'),
    path('reading/<int:pk>/',       v.channel_data_detail,  name='channel-data-detail'),
]
