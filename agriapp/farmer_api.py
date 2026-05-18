"""
Farmer REST API for the /api/mobile/farmers/ endpoints.
Requires JWT authentication. Only soil partners (or superusers) can access.

Endpoints
─────────
GET  /api/mobile/farmers/                   List farmers for the logged-in soil partner
POST /api/mobile/farmers/create/            Register a new farmer (multipart for image)
GET  /api/mobile/farmers/<pk>/              Farmer detail
POST /api/mobile/farmers/<pk>/status/       Update farmer status
GET  /api/mobile/farmers/<pk>/api-calls/    All API call readings linked to that farmer
"""
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status, serializers

from django.shortcuts import get_object_or_404

from .models import (
    Farmer, FarmerStatusHistory, UserProfile,
    FARMER_STATUS_CHOICES, SEASON_CHOICES,
    DeviseApis, DeviseApisFields,
)


# ── Serializers ───────────────────────────────────────────────────────────────

class StatusHistorySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    timestamp      = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model  = FarmerStatusHistory
        fields = ['status', 'status_display', 'timestamp']


class FarmerListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    season_display = serializers.CharField(source='get_season_display', read_only=True)
    created_at     = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    farmer_image   = serializers.SerializerMethodField()

    class Meta:
        model  = Farmer
        fields = [
            'id', 'farmer_name', 'phone', 'mobile', 'email', 'aadhaar_number',
            'farmer_image', 'state', 'district', 'village',
            'latitude', 'longitude', 'land_area', 'crop', 'season', 'season_display',
            'status', 'status_display', 'created_at',
        ]

    def get_farmer_image(self, obj):
        request = self.context.get('request')
        if obj.farmer_image and request:
            return request.build_absolute_uri(obj.farmer_image.url)
        return None


