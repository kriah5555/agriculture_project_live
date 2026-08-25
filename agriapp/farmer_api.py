"""
Farmer REST API for the /api/mobile/farmers/ endpoints.
Requires JWT authentication. Only soil partners (or superusers) can access.

Endpoints
─────────
GET    /api/mobile/farmers/                   List farmers for the logged-in soil partner
POST   /api/mobile/farmers/create/            Register a new farmer (multipart for image)
GET    /api/mobile/farmers/check-aadhaar/     Check if Aadhaar is already registered (?aadhaar=)
GET    /api/mobile/farmers/<pk>/              Farmer detail
PATCH  /api/mobile/farmers/<pk>/update/       Update farmer fields (partial)
DELETE /api/mobile/farmers/<pk>/delete/       Delete farmer
POST   /api/mobile/farmers/<pk>/status/       Update farmer status
GET    /api/mobile/farmers/<pk>/api-calls/                      Summary of API calls per device
GET    /api/mobile/farmers/<pk>/device-readings/<device_id>/   Paginated readings for one device
POST   /api/mobile/farmers/<pk>/image/        Upload / replace farmer image
DELETE /api/mobile/farmers/<pk>/image/delete/ Remove farmer image
"""
import os

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status, serializers

from django.shortcuts import get_object_or_404

from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, inline_serializer, OpenApiParameter,
)
from drf_spectacular.openapi import OpenApiTypes

from .models import (
    Farmer, FarmerStatusHistory, UserProfile,
    FARMER_STATUS_CHOICES, SEASON_CHOICES,
    DeviseApis, DeviseApisFields,
    Devise,
    SOIL_SAATHI_FIELDS, ATMO_SENSE_FIELDS, SOIL_LIFE_FIELDS, PH_BOTTLE_FIELDS,
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
            'farmer_image', 'state', 'district', 'village', 'address',
            'latitude', 'longitude', 'land_area', 'survey_number', 'plot_number',
            'crop', 'season', 'season_display',
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


class FarmerCreateSerializer(serializers.Serializer):
    farmer_name    = serializers.CharField(help_text='Full name of the farmer')
    phone          = serializers.CharField(help_text='Primary phone number')
    aadhaar_number = serializers.CharField(help_text='12-digit Aadhaar number')
    state          = serializers.CharField()
    district       = serializers.CharField()
    village        = serializers.CharField()
    address        = serializers.CharField(required=False, help_text='House/street address')
    land_area      = serializers.FloatField(help_text='Land area in acres')
    survey_number  = serializers.CharField(required=False, help_text='Land survey number')
    plot_number    = serializers.CharField(required=False, help_text='Land plot number')
    crop           = serializers.CharField(help_text='Primary crop grown')
    season         = serializers.ChoiceField(choices=SEASON_CHOICES)
    mobile         = serializers.CharField(required=False, help_text='Secondary mobile number')
    email          = serializers.EmailField(required=False)
    latitude       = serializers.FloatField(required=False, allow_null=True)
    longitude      = serializers.FloatField(required=False, allow_null=True)
    farmer_image   = serializers.ImageField(required=False, help_text='Farmer profile photo')
    soil_partner_id = serializers.IntegerField(required=False, help_text='Admin only: assign to a specific soil partner')


class FarmerUpdateSerializer(serializers.Serializer):
    farmer_name    = serializers.CharField(required=False)
    phone          = serializers.CharField(required=False)
    mobile         = serializers.CharField(required=False)
    email          = serializers.EmailField(required=False)
    aadhaar_number = serializers.CharField(required=False)
    state          = serializers.CharField(required=False)
    district       = serializers.CharField(required=False)
    village        = serializers.CharField(required=False)
    address        = serializers.CharField(required=False)
    latitude       = serializers.FloatField(required=False, allow_null=True)
    longitude      = serializers.FloatField(required=False, allow_null=True)
    land_area      = serializers.FloatField(required=False)
    survey_number  = serializers.CharField(required=False)
    plot_number    = serializers.CharField(required=False)
    crop           = serializers.CharField(required=False)
    season         = serializers.ChoiceField(choices=SEASON_CHOICES, required=False)
    farmer_image   = serializers.ImageField(required=False)


class FarmerStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=FARMER_STATUS_CHOICES,
        help_text='One of: registered, re_registered, sample_collected, testing_done, report_delivered',
    )


class FarmerImageSerializer(serializers.Serializer):
    farmer_image = serializers.ImageField(help_text='New farmer profile photo (multipart/form-data)')


