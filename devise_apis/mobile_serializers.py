"""
Mobile API serializers for ArkaShine platform.
All serializers for the /api/mobile/ endpoints live here.
"""
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from agriapp.models import (
    Devise, DeviseApis, DeviseApisFields, DeviseLocation,
    APICountThreshold, DEVICE_NAMES,
)


# ── Auth ─────────────────────────────────────────────────────────────────────

class MobileTokenObtainSerializer(TokenObtainPairSerializer):
    """JWT login serializer — adds user info to token response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = {
            'id'        : user.id,
            'username'  : user.username,
            'email'     : user.email,
            'full_name' : user.get_full_name(),
        }
        return data


# ── Device types ─────────────────────────────────────────────────────────────

class DeviceTypeSerializer(serializers.Serializer):
    """One entry per device type; locked=True when user owns no device of that type."""
    type_key    = serializers.CharField()
    type_name   = serializers.CharField()
    locked      = serializers.BooleanField()
    device_count = serializers.IntegerField()


# ── Devices ──────────────────────────────────────────────────────────────────

class DeviceLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviseLocation
        fields = ['latitude', 'longitude']


class DeviceListSerializer(serializers.ModelSerializer):
    """Compact device list for mobile."""
    type_name    = serializers.SerializerMethodField()
    api_count    = serializers.SerializerMethodField()
    has_location = serializers.SerializerMethodField()

    class Meta:
        model  = Devise
        fields = [
            'id', 'name', 'serial_no', 'devise_id', 'devise_type', 'type_name',
            'address1', 'address2', 'purchase_date', 'land',
            'api_count', 'has_location', 'created_at',
        ]

    def get_type_name(self, obj):
        return DEVICE_NAMES.get(obj.devise_type, obj.devise_type)

    def get_api_count(self, obj):
        if obj.devise_type == 'soilsaathi':
            return DeviseApis.objects.filter(device=obj).count()
        return DeviseApisFields.objects.filter(device=obj).count()

    def get_has_location(self, obj):
        return DeviseLocation.objects.filter(devise=obj).exists()


class DeviceDetailSerializer(DeviceListSerializer):
    """Full device details including location and threshold."""
    location  = serializers.SerializerMethodField()
    threshold = serializers.SerializerMethodField()

    class Meta(DeviceListSerializer.Meta):
        fields = DeviceListSerializer.Meta.fields + [
            'email', 'phone', 'chipset_no', 'warrenty',
            'amount_paid', 'balance_amount', 'time_of_sale',
            'location', 'threshold',
        ]

    def get_location(self, obj):
        loc = DeviseLocation.objects.filter(devise=obj).first()
        return DeviceLocationSerializer(loc).data if loc else None

    def get_threshold(self, obj):
        t = APICountThreshold.objects.filter(devise=obj).first()
        if not t:
            return None
        return {'red': t.red, 'orange': t.orange, 'blue': t.blue, 'green': t.green}


# ── Soil Saathi (SoiLENZ) API call ───────────────────────────────────────────

class SoilSaathiReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviseApis
        fields = [
            'id', 'area_name', 'tag',
            'nitrogen', 'phosphorous', 'potassium',
            'calcium', 'magnesium', 'sulphur',
            'zinc', 'manganese', 'iron', 'copper', 'boron',
            'ph', 'ec', 'oc', 'electrical_conduction',
            'crop_type', 'latitude', 'longitude', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SoilSaathiReadingCreateSerializer(serializers.ModelSerializer):
    """Used when creating a new reading for a SoiLENZ device."""
    class Meta:
        model  = DeviseApis
        fields = [
            'area_name', 'tag',
            'nitrogen', 'phosphorous', 'potassium',
            'calcium', 'magnesium', 'sulphur',
            'zinc', 'manganese', 'iron', 'copper', 'boron',
            'ph', 'ec', 'oc', 'electrical_conduction',
            'crop_type', 'latitude', 'longitude',
        ]


# ── AtmoSense / SoilLIFE (DeviseApisFields) API call ─────────────────────────

FIELD_LABELS = {
    'atmo_sense': {
        'field1': 'Soil Temp (°C)',     'field2': 'Soil Moisture (%)',
        'field3': 'Atmos Temp (°C)',    'field4': 'Atmos Humidity (%)',
        'field5': 'Light Intensity (lux)',
    },
    'soil_life': {
        'field1': 'CO₂ (ppm)',          'field2': 'Methane (ppm)',
        'field3': 'Ammonia (ppm)',       'field4': 'Nitrous Oxide (ppm)',
        'field5': 'Temperature (°C)',    'field6': 'Humidity (%)',
        'field7': 'Atmos Pressure (hPa)','field8': 'Microbial Content (%)',
    },
}


class FieldsReadingSerializer(serializers.ModelSerializer):
    labeled_fields = serializers.SerializerMethodField()

    class Meta:
        model  = DeviseApisFields
        fields = [
            'id', 'tag', 'image_path', 'crop_type', 'created_at',
            'field1', 'field2', 'field3', 'field4', 'field5',
            'field6', 'field7', 'field8',
            'labeled_fields',
        ]
        read_only_fields = ['id', 'created_at', 'labeled_fields']

    def get_labeled_fields(self, obj):
        labels = FIELD_LABELS.get(obj.device.devise_type, {})
        return {label: getattr(obj, key, 0) for key, label in labels.items()}


class FieldsReadingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviseApisFields
        fields = [
            'tag', 'image_path', 'crop_type',
            'field1', 'field2', 'field3', 'field4', 'field5',
            'field6', 'field7', 'field8',
        ]


# ── Threshold ─────────────────────────────────────────────────────────────────

class ThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model  = APICountThreshold
        fields = ['red', 'orange', 'blue', 'green']


# ── Recommendation (returned by existing FertilizerCalculation logic) ─────────

class RecommendationSerializer(serializers.Serializer):
    crop         = serializers.CharField(allow_blank=True)
    nitrogen     = serializers.FloatField()
    phosphorous  = serializers.FloatField()
    potassium    = serializers.FloatField()
    message      = serializers.CharField(allow_blank=True)