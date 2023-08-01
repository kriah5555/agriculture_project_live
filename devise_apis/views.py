from django.shortcuts import render
from .serializers import DeviseApiSerializer
from agriapp.models import DeviseApis, Devise, DeviseLocation, ColumnData
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from agriapp import UserFuncrtions, FertilizerCalculation as f
from .encryption_utils import encrypt_device_id, decrypt_device_id

# Create your views here.

@api_view(['GET', 'POST'])
def get_api_list(request):
    all_apis   = DeviseApis.objects.all()
    serializer = DeviseApiSerializer(all_apis, many=True)
    return JsonResponse({'data':serializer.data})

@api_view(['POST'])
def get_devise_by_devise_id(request):
    try:
        if request.POST:
            devise_id = request.POST['devise_id']
            if devise_id:
                devise = Devise.objects.filter(devise_id=devise_id).first()
                return Response({'device_key' : encrypt_device_id(devise.pk)}, status.HTTP_200_OK)
            else:
                return Response({'message' : 'Please send valid devse id'}, status.HTTP_400_BAD_REQUEST)
        else:
                return Response({'message' :serializer.errors}, status.HTTP_400_BAD_REQUEST)

    except  Exception as e:
        return Response({'message' : "Something went wrong while fetching data please check the parameters"}, status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def add_location(request):
    try:
        if 'devise' in request.POST and 'latitude' in request.POST and 'longitude' in request.POST:
            device_key =  request.POST['device_key']
            latitude   =  request.POST['latitude']
            longitude  =  request.POST['longitude']
            if devise and longitude and longitude:
                location = DeviseLocation.objects.filter(devise__pk = decrypt_device_id(device_key))
                if location:
                    location.update(latitude= latitude, longitude= longitude)
                else :
                    DeviseLocation.objects,Create(devise =  devise, latitude =  latitude, longitude =  longitude)
                return Response({'message' : "Location updated successfully"}, status=status.HTTP_200_OK)
            else :
             return Response({'message' : "Please pass all parameters"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'message' : "Please pass all parameters"}, status=status.HTTP_400_BAD_REQUEST)
    except  Exception as e:
        return Response({'message' : "Something went wrong while fetching data please check the parameters"}, status.HTTP_400_BAD_REQUEST)  

@api_view(['POST'])
def add_soil_data(request):
    try:
        modified_data           = request.data.copy()
        device                  = decrypt_device_id(modified_data['device_key'])
        modified_data['device'] = device
        serializer              = DeviseApiSerializer(data = request.data)
        if serializer.is_valid():
            serializer.save()
            api_id         = serializer.data['id']
            dynamic_fields = UserFuncrtions.get_all_dynamic_fields()
            if (dynamic_fields):
                for dynamic_field in dynamic_fields:
                    field_name = dynamic_field.field_name
                    if field_name in request.data.keys():
                        ColumnData.objects.create(api = DeviseApis.objects.get(pk=api_id), field = dynamic_field, field_value = request.data[field_name])
            return Response({'message' : 'Soil data added successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'errors' : serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except  Exception as e:
        return Response({'message' : "Something went wrong while fetching data please check the parameters"}, status.HTTP_400_BAD_REQUEST)  

@api_view(['POST'])
def get_crops(request):
    try:
        return Response({'message' : 'available crops', 'crops' : f.get_crop_list()}, status=status.HTTP_200_OK)
    except  Exception as e:
        return Response({'message' : "Something went wrong while fetching data please check the parameters"}, status.HTTP_400_BAD_REQUEST)        

        