# ── Inline response schemas ───────────────────────────────────────────────────

_farmer_list_response = inline_serializer(
    name='FarmerListResponse',
    fields={
        'count'  : serializers.IntegerField(),
        'results': FarmerListSerializer(many=True),
    },
)

_status_update_response = inline_serializer(
    name='FarmerStatusUpdateResponse',
    fields={
        'id'     : serializers.IntegerField(),
        'status' : serializers.CharField(),
        'display': serializers.CharField(),
        'message': serializers.CharField(),
    },
)

_delete_response = inline_serializer(
    name='FarmerDeleteResponse',
    fields={'message': serializers.CharField()},
)

_image_response = inline_serializer(
    name='FarmerImageResponse',
    fields={
        'id'          : serializers.IntegerField(),
        'farmer_image': serializers.URLField(allow_null=True),
        'message'     : serializers.CharField(),
    },
)

class FarmerSoilsaathiReadingSerializer(serializers.Serializer):
    id          = serializers.IntegerField()
    device_id   = serializers.IntegerField()
    area_name   = serializers.CharField()
    nitrogen    = serializers.FloatField()
    phosphorous = serializers.FloatField()
    potassium   = serializers.FloatField()
    ph          = serializers.FloatField()
    ec          = serializers.FloatField()
    oc          = serializers.FloatField()
    crop_type   = serializers.CharField()
    latitude    = serializers.FloatField(allow_null=True)
    longitude   = serializers.FloatField(allow_null=True)
    created_at  = serializers.DateTimeField()


class FarmerSensorReadingSerializer(serializers.Serializer):
    id         = serializers.IntegerField()
    device_id  = serializers.IntegerField()
    tag        = serializers.CharField()
    field1     = serializers.FloatField()
    field2     = serializers.FloatField()
    field3     = serializers.FloatField()
    field4     = serializers.FloatField()
    field5     = serializers.FloatField()
    field6     = serializers.FloatField()
    field7     = serializers.FloatField()
    field8     = serializers.FloatField()
    latitude   = serializers.FloatField(allow_null=True)
    longitude  = serializers.FloatField(allow_null=True)
    created_at = serializers.DateTimeField()


