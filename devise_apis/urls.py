from django.urls import path
from . import views as v
from django.http import JsonResponse
from soilmap import views as sm_views

urlpatterns = [
    path('add_location/',             v.add_location,          name='add_location'),
    path('authenticate/',             v.authenticate,          name='authenticate'),
    path('add_soil_data/',            v.add_soil_data,         name='add_soil_data'),
    path('get_crops/',                v.get_crops,             name='get_crops'),
    path('add_data/',                 v.add_soil_data_open,    name='add_data'),
    path('add_location_data/',        v.add_location_data,     name='add_location_data'),
    path('create-atmos-sense-data/',  v.add_atmos_sense_data,  name='add-atmos-sense-data'),
    path('create-soil-life-data/',    v.add_soil_life_data,    name='add-soil-life-data'),
    path('list_all_apis/',            v.list_all_apis,         name='list_all_apis'),
    # SoilMap API (mounted here so /api/predict/ resolves correctly)
    path('predict/',                              sm_views.predict_soil,    name='predict-soil'),
    path('soil-map/upload/<int:device_id>/',      sm_views.upload_soil_data, name='upload-soil-data'),
]