from rest_framework import serializers
from agriapp.models import DeviseApis, DeviseLocation, DeviseApisFields
from rest_framework.decorators import api_view

class DeviseApiSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviseApis
        fields = '__all__'

class DeviseFieldsApiSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviseApisFields
        fields = '__all__'

# class DeviseLocationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = DeviseLocation
#         fields = (
#             'devise',
#             'latitude',
#             'longitude',
#         )
        