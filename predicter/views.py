#from django.shortcuts import render

# Create your views here.
from django.http import HttpResponseBadRequest
from . ai_model.model import run_model
from agriapp.models import DeviseApis
from django.shortcuts import get_object_or_404, render

def get_recommendation(request):
    api_id   = request.GET.get("api_id")
    api_data = ''
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    try:
        api_id   = int(api_id)
        api_data = DeviseApis.objects.filter(pk=api_id).first()
    except ValueError:
        return HttpResponseBadRequest("Invalid 'api_id' parameter.")
    
    if api_data:
        # soil_nutrients = {'N': [118], 'P': [21], 'K': [34], 'temperature': [24.34986394], 'humidity':[64.79187265], 'ph': [7.287268394], 'rainfall': [119.63636055]};
        soil_nutrients = {'N': [api_data.nitrogen], 'P': [api_data.phosphorous], 'K': [api_data.potassium], 'temperature': [10], 'humidity':[10], 'ph': [api_data.ph], 'rainfall': [10]};
        result         = run_model(soil_nutrients)
    else:
        result = 'No data found for the provided api id.'
    return render(request, 'crop_recom_dashb.html', {'recommendation': result, 'soil_nutrients': api_data})
