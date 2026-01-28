from rest_framework import serializers
from .models import AppVersion

class AppVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersion
        fields = ['id', 'version', 'zip_file', 'is_active', 'created_at']