class FarmerDetailSerializer(FarmerListSerializer):
    status_history = StatusHistorySerializer(many=True, read_only=True)
    soil_partner   = serializers.SerializerMethodField()

    class Meta(FarmerListSerializer.Meta):
        fields = FarmerListSerializer.Meta.fields + ['status_history', 'soil_partner']

    def get_soil_partner(self, obj):
        return {
            'id'       : obj.soil_partner.id,
            'username' : obj.soil_partner.username,
            'full_name': obj.soil_partner.get_full_name(),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_soil_partner(user):
    try:
        return user.profile.user_type == 'soil_partner'
    except UserProfile.DoesNotExist:
        return False

def _has_farmer_access(user):
    return user.is_superuser or _is_soil_partner(user)

def _farmer_qs(user):
    if user.is_superuser:
        return Farmer.objects.all()
    return Farmer.objects.filter(soil_partner=user)


# ── Views ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_list(request):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Only soil partners can access farmers.'}, status=403)

    farmers    = _farmer_qs(request.user).order_by('-created_at')
    serializer = FarmerListSerializer(farmers, many=True, context={'request': request})
    return Response({'count': farmers.count(), 'results': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def farmer_create(request):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Only soil partners can register farmers.'}, status=403)

    data = request.data

    # Determine soil partner
    if request.user.is_superuser:
        sp_id = data.get('soil_partner_id')
        if not sp_id:
            return Response({'detail': 'soil_partner_id is required for admin.'}, status=400)
        from django.contrib.auth.models import User
        soil_partner = get_object_or_404(User, pk=sp_id)
    else:
        soil_partner = request.user

    required = ['farmer_name', 'phone', 'aadhaar_number', 'state', 'district', 'village', 'land_area', 'crop', 'season']
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return Response({'detail': f'Missing required fields: {", ".join(missing)}'}, status=400)

    valid_seasons = [s[0] for s in SEASON_CHOICES]
    if data.get('season') not in valid_seasons:
        return Response({'detail': f'season must be one of: {", ".join(valid_seasons)}'}, status=400)

    farmer = Farmer(
        soil_partner   = soil_partner,
        farmer_name    = data.get('farmer_name', '').strip(),
        phone          = data.get('phone', '').strip(),
        email          = data.get('email', '').strip(),
        aadhaar_number = data.get('aadhaar_number', '').strip(),
        mobile         = data.get('mobile', '').strip(),
        state          = data.get('state', '').strip(),
        district       = data.get('district', '').strip(),
        village        = data.get('village', '').strip(),
        latitude       = data.get('latitude') or None,
        longitude      = data.get('longitude') or None,
        land_area      = data.get('land_area', 0),
        crop           = data.get('crop', '').strip(),
        season         = data.get('season', ''),
    )
    if request.FILES.get('farmer_image'):
        farmer.farmer_image = request.FILES['farmer_image']
    farmer.save()
    FarmerStatusHistory.objects.create(farmer=farmer, status='registered')

    serializer = FarmerDetailSerializer(farmer, context={'request': request})
    return Response(serializer.data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_detail(request, pk):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)
    serializer = FarmerDetailSerializer(farmer, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def farmer_update_status(request, pk):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    new_status = request.data.get('status', '')
    valid      = [s[0] for s in FARMER_STATUS_CHOICES]
    if new_status not in valid:
        return Response({'detail': f'status must be one of: {", ".join(valid)}'}, status=400)

    farmer.status = new_status
    farmer.save()
    FarmerStatusHistory.objects.create(farmer=farmer, status=new_status)

    return Response({
        'id'      : farmer.pk,
        'status'  : farmer.status,
        'display' : dict(FARMER_STATUS_CHOICES)[new_status],
        'message' : 'Status updated successfully.',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_api_calls(request, pk):
    """Return all device readings (DeviseApis + DeviseApisFields) linked to a farmer."""
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    soilsaathi = list(
        DeviseApis.objects.filter(farmer=farmer).values(
            'id', 'device_id', 'area_name', 'nitrogen', 'phosphorous', 'potassium',
            'ph', 'ec', 'oc', 'crop_type', 'latitude', 'longitude', 'created_at'
        )
    )
    sensor = list(
        DeviseApisFields.objects.filter(farmer=farmer).values(
            'id', 'device_id', 'tag', 'field1', 'field2', 'field3', 'field4',
            'field5', 'field6', 'field7', 'field8', 'latitude', 'longitude', 'created_at'
        )
    )

    return Response({
        'farmer_id'       : farmer.pk,
        'farmer_name'     : farmer.farmer_name,
        'soilsaathi_count': len(soilsaathi),
        'sensor_count'    : len(sensor),
        'soilsaathi'      : soilsaathi,
        'sensor_readings' : sensor,
    })


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def farmer_update(request, pk):
    """Update farmer details. Only the owning soil partner (or admin) can update."""
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    data            = request.data
    updatable_fields = [
        'farmer_name', 'phone', 'mobile', 'email', 'aadhaar_number',
        'state', 'district', 'village', 'latitude', 'longitude',
        'land_area', 'crop', 'season',
    ]
    for field in updatable_fields:
        if field in data:
            setattr(farmer, field, data[field])

    if 'season' in data:
        valid_seasons = [s[0] for s in SEASON_CHOICES]
        if data['season'] not in valid_seasons:
            return Response({'detail': f'season must be one of: {", ".join(valid_seasons)}'}, status=400)

    farmer.save()
    serializer = FarmerDetailSerializer(farmer, context={'request': request})
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def farmer_delete(request, pk):
    """Delete a farmer. Only the owning soil partner (or admin) can delete."""
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)
    farmer_name = farmer.farmer_name
    farmer.delete()
    return Response({'message': f'Farmer "{farmer_name}" deleted successfully.'}, status=200)


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def farmer_update_image(request, pk):
    """Replace farmer profile image. Send as multipart field 'farmer_image'."""
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    image = request.FILES.get('farmer_image')
    if not image:
        return Response({'detail': 'farmer_image file is required.'}, status=400)

    # Remove old image file from storage if it exists
    if farmer.farmer_image:
        import os
        if os.path.isfile(farmer.farmer_image.path):
            os.remove(farmer.farmer_image.path)

    farmer.farmer_image = image
    farmer.save()

    url = request.build_absolute_uri(farmer.farmer_image.url) if farmer.farmer_image else None
    return Response({'id': farmer.pk, 'farmer_image': url, 'message': 'Image updated successfully.'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def farmer_delete_image(request, pk):
    """Remove farmer profile image."""
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    if not farmer.farmer_image:
        return Response({'detail': 'No image to delete.'}, status=400)

    import os
    if os.path.isfile(farmer.farmer_image.path):
        os.remove(farmer.farmer_image.path)
    farmer.farmer_image = None
    farmer.save()

    return Response({'id': farmer.pk, 'farmer_image': None, 'message': 'Image deleted successfully.'})