_api_calls_response = inline_serializer(
    name='FarmerApiCallsResponse',
    fields={
        'farmer_id'       : serializers.IntegerField(),
        'farmer_name'     : serializers.CharField(),
        'soilsaathi_count': serializers.IntegerField(),
        'sensor_count'    : serializers.IntegerField(),
        'soilsaathi'      : FarmerSoilsaathiReadingSerializer(many=True),
        'sensor_readings' : FarmerSensorReadingSerializer(many=True),
    },
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_soil_partner(user):
    try:
        return user.profile.user_type == 'soil_partner'
    except UserProfile.DoesNotExist:
        return False

def _is_active_soil_partner(user):
    """Returns True only if user is a soil partner AND their profile status is active."""
    if user.is_superuser:
        return True
    try:
        p = user.profile
        return p.user_type == 'soil_partner' and p.status is True
    except UserProfile.DoesNotExist:
        return False

def _has_farmer_access(user):
    return user.is_superuser or _is_soil_partner(user)

def _check_active_partner(user):
    """
    Returns a 403 Response if the user is a soil partner but their account is inactive,
    or None if the request should proceed.
    """
    if user.is_superuser:
        return None
    if not _is_soil_partner(user):
        return Response({'detail': 'Only soil partners can perform this action.'}, status=403)
    try:
        if not user.profile.status:
            return Response(
                {'detail': 'Your soil partner account is inactive. Please contact the administrator.'},
                status=403,
            )
    except UserProfile.DoesNotExist:
        return Response({'detail': 'Profile not found.'}, status=403)
    return None

def _farmer_qs(user):
    if user.is_superuser:
        return Farmer.objects.all()
    return Farmer.objects.filter(soil_partner=user)


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Farmers'],
    summary='List farmers',
    description='Returns all farmers for the logged-in soil partner. Superusers see all farmers.',
    responses={
        200: _farmer_list_response,
        403: OpenApiResponse(description='Not a soil partner'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_list(request):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Only soil partners can access farmers.'}, status=403)

    farmers    = _farmer_qs(request.user).order_by('-created_at')
    serializer = FarmerListSerializer(farmers, many=True, context={'request': request})
    return Response({'count': farmers.count(), 'results': serializer.data})


@extend_schema(
    tags=['Farmers'],
    summary='Create a farmer',
    description='Register a new farmer under the logged-in soil partner. Send as multipart/form-data if uploading an image.',
    request=FarmerCreateSerializer,
    responses={
        201: FarmerDetailSerializer,
        400: OpenApiResponse(description='Missing or invalid fields'),
        403: OpenApiResponse(description='Not a soil partner'),
        409: OpenApiResponse(description='Aadhaar already registered — returns existing farmer data with reset instructions'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def farmer_create(request):
    blocked = _check_active_partner(request.user)
    if blocked:
        return blocked

    data = request.data

    if request.user.is_superuser:
        sp_id = data.get('soil_partner_id')
        if not sp_id:
            return Response({'detail': 'soil_partner_id is required for admin.'}, status=400)
        from django.contrib.auth.models import User
        soil_partner = get_object_or_404(User, pk=sp_id)
    else:
        soil_partner = request.user

    aadhaar = data.get('aadhaar_number', '').strip()
    if aadhaar:
        existing = Farmer.objects.filter(soil_partner=soil_partner, aadhaar_number=aadhaar).first()
        if existing:
            serializer = FarmerDetailSerializer(existing, context={'request': request})
            return Response({
                'duplicate'      : True,
                'detail'         : f'A farmer with Aadhaar {aadhaar} already exists under your account.',
                'farmer'         : serializer.data,
                'reset_url'      : f'/api/mobile/farmers/{existing.pk}/status/',
                'reset_hint'     : 'POST {"status": "re_registered"} to the reset_url to reactivate this farmer.',
            }, status=status.HTTP_409_CONFLICT)

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
        address        = data.get('address', '').strip(),
        latitude       = data.get('latitude') or None,
        longitude      = data.get('longitude') or None,
        land_area      = data.get('land_area', 0),
        survey_number  = data.get('survey_number', '').strip(),
        plot_number    = data.get('plot_number', '').strip(),
        crop           = data.get('crop', '').strip(),
        season         = data.get('season', ''),
    )
    if request.FILES.get('farmer_image'):
        farmer.farmer_image = request.FILES['farmer_image']
    farmer.save()
    FarmerStatusHistory.objects.create(farmer=farmer, status='registered')

    serializer = FarmerDetailSerializer(farmer, context={'request': request})
    return Response(serializer.data, status=201)


@extend_schema(
    tags=['Farmers'],
    summary='Get farmer detail',
    responses={
        200: FarmerDetailSerializer,
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_detail(request, pk):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)
    serializer = FarmerDetailSerializer(farmer, context={'request': request})
    return Response(serializer.data)


@extend_schema(
    tags=['Farmers'],
    summary='Update farmer details',
    description='All fields are optional. Send only the fields you want to change.',
    request=FarmerUpdateSerializer,
    responses={
        200: FarmerDetailSerializer,
        400: OpenApiResponse(description='Invalid field value'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def farmer_update(request, pk):
    blocked = _check_active_partner(request.user)
    if blocked:
        return blocked
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    data             = request.data
    updatable_fields = [
        'farmer_name', 'phone', 'mobile', 'email', 'aadhaar_number',
        'state', 'district', 'village', 'address', 'latitude', 'longitude',
        'land_area', 'survey_number', 'plot_number', 'crop', 'season',
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


@extend_schema(
    tags=['Farmers'],
    summary='Delete a farmer',
    responses={
        200: _delete_response,
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def farmer_delete(request, pk):
    blocked = _check_active_partner(request.user)
    if blocked:
        return blocked
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)
    farmer_name = farmer.farmer_name
    farmer.delete()
    return Response({'message': f'Farmer "{farmer_name}" deleted successfully.'}, status=200)


@extend_schema(
    tags=['Farmers'],
    summary='Update farmer status',
    description='Valid values: `registered`, `re_registered`, `sample_collected`, `testing_done`, `report_delivered`. Each change is recorded in the status history timeline.',
    request=FarmerStatusUpdateSerializer,
    responses={
        200: _status_update_response,
        400: OpenApiResponse(description='Invalid status value'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def farmer_update_status(request, pk):
    blocked = _check_active_partner(request.user)
    if blocked:
        return blocked
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    new_status = request.data.get('status', '')
    valid      = [s[0] for s in FARMER_STATUS_CHOICES]
    if new_status not in valid:
        return Response({'detail': f'status must be one of: {", ".join(valid)}'}, status=400)

    farmer.status = new_status
    farmer.save()
    FarmerStatusHistory.objects.create(farmer=farmer, status=new_status)

    return Response({
        'id'     : farmer.pk,
        'status' : farmer.status,
        'display': dict(FARMER_STATUS_CHOICES)[new_status],
        'message': 'Status updated successfully.',
    })


@extend_schema(
    tags=['Farmers'],
    summary='Get farmer API call summary with readings list',
    description=(
        'Returns a per-device summary (count + list of readings) for all API calls linked to this farmer.\n\n'
        '**Query params:**\n'
        '- `per_device` — max readings to include per device (default 20, max 100). Pass `0` to get counts only (no readings list).\n'
        '- `page` — page number for the readings within each device (default 1).\n\n'
        'Each device entry includes:\n'
        '- `api_count` — total readings for this farmer+device\n'
        '- `readings` — array of the most recent readings (empty when `per_device=0`)\n'
        '- `readings_page` / `readings_total_pages` — pagination info'
    ),
    parameters=[
        OpenApiParameter('per_device', OpenApiTypes.INT, description='Readings per device (default 20, max 100; 0 = counts only)'),
        OpenApiParameter('page',       OpenApiTypes.INT, description='Page number for readings (default 1)'),
    ],
    responses={
        200: OpenApiResponse(description='API call summary with readings per device'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_api_calls(request, pk):
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    per_device = min(int(request.query_params.get('per_device', 20)), 100)
    page       = max(1, int(request.query_params.get('page', 1)))

    from django.db.models import Count as _Count
    import pytz
    from django.utils import timezone as _tz

    bangalore_tz = pytz.timezone('Asia/Kolkata')

    def _fmt_dt(dt):
        if not dt:
            return None
        if _tz.is_naive(dt):
            dt = _tz.make_aware(dt, pytz.UTC)
        return dt.astimezone(bangalore_tz).strftime('%Y-%m-%d %H:%M:%S')

    # ── SoiLENZ (soilsaathi) ──────────────────────────────────────────────────
    ss_summary = list(
        DeviseApis.objects.filter(farmer=farmer)
        .values('device__id', 'device__name', 'device__devise_id')
        .annotate(count=_Count('id'))
        .order_by('device__id')
    )

    # ── Sensor devices (atmo_sense, soil_life, ph_bottle) ─────────────────────
    sensor_summary = list(
        DeviseApisFields.objects.filter(farmer=farmer)
        .values('device__id', 'device__name', 'device__devise_id', 'device__devise_type')
        .annotate(count=_Count('id'))
        .order_by('device__id')
    )

    def _ss_readings(device_id, per_pg, pg):
        qs     = DeviseApis.objects.filter(farmer=farmer, device_id=device_id).order_by('-created_at')
        total  = qs.count()
        offset = (pg - 1) * per_pg
        rows   = []
        for r in qs[offset:offset + per_pg]:
            rows.append({
                'id': r.pk, 'created_at': _fmt_dt(r.created_at),
                'area_name': r.area_name, 'tag': r.tag, 'crop_type': r.crop_type,
                'ph': r.ph, 'ec': r.ec, 'oc': r.oc,
                'nitrogen': r.nitrogen, 'phosphorous': r.phosphorous, 'potassium': r.potassium,
                'calcium': r.calcium, 'magnesium': r.magnesium, 'sulphur': r.sulphur,
                'zinc': r.zinc, 'manganese': r.manganese, 'iron': r.iron,
                'copper': r.copper, 'boron': r.boron,
                'latitude': r.latitude, 'longitude': r.longitude,
            })
        return rows, total

    def _sensor_readings(device_id, device_type, per_pg, pg):
        from agriapp.models import ATMO_SENSE_FIELDS, SOIL_LIFE_FIELDS, PH_BOTTLE_FIELDS
        headers_map = {'atmo_sense': ATMO_SENSE_FIELDS, 'soil_life': SOIL_LIFE_FIELDS, 'ph_bottle': PH_BOTTLE_FIELDS}
        field_keys  = [k for k in headers_map.get(device_type, {}) if k.startswith('field')]
        qs     = DeviseApisFields.objects.filter(farmer=farmer, device_id=device_id).order_by('-created_at')
        total  = qs.count()
        offset = (pg - 1) * per_pg
        rows   = []
        for r in qs[offset:offset + per_pg]:
            img = request.build_absolute_uri(r.image_path) if r.image_path else None
            row = {'id': r.pk, 'created_at': _fmt_dt(r.created_at),
                   'tag': r.tag, 'crop_type': r.crop_type, 'image_path': img,
                   'latitude': r.latitude, 'longitude': r.longitude}
            for fk in field_keys:
                row[fk] = getattr(r, fk, None)
            rows.append(row)
        return rows, total

    device_summary = []

    for r in ss_summary:
        entry = {
            'device_id'  : r['device__id'],
            'device_name': r['device__name'] or r['device__devise_id'],
            'device_type': 'soilsaathi',
            'api_count'  : r['count'],
        }
        if per_device > 0:
            rows, total = _ss_readings(r['device__id'], per_device, page)
            entry['readings']            = rows
            entry['readings_page']       = page
            entry['readings_total_pages'] = max(1, -(-total // per_device))
        else:
            entry['readings'] = []
        device_summary.append(entry)

    for r in sensor_summary:
        entry = {
            'device_id'  : r['device__id'],
            'device_name': r['device__name'] or r['device__devise_id'],
            'device_type': r['device__devise_type'],
            'api_count'  : r['count'],
        }
        if per_device > 0:
            rows, total = _sensor_readings(r['device__id'], r['device__devise_type'], per_device, page)
            entry['readings']            = rows
            entry['readings_page']       = page
            entry['readings_total_pages'] = max(1, -(-total // per_device))
        else:
            entry['readings'] = []
        device_summary.append(entry)

    total_calls = sum(d['api_count'] for d in device_summary)

    return Response({
        'farmer_id'      : farmer.pk,
        'farmer_name'    : farmer.farmer_name,
        'total_api_calls': total_calls,
        'per_device'     : per_device,
        'page'           : page,
        'devices'        : device_summary,
    })


_DEVICE_FIELD_HEADERS = {
    'soilsaathi': SOIL_SAATHI_FIELDS,
    'atmo_sense' : ATMO_SENSE_FIELDS,
    'soil_life'  : SOIL_LIFE_FIELDS,
    'ph_bottle'  : PH_BOTTLE_FIELDS,
}


@extend_schema(
    tags=['Farmers'],
    summary='List readings for a farmer + device (paginated)',
    description=(
        'Returns paginated API-call readings for a specific farmer and device combination. '
        'Use the `devices` list from `GET /api/mobile/farmers/<pk>/api-calls/` to find valid device IDs.'
    ),
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number (default 1)'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 100, default 50)'),
    ],
    responses={
        200: OpenApiResponse(description='Paginated readings with field headers'),
        400: OpenApiResponse(description='Unsupported device type'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer or device not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_device_readings(request, pk, device_id):
    """Paginated readings for one farmer + device — mirrors the web expand panel."""
    if not _has_farmer_access(request.user):
        return Response({'detail': 'Permission denied.'}, status=403)
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)
    device = get_object_or_404(Devise, pk=device_id)

    page     = max(1, int(request.query_params.get('page', 1)))
    per_page = min(int(request.query_params.get('per_page', 50)), 100)

    headers = _DEVICE_FIELD_HEADERS.get(device.devise_type)
    if headers is None:
        return Response({'detail': f'Unsupported device type: {device.devise_type}.'}, status=status.HTTP_400_BAD_REQUEST)

    if device.devise_type == 'soilsaathi':
        qs = DeviseApis.objects.filter(device=device, farmer=farmer).order_by('-created_at')
    else:
        qs = DeviseApisFields.objects.filter(device=device, farmer=farmer).order_by('-created_at')

    from django.core.paginator import Paginator
    import pytz
    from django.utils import timezone as _tz

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)
    data      = list(page_obj.object_list.values())

    btz = pytz.timezone('Asia/Kolkata')
    for item in data:
        if item.get('created_at'):
            utc_dt = item['created_at']
            if _tz.is_naive(utc_dt):
                utc_dt = _tz.make_aware(utc_dt, timezone=pytz.UTC)
            item['created_at'] = utc_dt.astimezone(btz).strftime('%Y-%m-%d %H:%M:%S')
        item.pop('farmer_id', None)
        item.pop('device_id', None)
        # Build full URL for image_path
        if item.get('image_path'):
            item['image_path'] = request.build_absolute_uri(item['image_path'])

    return Response({
        'farmer_id'  : farmer.pk,
        'farmer_name': farmer.farmer_name,
        'device_id'  : device.pk,
        'device_name': device.name or device.devise_id,
        'device_type': device.devise_type,
        'headers'    : headers,
        'pagination' : {
            'current_page' : page_obj.number,
            'per_page'     : per_page,
            'total_pages'  : paginator.num_pages,
            'total_records': paginator.count,
        },
        'data': data,
    })


@extend_schema(
    tags=['Farmers'],
    summary='Upload / replace farmer image',
    description='Send as `multipart/form-data` with field name `farmer_image`. Replaces any existing image.',
    request=FarmerImageSerializer,
    responses={
        200: _image_response,
        400: OpenApiResponse(description='No image file provided'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def farmer_update_image(request, pk):
    blocked = _check_active_partner(request.user)
    if blocked:
        return blocked
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    image = request.FILES.get('farmer_image')
    if not image:
        return Response({'detail': 'farmer_image file is required.'}, status=400)

    if farmer.farmer_image:
        if os.path.isfile(farmer.farmer_image.path):
            os.remove(farmer.farmer_image.path)

    farmer.farmer_image = image
    farmer.save()

    url = request.build_absolute_uri(farmer.farmer_image.url) if farmer.farmer_image else None
    return Response({'id': farmer.pk, 'farmer_image': url, 'message': 'Image updated successfully.'})


@extend_schema(
    tags=['Farmers'],
    summary='Delete farmer image',
    description='Removes the farmer profile photo from storage.',
    responses={
        200: _image_response,
        400: OpenApiResponse(description='No image to delete'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='Farmer not found'),
    },
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def farmer_delete_image(request, pk):
    blocked = _check_active_partner(request.user)
    if blocked:
        return blocked
    farmer = get_object_or_404(_farmer_qs(request.user), pk=pk)

    if not farmer.farmer_image:
        return Response({'detail': 'No image to delete.'}, status=400)

    if os.path.isfile(farmer.farmer_image.path):
        os.remove(farmer.farmer_image.path)
    farmer.farmer_image = None
    farmer.save()

    return Response({'id': farmer.pk, 'farmer_image': None, 'message': 'Image deleted successfully.'})


# ── Aadhaar check ─────────────────────────────────────────────────────────────

_aadhaar_check_response = inline_serializer(
    name='AadhaarCheckResponse',
    fields={
        'exists'        : serializers.BooleanField(),
        'id'            : serializers.IntegerField(required=False),
        'name'          : serializers.CharField(required=False),
        'phone'         : serializers.CharField(required=False),
        'village'       : serializers.CharField(required=False),
        'status'        : serializers.CharField(required=False),
        'status_display': serializers.CharField(required=False),
        'reset_hint'    : serializers.CharField(required=False),
    },
)


@extend_schema(
    tags=['Farmers'],
    summary='Check if an Aadhaar number is already registered',
    description=(
        'Returns `exists: false` if no farmer with this Aadhaar exists for the '
        'current soil partner. Returns `exists: true` with farmer details and a '
        '`reset_hint` message when a duplicate is found — mirrors the live-check '
        'shown on the web Create Farmer form. '
        'Superusers may pass `?sp_id=<id>` to scope the check to a specific soil partner.'
    ),
    parameters=[
        OpenApiParameter('aadhaar', OpenApiTypes.STR, required=True, description='12-digit Aadhaar number'),
        OpenApiParameter('sp_id',   OpenApiTypes.INT, required=False, description='Superuser only: scope to a specific soil partner'),
    ],
    responses={
        200: _aadhaar_check_response,
        400: OpenApiResponse(description='Aadhaar number not provided'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def farmer_check_aadhaar(request):
    """Check whether an Aadhaar number is already registered for this soil partner."""
    aadhaar = request.query_params.get('aadhaar', '').strip()
    if not aadhaar:
        return Response({'detail': 'aadhaar query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    sp_id = request.query_params.get('sp_id')
    user  = request.user

    if user.is_superuser and sp_id:
        qs = Farmer.objects.filter(aadhaar_number=aadhaar, soil_partner_id=sp_id)
    elif user.is_superuser:
        qs = Farmer.objects.filter(aadhaar_number=aadhaar)
    else:
        qs = Farmer.objects.filter(aadhaar_number=aadhaar, soil_partner=user)

    farmer = qs.first()
    if farmer:
        return Response({
            'exists'        : True,
            'id'            : farmer.pk,
            'name'          : farmer.farmer_name,
            'phone'         : farmer.phone,
            'village'       : farmer.village,
            'status'        : farmer.status,
            'status_display': dict(FARMER_STATUS_CHOICES)[farmer.status],
            'reset_hint'    : (
                f'Already registered: {farmer.farmer_name} ({farmer.village}) — '
                f'{dict(FARMER_STATUS_CHOICES)[farmer.status]}. '
                'Submitting will reset their status to Re-Registered.'
            ),
        })
    return Response({'exists': False})