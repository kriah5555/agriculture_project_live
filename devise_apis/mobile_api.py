"""
Mobile REST API — device, readings, threshold, recommendations, account.

Auth views live in auth_api.py.
Per-device reading logic lives in devices/soilsaathi.py, atmo_sense.py, soil_life.py.
All endpoints are prefixed with /api/mobile/ and require JWT Bearer auth
except the auth endpoints themselves.

Token lifetimes are configured in settings.MOBILE_TOKEN_SETTINGS.
"""
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiResponse, inline_serializer,
)
from drf_spectacular.openapi import OpenApiTypes
from rest_framework import serializers as drf_serializers

from agriapp.models import (
    Devise, DeviseApis, DeviseApisFields, DeviseLocation,
    APICountThreshold, DEVICE_NAMES,
    SOIL_SAATHI_FIELDS, ATMO_SENSE_FIELDS, SOIL_LIFE_FIELDS, PH_BOTTLE_FIELDS,
)
from agriapp import FertilizerCalculation
from .mobile_serializers import (
    DeviceTypeSerializer,
    DeviceListSerializer,
    DeviceDetailSerializer,
    SoilSaathiReadingSerializer,
    SoilSaathiReadingCreateSerializer,
    FieldsReadingSerializer,
    FieldsReadingCreateSerializer,
    ThresholdSerializer,
)


# ── Inline response schemas ───────────────────────────────────────────────────

_location_response = inline_serializer(
    name='DeviceLocationResponse',
    fields={
        'latitude' : drf_serializers.FloatField(),
        'longitude': drf_serializers.FloatField(),
    },
)

_profile_response = inline_serializer(
    name='UserProfileResponse',
    fields={
        'id'         : drf_serializers.IntegerField(),
        'username'   : drf_serializers.CharField(),
        'email'      : drf_serializers.EmailField(),
        'first_name' : drf_serializers.CharField(),
        'last_name'  : drf_serializers.CharField(),
        'full_name'  : drf_serializers.CharField(),
        'date_joined': drf_serializers.DateTimeField(),
        'last_login' : drf_serializers.DateTimeField(),
    },
)

_profile_update_response = inline_serializer(
    name='UserProfileUpdateResponse',
    fields={
        'id'        : drf_serializers.IntegerField(),
        'username'  : drf_serializers.CharField(),
        'email'     : drf_serializers.EmailField(),
        'first_name': drf_serializers.CharField(),
        'last_name' : drf_serializers.CharField(),
        'full_name' : drf_serializers.CharField(),
    },
)

