from django.shortcuts import render
from .serializers import DeviseApiSerializer, DeviseFieldsApiSerializer
from agriapp.models import DeviseApis, Devise, DeviseLocation, ColumnData, DeviseApisFields
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from agriapp import UserFuncrtions, FertilizerCalculation as f
from .encryption_utils import encrypt_device_id, decrypt_device_id
from django.contrib import auth
import base64
from map.views import get_marker_color
import copy
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile

def encode_to_base64(value):
    """
    Encode a value to base64.
    
    :param value: The value to encode.
    :return: The base64-encoded string.
    """
    encoded_bytes = base64.b64encode(str(value).encode('utf-8'))
    return encoded_bytes.decode('utf-8')

def decode_from_base64(encoded_string):
    """
    Decode a base64-encoded string to its original value.
    
    :param encoded_string: The base64-encoded string.
    :param data_type: The data type to convert the decoded value to (str or int).
    :return: The decoded value.
    """
    decoded_bytes = base64.b64decode(encoded_string)

    # If you want to convert the bytes back to a string (assuming it was originally encoded from a string)
    original_string = decoded_bytes.decode('utf-8')

    # If you want to convert the bytes back to an integer (assuming it was originally encoded from an integer)
    return int(decoded_bytes)

# Create your views here.

@api_view(['GET', 'POST'])
def get_api_list(request):
    all_apis   = DeviseApis.objects.all()
    serializer = DeviseApiSerializer(all_apis, many=True)
    return JsonResponse({'data':serializer.data})

# @api_view(['POST'])
# def authenticate(request):
#     try:
#         if request.POST:
#             devise_id = request.POST['devise_id']
#             if devise_id:
#                 devise = Devise.objects.filter(devise_id=devise_id).first()
#                 return Response({'device_key' : encrypt_device_id(devise.pk)}, status.HTTP_200_OK)
#             else:
#                 return Response({'message' : 'Please send valid devse id'}, status.HTTP_400_BAD_REQUEST)
#         else:
#                 return Response({'message' :serializer.errors}, status.HTTP_400_BAD_REQUEST)

#     except  Exception as e:
#         return Response({'message' : "Something went wrong while fetching data please check the parameters"}, status.HTTP_400_BAD_REQUEST)    

@api_view(['POST'])
def authenticate(request):
    try:
        if request.method == 'POST':
            devise_id = request.POST['devise_id']
            password  = request.POST['password']
            user      = auth.authenticate(username=devise_id, password=password)
            if user is not None:
                devise = Devise.objects.filter(devise_id=devise_id).first()

                # Encrypt the device key
                device_key_encoded = encode_to_base64(devise.pk)
                return Response({'device_key': device_key_encoded}, status.HTTP_200_OK)
            else:
                return Response({'message': 'Please send a valid devise_id or password'}, status=401)
        else:
            return Response({'message': 'Invalid request method'}, status=400)

    except Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)
   
