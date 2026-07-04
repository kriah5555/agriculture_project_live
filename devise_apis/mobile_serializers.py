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
    ATMO_SENSE_FIELDS, SOIL_LIFE_FIELDS, PH_BOTTLE_FIELDS, SOIL_SAATHI_FIELDS, SOIL_MAP_FIELDS,
    LEAFLENZ_FIELDS,
)
from agri_ai.leaf import parse_class_label, get_disease_details


# ── Auth ─────────────────────────────────────────────────────────────────────

class MobileTokenObtainSerializer(TokenObtainPairSerializer):
    """JWT login serializer — adds full user + profile info to token response."""

    def validate(self, attrs):
        data    = super().validate(attrs)
        user    = self.user
        profile = getattr(user, 'profile', None)
        data['user'] = _build_user_dict(user, profile)
        return data


def _build_user_dict(user, profile=None):
    """Build the full user info dict used in both login and profile responses."""
    if profile is None:
        profile = getattr(user, 'profile', None)
    return {
        'id'           : user.id,
        'username'     : user.username,
        'email'        : user.email,
        'first_name'   : user.first_name,
        'last_name'    : user.last_name,
        'full_name'    : user.get_full_name(),
        'is_superuser' : user.is_superuser,
        'is_staff'     : user.is_staff,
        'is_active'    : user.is_active,
        'date_joined'  : user.date_joined.isoformat() if user.date_joined else None,
        'last_login'   : user.last_login.isoformat()  if user.last_login  else None,
        # from UserProfile
        'user_type'    : profile.user_type    if profile else None,
        'state'        : profile.state        if profile else None,
        'district'     : profile.district     if profile else None,
        'city_village' : profile.city_village if profile else None,
        'is_profile_active': profile.status   if profile else None,
    }


# ── Device types ─────────────────────────────────────────────────────────────

class DeviceTypeSerializer(serializers.Serializer):
    """One entry per device type; locked=True when user owns no device of that type."""
    type_key     = serializers.CharField()
    type_name    = serializers.CharField()
    locked       = serializers.BooleanField()
    device_count = serializers.IntegerField()
    api_used     = serializers.IntegerField()


# ── Devices ──────────────────────────────────────────────────────────────────

class DeviceLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviseLocation
        fields = ['latitude', 'longitude']


class DeviceListSerializer(serializers.ModelSerializer):
    """Compact device list for mobile."""
    type_name    = serializers.SerializerMethodField()
    api_used     = serializers.SerializerMethodField()
    api_limit    = serializers.SerializerMethodField()
    has_location = serializers.SerializerMethodField()

    class Meta:
        model  = Devise
        fields = [
            'id', 'name', 'serial_no', 'devise_id', 'devise_type', 'type_name',
            'address1', 'address2', 'purchase_date', 'land',
            'api_used', 'api_limit', 'has_location', 'created_at',
        ]

    def get_type_name(self, obj):
        return DEVICE_NAMES.get(obj.devise_type, obj.devise_type)

    def get_api_used(self, obj):
        if obj.devise_type == 'soilsaathi':
            return DeviseApis.objects.filter(device=obj).count()
        return DeviseApisFields.objects.filter(device=obj).count()

    def get_api_limit(self, obj):
        t = APICountThreshold.objects.filter(devise=obj).first()
        return t.red if t else None

    def get_has_location(self, obj):
        return DeviseLocation.objects.filter(devise=obj).exists()


class DeviceDetailSerializer(DeviceListSerializer):
    """Full device details including location and usage."""
    location = serializers.SerializerMethodField()

    class Meta(DeviceListSerializer.Meta):
        fields = DeviceListSerializer.Meta.fields + [
            'email', 'phone', 'chipset_no', 'warrenty',
            'amount_paid', 'balance_amount', 'time_of_sale',
            'location',
        ]

    def get_location(self, obj):
        loc = DeviseLocation.objects.filter(devise=obj).first()
        return DeviceLocationSerializer(loc).data if loc else None


# ── Soil Saathi (SoiLENZ) API call ───────────────────────────────────────────

class SoilSaathiReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviseApis
        fields = [
            'id', 'farmer_id', 'area_name', 'tag',
            'nitrogen', 'phosphorous', 'potassium',
            'calcium', 'magnesium', 'sulphur',
            'zinc', 'manganese', 'iron', 'copper', 'boron',
            'ph', 'ec', 'oc', 'electrical_conduction',
            'crop_type', 'latitude', 'longitude', 'created_at',
        ]
        read_only_fields = ['id', 'farmer_id', 'created_at']


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


# ── AtmoSense / SoilLIFE / PHBottle (DeviseApisFields) API call ──────────────

def _sensor_fields(field_map):
    """Extract only field1–field8 entries from a *_FIELDS map."""
    return {k: v for k, v in field_map.items() if k.startswith('field')}

FIELD_LABELS = {
    'atmo_sense': _sensor_fields(ATMO_SENSE_FIELDS),
    'soil_life' : _sensor_fields(SOIL_LIFE_FIELDS),
    'ph_bottle' : _sensor_fields(PH_BOTTLE_FIELDS),
    'soil_map'  : _sensor_fields(SOIL_MAP_FIELDS),
    'leaflenz'  : _sensor_fields(LEAFLENZ_FIELDS),
}


class FieldsReadingSerializer(serializers.ModelSerializer):
    labeled_fields = serializers.SerializerMethodField()
    image_path     = serializers.SerializerMethodField()

    class Meta:
        model  = DeviseApisFields
        fields = [
            'id', 'farmer_id', 'tag', 'image_path', 'crop_type',
            'latitude', 'longitude',
            'field1', 'field2', 'field3', 'field4', 'field5',
            'field6', 'field7', 'field8',
            'labeled_fields', 'created_at',
        ]
        read_only_fields = ['id', 'farmer_id', 'created_at', 'labeled_fields', 'image_path']

    def get_image_path(self, obj):
        if not obj.image_path:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image_path)
        return obj.image_path

    def get_labeled_fields(self, obj):
        labels = FIELD_LABELS.get(obj.device.devise_type, {})
        return {label: getattr(obj, key, 0) for key, label in labels.items()}


class FieldsReadingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviseApisFields
        fields = [
            'tag', 'image_path', 'crop_type',
            'latitude', 'longitude',
            'field1', 'field2', 'field3', 'field4', 'field5',
            'field6', 'field7', 'field8',
        ]


# ── LeafLenz (leaf disease scan) ──────────────────────────────────────────────

class LeafLenzReadingSerializer(FieldsReadingSerializer):
    """
    FieldsReadingSerializer + disease details derived from `tag` (the raw
    predicted class label, e.g. 'Tomato___Early_blight') and field1 (confidence).
    """
    plant_name   = serializers.SerializerMethodField()
    disease_name = serializers.SerializerMethodField()
    disease_info = serializers.SerializerMethodField()

    class Meta(FieldsReadingSerializer.Meta):
        fields = FieldsReadingSerializer.Meta.fields + ['plant_name', 'disease_name', 'disease_info']

    def get_plant_name(self, obj):
        plant, _ = parse_class_label(obj.tag or 'fallback')
        return plant

    def get_disease_name(self, obj):
        _, disease = parse_class_label(obj.tag or 'fallback')
        return disease

    def get_disease_info(self, obj):
        details = get_disease_details(obj.tag or 'fallback')
        return {
            'description'           : details.get('description', 'N/A'),
            'symptoms'              : details.get('symptoms', 'N/A'),
            'treatment_and_prevention': details.get('treatment_prevention', 'N/A'),
        }


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