_recommendation_response = inline_serializer(
    name='RecommendationResponse',
    fields={
        'device_id'      : drf_serializers.IntegerField(),
        'reading_id'     : drf_serializers.IntegerField(),
        'reading_date'   : drf_serializers.DateTimeField(),
        'crop_type'      : drf_serializers.CharField(),
        'npk'            : inline_serializer(name='NPKValues', fields={
            'nitrogen'   : drf_serializers.FloatField(),
            'phosphorous': drf_serializers.FloatField(),
            'potassium'  : drf_serializers.FloatField(),
            'ph'         : drf_serializers.FloatField(),
            'ec'         : drf_serializers.FloatField(),
            'oc'         : drf_serializers.FloatField(),
        }),
        'recommendations': drf_serializers.ListField(child=drf_serializers.DictField()),
    },
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class MobilePagination(PageNumberPagination):
    page_size             = 50
    page_size_query_param = 'per_page'
    max_page_size         = 200

    def get_paginated_response(self, data):
        return Response({
            'count'      : self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'page'       : self.page.number,
            'per_page'   : self.get_page_size(self.request),
            'next'       : self.get_next_link(),
            'previous'   : self.get_previous_link(),
            'results'    : data,
        })


def _get_user_device(request, device_id):
    """Return device only if it belongs to the requesting user. 404 otherwise."""
    return get_object_or_404(Devise, pk=device_id, user=request.user)


# ── Device Types ──────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Device Types'],
    summary='List all device types',
    description=(
        'Returns all supported device types (SoiLENZ, SoilSparsh, SoilLIFE, PHBottle). '
        'Each entry includes `locked: true` when the user does not own any device of that type. '
        'Designed to render a "Page 1" device selector in the mobile app. '
        'Scalable — new device types added to the backend appear automatically.'
    ),
    responses={200: DeviceTypeSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_types(request):
    user       = request.user
    owned_types = set(
        Devise.objects.filter(user=user).values_list('devise_type', flat=True)
    )
    result = []
    for type_key, type_name in DEVICE_NAMES.items():
        count = Devise.objects.filter(user=user, devise_type=type_key).count()
        result.append({
            'type_key'    : type_key,
            'type_name'   : type_name,
            'locked'      : type_key not in owned_types,
            'device_count': count,
        })
    return Response(DeviceTypeSerializer(result, many=True).data)


# ── Device field schema ───────────────────────────────────────────────────────

_FIELD_SCHEMA_MAP = {
    'soilsaathi': SOIL_SAATHI_FIELDS,
    'atmo_sense': ATMO_SENSE_FIELDS,
    'soil_life' : SOIL_LIFE_FIELDS,
    'ph_bottle' : PH_BOTTLE_FIELDS,
}

@extend_schema(
    tags=['Device Types'],
    summary='Get field label map for a device type',
    description=(
        'Returns the mapping of sensor field keys to their human-readable labels for any device type. '
        'Use this to display column headers or form labels without needing an actual reading. '
        '\n\n'
        'Valid `type_key` values: `soilsaathi`, `atmo_sense`, `soil_life`, `ph_bottle`. '
        '\n\n'
        '**SoiLENZ (`soilsaathi`)** returns named keys like `nitrogen`, `phosphorous`, `ph`, etc. '
        '**All other types** return generic keys `field1`–`fieldN` with their label mapping '
        '(e.g. for `ph_bottle`: `field1` → `"pH Value"`, `field2` → `"pH Voltage (mV)"`, etc.).'
    ),
    responses={
        200: inline_serializer(
            name='FieldSchemaResponse',
            fields={'schema': drf_serializers.DictField(child=drf_serializers.CharField())},
        ),
        400: OpenApiResponse(description='Unknown device type key'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_field_schema(request, type_key):
    """Return the field-key → label map for any device type."""
    schema = _FIELD_SCHEMA_MAP.get(type_key)
    if schema is None:
        return Response(
            {'detail': f'Unknown device type "{type_key}". '
                       f'Valid types: {list(_FIELD_SCHEMA_MAP.keys())}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    exclude = {'id', 'tag', 'image_path', 'created_at'}
    return Response({'schema': {k: v for k, v in schema.items() if k not in exclude}})


# ── Devices ───────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Devices'],
    summary='List all user devices',
    parameters=[
        OpenApiParameter(
            'type', OpenApiTypes.STR, OpenApiParameter.QUERY,
            description='Filter by device type: soilsaathi | atmo_sense | soil_life | ph_bottle',
            required=False,
        )
    ],
    responses={200: DeviceListSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_list(request):
    """List all devices belonging to the authenticated user, optionally filtered by type."""
    qs          = Devise.objects.filter(user=request.user).order_by('-created_at')
    device_type = request.query_params.get('type')
    if device_type:
        qs = qs.filter(devise_type=device_type)
    paginator  = MobilePagination()
    page       = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(DeviceListSerializer(page, many=True).data)


@extend_schema(
    tags=['Devices'],
    summary='Get device details',
    description=(
        'Returns full details for a single device. '
        '\n\n'
        '**Important — `device_id` vs `devise_id`:** '
        'The `<device_id>` in this URL is the **integer primary key** (`id`) of the device record. '
        'This is different from the `devise_id` string field shown on the device details page, '
        'which is a human-readable identifier (e.g. a serial tag). '
        'Always use the integer `id` returned by the device list endpoint when calling this API.'
    ),
    responses={
        200: DeviceDetailSerializer,
        404: OpenApiResponse(description='Device not found or not owned by user'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_detail(request, device_id):
    """Full details for a single device including location and threshold."""
    device = _get_user_device(request, device_id)
    return Response(DeviceDetailSerializer(device).data)


@extend_schema(
    tags=['Devices'],
    summary='Get device GPS location',
    responses={
        200: _location_response,
        404: OpenApiResponse(description='No location set for this device'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_location(request, device_id):
    """Return the stored GPS location for a device."""
    device   = _get_user_device(request, device_id)
    location = get_object_or_404(DeviseLocation, devise=device)
    return Response({'latitude': location.latitude, 'longitude': location.longitude})


# ── API Calls (readings) ──────────────────────────────────────────────────────

@extend_schema(
    tags=['API Calls'],
    summary='List API calls for a device',
    description=(
        'Returns paginated sensor readings for the device. '
        'Response shape depends on device type: '
        '**SoiLENZ** returns NPK/pH fields; '
        '**SoilSparsh / SoilLIFE** return field1–field8 with a `labeled_fields` map.'
    ),
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number (default 1)'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (default 50, max 200)'),
    ],
    responses={200: FieldsReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_call_list(request, device_id):
    """Paginated list of all sensor readings for a device (routes by device type)."""
    device    = _get_user_device(request, device_id)
    paginator = MobilePagination()

    if device.devise_type == 'soilsaathi':
        qs         = DeviseApis.objects.filter(device=device).order_by('-created_at')
        page       = paginator.paginate_queryset(qs, request)
        serializer = SoilSaathiReadingSerializer(page, many=True)
    else:
        qs         = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
        page       = paginator.paginate_queryset(qs, request)
        serializer = FieldsReadingSerializer(page, many=True)

    return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=['API Calls'],
    summary='Create a new API call record',
    description=(
        'Submit a new sensor reading. '
        '**SoilSparsh / SoilLIFE** — send `field1`–`field8` (+ optional `tag`, `crop_type`, `image_path`). '
        '**SoiLENZ** — send NPK/pH fields: `nitrogen`, `phosphorous`, `potassium`, `ph`, `ec`, `oc`, `crop_type`, etc. '
        'The device API call threshold is validated before saving.'
    ),
    request=FieldsReadingCreateSerializer,
    responses={
        201: FieldsReadingSerializer,
        400: OpenApiResponse(description='Validation error — check field values'),
        403: OpenApiResponse(description='API call threshold exceeded for this device'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_call_create(request, device_id):
    """Create a sensor reading with threshold enforcement (routes by device type)."""
    device = _get_user_device(request, device_id)

    # ── Threshold check ──────────────────────────────────────────────────────
    threshold = APICountThreshold.objects.filter(devise=device).first()
    if threshold:
        if device.devise_type == 'soilsaathi':
            current_count = DeviseApis.objects.filter(device=device).count()
        else:
            current_count = DeviseApisFields.objects.filter(device=device).count()

        if current_count >= threshold.red:
            return Response(
                {
                    'detail' : 'API call limit reached for this device. Please contact the admin.',
                    'limit'  : threshold.red,
                    'current': current_count,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

    # ── Save reading ─────────────────────────────────────────────────────────
    if device.devise_type == 'soilsaathi':
        serializer = SoilSaathiReadingCreateSerializer(data=request.data)
        if serializer.is_valid():
            reading = serializer.save(
                device    = device,
                devise_id = device.devise_id,
                serial_no = device.serial_no,
            )
            return Response(SoilSaathiReadingSerializer(reading).data, status=status.HTTP_201_CREATED)
    else:
        serializer = FieldsReadingCreateSerializer(data=request.data)
        if serializer.is_valid():
            reading = serializer.save(device=device)
            return Response(FieldsReadingSerializer(reading).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['API Calls'],
    summary='Get a single API call record',
    responses={
        200: FieldsReadingSerializer,
        404: OpenApiResponse(description='Record not found or not accessible'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_call_detail(request, device_id, call_id):
    """Return full details for a single sensor reading (routes by device type)."""
    device = _get_user_device(request, device_id)

    if device.devise_type == 'soilsaathi':
        reading    = get_object_or_404(DeviseApis, pk=call_id, device=device)
        serializer = SoilSaathiReadingSerializer(reading)
    else:
        reading    = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
        serializer = FieldsReadingSerializer(reading)

    return Response(serializer.data)


# ── Threshold ─────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Thresholds'],
    summary='Get device alert threshold',
    responses={
        200: ThresholdSerializer,
        404: OpenApiResponse(description='No threshold configured for this device'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_threshold(request, device_id):
    """Return the alert threshold levels configured for a device."""
    device    = _get_user_device(request, device_id)
    threshold = get_object_or_404(APICountThreshold, devise=device)
    return Response(ThresholdSerializer(threshold).data)


@extend_schema(
    tags=['Thresholds'],
    summary='Create or update device alert threshold',
    request=ThresholdSerializer,
    responses={
        200: ThresholdSerializer,
        400: OpenApiResponse(description='Validation error'),
    },
)
@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def device_threshold_set(request, device_id):
    """Create or update the alert threshold for a device."""
    device       = _get_user_device(request, device_id)
    threshold, _ = APICountThreshold.objects.get_or_create(devise=device)
    serializer   = ThresholdSerializer(threshold, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Recommendations (SoiLENZ only) ───────────────────────────────────────────

@extend_schema(
    tags=['Recommendations'],
    summary='Get fertilizer recommendations for a device',
    parameters=[
        OpenApiParameter(
            'call_id', OpenApiTypes.INT, OpenApiParameter.QUERY,
            description='ID of the specific API call record to base recommendations on. '
                        'If omitted, uses the most recent reading.',
            required=False,
        )
    ],
    responses={
        200: _recommendation_response,
        400: OpenApiResponse(description='Device type does not support recommendations'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_recommendations(request, device_id):
    """
    Fertilizer and crop recommendations based on sensor readings.
    Only available for SoiLENZ (soilsaathi) devices which capture NPK/pH data.
    """
    device = _get_user_device(request, device_id)

    if device.devise_type != 'soilsaathi':
        return Response(
            {'detail': 'Recommendations are only available for SoiLENZ (soilsaathi) devices.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    call_id = request.query_params.get('call_id')
    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response(
                {'detail': 'No readings found for this device.'},
                status=status.HTTP_404_NOT_FOUND,
            )

    crops_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(
        reading.nitrogen, reading.phosphorous, reading.potassium,
        reading.ph, reading.ec, reading.oc, reading.crop_type,
    )

    return Response({
        'device_id'      : device.id,
        'reading_id'     : reading.id,
        'reading_date'   : reading.created_at,
        'crop_type'      : reading.crop_type,
        'npk'            : {
            'nitrogen'   : reading.nitrogen,
            'phosphorous': reading.phosphorous,
            'potassium'  : reading.potassium,
            'ph'         : reading.ph,
            'ec'         : reading.ec,
            'oc'         : reading.oc,
        },
        'recommendations': crops_data,
    })


# ── Account ───────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Account'],
    summary='Get current user profile',
    responses={200: _profile_response},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_profile(request):
    """Return the authenticated user's profile details."""
    user = request.user
    return Response({
        'id'         : user.id,
        'username'   : user.username,
        'email'      : user.email,
        'first_name' : user.first_name,
        'last_name'  : user.last_name,
        'full_name'  : user.get_full_name(),
        'date_joined': user.date_joined,
        'last_login' : user.last_login,
    })


@extend_schema(
    tags=['Account'],
    summary='Update user profile',
    description=(
        'Update the authenticated user\'s own profile. '
        'Accepted fields: `first_name`, `last_name`, `email`. '
        'Username and password cannot be changed via this endpoint.'
    ),
    request=inline_serializer(
        name='ProfileUpdateRequest',
        fields={
            'first_name': drf_serializers.CharField(required=False, allow_blank=True),
            'last_name' : drf_serializers.CharField(required=False, allow_blank=True),
            'email'     : drf_serializers.EmailField(required=False),
        },
    ),
    responses={
        200: _profile_update_response,
        400: inline_serializer(
            name='ProfileUpdateError',
            fields={'email': drf_serializers.CharField()},
        ),
    },
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def account_profile_update(request):
    """Update first_name, last_name, and/or email for the logged-in user."""
    user    = request.user
    allowed = {'first_name', 'last_name', 'email'}
    data    = {k: v for k, v in request.data.items() if k in allowed}

    if 'email' in data:
        new_email = data['email'].strip()
        if User.objects.exclude(pk=user.pk).filter(email=new_email).exists():
            return Response(
                {'email': 'This email is already in use.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.email = new_email

    if 'first_name' in data:
        user.first_name = data['first_name'].strip()
    if 'last_name' in data:
        user.last_name = data['last_name'].strip()

    user.save(update_fields=['email', 'first_name', 'last_name'])

    return Response({
        'id'        : user.id,
        'username'  : user.username,
        'email'     : user.email,
        'first_name': user.first_name,
        'last_name' : user.last_name,
        'full_name' : user.get_full_name(),
    })