@api_view(['POST'])
def add_location(request):
    try:
        if 'device_key' in request.POST and 'latitude' in request.POST and 'longitude' in request.POST:
            device_key =  request.POST['device_key']
            latitude   =  request.POST['latitude']
            longitude  =  request.POST['longitude']
            device_key = decode_from_base64(request.POST['device_key'])
            if device_key and longitude and longitude:
                 # Check if the Devise object with the given device_key exists
                devise = Devise.objects.filter(pk=device_key).first()
                if devise:
                    # Update the location if the devise exists
                    location, created = DeviseLocation.objects.get_or_create(devise=devise)
                    location.latitude = latitude
                    location.longitude = longitude
                    location.save()
                    return Response({'message': "Location updated successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response({'message': "Inaveld Devise Key"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'message' : "Please pass all parameters"}, status=status.HTTP_400_BAD_REQUEST)
    except  Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def add_soil_data(request):
    try:
        # Get the device_key from the POST data and decode if needed
        device_key = request.POST.get('device_key', '')
        devise_pk = decode_from_base64(device_key)


        devise     = Devise.objects.get(pk = devise_pk)
        api_limit  = get_marker_color(devise)
        if (api_limit == 'red'):
            return Response({'message': 'You have exceeded the limit of api calls please contact the admin for more clarification'}, status=status.HTTP_200_OK)


        # Modify request.data to include the Devise object
        modified_data = request.data.copy()
        modified_data['device'] = devise_pk

        serializer = DeviseApiSerializer(data=modified_data)

        if serializer.is_valid():
            serializer.save()
            api_id = serializer.data['id']
            dynamic_fields = UserFuncrtions.get_all_dynamic_fields()
            if dynamic_fields:
                for dynamic_field in dynamic_fields:
                    field_name = dynamic_field.field_name
                    if field_name in modified_data:
                        ColumnData.objects.create(
                            api=DeviseApis.objects.get(pk=api_id),
                            field=dynamic_field,
                            field_value=modified_data[field_name]
                        )

            api        = DeviseApis.objects.get(pk=api_id)
            crops_data = f.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
            return Response({'message': 'Soil data added successfully', 'data':crops_data }, status=status.HTTP_200_OK)
        else:
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def add_atmos_sense_data(request):
    try:
        # uploaded_file = request.FILES.get('file')
        # file_url      = ''
        # if uploaded_file:
        #     fs = FileSystemStorage()
        #     filename = fs.save(uploaded_file.name, uploaded_file)
        #     file_url = fs.url(filename)
        # Get the device_key from the POST data and decode if needed

        file_data_base64 = request.data.get('file_data', '')
        file_url = ''
        if file_data_base64:
            try:
                file_data = base64.b64decode(file_data_base64)
                # Save the decoded data as a file using Django's FileSystemStorage
                fs           = FileSystemStorage()
                content_file = ContentFile(file_data)
                file_name    = fs.save('img.jpg', content_file)
                file_url     = fs.url(file_name)
            except base64.binascii.Error as e:
                return Response({'error': f'Invalid base64-encoded data: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Modify request.data to include the Devise object
        random_devise = Devise.objects.order_by('?').first()
        if not random_devise:
            return Response({'message': 'No Devise found in the database.'}, status=status.HTTP_404_NOT_FOUND)
            
        modified_data               = request.data.copy()
        modified_data['image_path'] = file_url
        modified_data['device']     = random_devise.pk

        serializer = DeviseFieldsApiSerializer(data=modified_data)

        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'AtmosSense data added successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def get_crops(request):
    try:
        return Response({'message' : 'available crops', 'data' : f.get_crop_list(True)}, status=status.HTTP_200_OK)
    except  Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def add_soil_data_open(request):
    try:
        device_id = request.GET.get('devise_id', '')
        devise = Devise.objects.filter(devise_id=device_id).first()
        if (not devise):
            return Response({'message': 'Invslid devise ID'}, status=status.HTTP_400_BAD_REQUEST)

        api_limit  = get_marker_color(devise)
        if (api_limit == 'red'):
            return Response({'message': 'You have exceeded the limit of api calls please contact the admin for more clarification'}, status=status.HTTP_400_BAD_REQUEST)


        # Modify request.data to include the Devise object
        modified_data = copy.deepcopy(request.GET)
        modified_data['device'] = devise.pk

        
        serializer = DeviseApiSerializer(data=modified_data)

        if serializer.is_valid():
            serializer.save()
            api_id = serializer.data['id']
            dynamic_fields = UserFuncrtions.get_all_dynamic_fields()
            if dynamic_fields:
                for dynamic_field in dynamic_fields:
                    field_name = dynamic_field.field_name
                    if field_name in modified_data:
                        ColumnData.objects.create(
                            api=DeviseApis.objects.get(pk=api_id),
                            field=dynamic_field,
                            field_value=modified_data[field_name]
                        )

            api        = DeviseApis.objects.get(pk=api_id)
            crops_data = f.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
            return Response({'message': 'Soil data added successfully', 'data':crops_data }, status=status.HTTP_200_OK)
        else:
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def add_location_data(request):
    try:
        if all(key in request.GET for key in ['devise_id', 'latitude', 'longitude']):
            devise_id  =  request.GET['devise_id']
            latitude   =  request.GET['latitude']
            longitude  =  request.GET['longitude']

             # Validate latitude and longitude
            if not (latitude and longitude):
                return Response({'message': "Latitude and longitude are required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                
                # Add additional validation for latitude and longitude range if needed
                if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                    return Response({'message': "Invalid latitude or longitude values"}, status=status.HTTP_400_BAD_REQUEST)
                
            except ValueError:
                return Response({'message': "Invalid latitude or longitude format"}, status=status.HTTP_400_BAD_REQUEST)

                
            if devise_id and longitude and longitude:
                 # Check if the Devise object with the given device_key exists
                devise = Devise.objects.filter(devise_id=devise_id).first()
                if devise:
                    # Update the location if the devise exists
                    location, created = DeviseLocation.objects.get_or_create(devise=devise)
                    location.latitude = latitude
                    location.longitude = longitude
                    location.save()
                    return Response({'message': "Location updated successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response({'message': "Inaveld Devise id"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'message' : "Please pass all parameters"}, status=status.HTTP_400_BAD_REQUEST)
    except  Exception as e:
        error_message = f'Something went wrong: {str(e)}'
        return Response({'message': error_message}, status=status.HTTP_400_BAD_REQUEST)