from django.urls import path
from . import views as v
from django.http import JsonResponse

def get_api_endpoints(request):
    """
    Return a list of all available API endpoints.
    """
    endpoints = []
    for url_pattern in urlpatterns:
        if hasattr(url_pattern, 'name') and url_pattern.name:
            endpoints.append(url_pattern.name)
    return JsonResponse({'data': endpoints})

urlpatterns = [
    # path('list/',  v.get_api_list, name = "home"),  
    path('add_location/',  v.add_location, name = "add_location"),  
    path('authenticate/',  v.authenticate, name = "authenticate"),  
    path('add_soil_data/',  v.add_soil_data, name = "add_soil_data"),  
    path('get_crops/',  v.get_crops, name = "get_crops"),  
    path('list_all_apis/', get_api_endpoints, name='list_all_apis'),

    path('add_data/',  v.add_soil_data_open, name = "add_data"),  

]

