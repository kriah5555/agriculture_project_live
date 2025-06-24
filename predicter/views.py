#from django.shortcuts import render

# Create your views here.
from django.http import HttpResponseBadRequest
from . ai_model.model import run_model
from agriapp.models import DeviseApis
from django.shortcuts import get_object_or_404, render

def get_recommendation(request):
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    try:
        api_id = int(api_id)
    except ValueError:
        return HttpResponseBadRequest("Invalid 'api_id' parameter.")
### Test:
# ------------- Comment or Remove below during deployment -------------
    #59,55,79,20.36720401,16.89574311,8.766128654,82.2545577,chickpea
    #soil_nutrients = {'N': [86], 'P': [36], 'K': [24], 'temperature': [26.54986394], 'humidity':[72.89187265], 'ph': [5.787268394], 'rainfall': [73.33636055]}
    #soil_nutrients = {'N': [59], 'P': [55], 'K': [79], 'temperature': [20.54986394], 'humidity':[16.89187265], 'ph': [8.787268394], 'rainfall': [82.33636055]}
    #118,21,34,24.38534644,64.72543073,7.234258375,119.6324109,coffee
    soil_nutrients = {'N': [118], 'P': [21], 'K': [34], 'temperature': [24.34986394], 'humidity':[64.79187265], 'ph': [7.287268394], 'rainfall': [119.63636055]}        
    result = run_model(soil_nutrients)
    return render(request, 'crop_recom_dashb.html', {'recommendation': result, 'soil_nutrients': soil_nutrients})
# ---------------------------------------------------------------------
#    if request.method == "POST":
#        data_instance = get_object_or_404(DeviseApis, id=api_id)
#---------- Remove below comment during deployment -------------
#            soil_nutrients = {
#                'N':[float(instance.nitrogen)],
#                'P':[float(instance.phosphorous)],
#                'K':[float(instance.potassium)],
#                'temperature':[float(instance.temperature)],
#                'humidity':[float(body['humidity'])],
#                'ph':[float(body['ph'])],
#                'rainfall':[float(body['rainfall'])]
#                }
#---------------------------------------------------------------            
    # This is how the above soil nutrient data will be sent to model
    # Example:
    # {'N': [86], 'P': [36], 'K': [24], 'temperature': [26.54986394], 'humidity':[72.89187265], 'ph': [5.787268394], 'rainfall': [73.33636055]}
    # The model is dependent on pandas module and it is required above example format type to be sent
#            result = run_modal(soil_nutrients)
#            return render({'recommendation': result})