from django.shortcuts import render
import folium as fol
# import geocoder as geo
import os
from django.contrib.auth.decorators import login_required
from agriapp.models import DeviseLocation, Devise, DeviseApis, APICountThreshold, DeviseApisFields

# Create your views here.

# @login_required(login_url='/admin-login/')    
# def map_view(request, **kwargs):
#     location  = geo.osm('IN')
#     latitude   = location.lat
#     longitude = location.lng
#     country   = location.country
#     map = fol.Map(location=[latitude, longitude], zoom_start = 6)
#     fol.Marker([latitude, longitude], tooltip = f'India', popup = f'{country}', icon=fol.Icon(color="blue"),).add_to(map)
#     if kwargs:login1
#         devise_id = kwargs['pk']
#         location = DeviseLocation.objects.filter(status=True, devise__pk = devise_id)
#         if location:
#             latitude  = location.latitude
#             longitude = location.longitude
#             map       = fol.Map(location=[latitude, longitude], zoom_start = 6)
#             fol.Marker([latitude, longitude], tooltip = f'Click for details', popup = f'{location.device.name}', icon=fol.Icon(color="blue"),).add_to(map)
        
#     # Create map objects
    
#     # Htmp representation of teh map object
#     map = map._repr_html_()
#     context = {
#         'map' : map
#     }
#     return render(request, 'map/map_index.html', context = context)

def get_marker_color(devise):
    if devise:
        api_thresholds = APICountThreshold.objects.filter(devise = devise).first()
        if devise.devise_type == 'soilsaathi':
            api_count = len(DeviseApis.objects.filter(device = devise))
        else :
            api_count = len(DeviseApisFields.objects.filter(device = devise))
        color = 'pink'

        if api_thresholds:
            if api_count >= api_thresholds.red:
                color = 'red'
            if api_count >= api_thresholds.orange and api_count <= api_thresholds.red:
                color = 'orange'
            if api_count >= api_thresholds.blue and api_count <= api_thresholds.orange:
                color = 'blue'
            if api_count >= api_thresholds.green and api_count <= api_thresholds.blue:
                color = 'green'
            if api_count < api_thresholds.green:
                color = 'pink'
    return color

@login_required(login_url='/admin-login/')    
def map_view(request, **kwargs):
    zoom = 0
    pk = ''
    
    if request.method == 'POST':
        pk = request.POST['pk']
    elif (kwargs):
        pk = kwargs['pk']
        
    if pk:
        devises = DeviseLocation.objects.filter(devise__pk = pk)
        zoom    = 19
    else :
        devises = DeviseLocation.objects.all()

    display_devises_location = dict()
    for devices_location in devises:
        display_devises_location[devices_location.pk] = {
            'name' : devices_location.devise.name,
            'latitude' : devices_location.latitude,
            'longitude' : devices_location.longitude,
            'devise_pk' : devices_location.devise.pk,
            'color' : get_marker_color(devices_location.devise)
        }
        
        # icon: { url: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png" } # icon color for map
    
    context = {
        'filter_devise_list' : DeviseLocation.objects.all(),
        'devises' : display_devises_location,
        'zoom'    : zoom,
    }
    return render(request, 'map/map_index.html', context=context)


