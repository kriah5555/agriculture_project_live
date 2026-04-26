"""
SoiLENZ (soilsaathi) mobile API endpoints.

Routes (mounted under /api/mobile/devices/<id>/soilsaathi/):
  GET  /                      List readings
  POST /create/               Create reading
  GET  /<cid>/                Reading detail
  GET  /recommendations/      Fertilizer recommendations (FertilizerCalculation engine)
  GET  /ai-recommendation/    ML crop recommendation (?call_id=<id>)

All routes are mounted under /api/mobile/devices/<id>/  via mobile_urls.py.
Every write operation checks APICountThreshold before saving.
"""
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from agriapp.models import DeviseApis
from agriapp import FertilizerCalculation
from devise_apis.mobile_serializers import (
    SoilSaathiReadingSerializer,
    SoilSaathiReadingCreateSerializer,
)
from ._common import check_threshold, DevicePagination, get_user_device


# ── List readings ─────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='List SoiLENZ readings',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: SoilSaathiReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_list(request, device_id):
    """Paginated list of all SoiLENZ readings for a device."""
    device    = get_user_device(request, device_id)
    qs        = DeviseApis.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(SoilSaathiReadingSerializer(page, many=True).data)


# ── Create reading ────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Create SoiLENZ reading',
    description=(
        'Submit a new soil sensor reading for a SoiLENZ device. '
        'The API call threshold is checked **before** saving — if the device '
        'has reached its red-limit the request is rejected with HTTP 403.'
    ),
    request=SoilSaathiReadingCreateSerializer,
    responses={
        201: SoilSaathiReadingSerializer,
        400: OpenApiResponse(description='Validation error'),
        403: OpenApiResponse(description='API call threshold exceeded'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def soilsaathi_create(request, device_id):
    """
    Create a new SoiLENZ reading.
    Threshold is validated against APICountThreshold.red before the record is saved.
    """
    device = get_user_device(request, device_id)

    # ── Threshold guard ──────────────────────────────────────────────────────
    blocked = check_threshold(device)
    if blocked:
        return blocked

    serializer = SoilSaathiReadingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    reading = serializer.save(
        device    = device,
        devise_id = device.devise_id,
        serial_no = device.serial_no,
    )
    return Response(SoilSaathiReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


# ── Single reading detail ─────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get a single SoiLENZ reading',
    responses={
        200: SoilSaathiReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_detail(request, device_id, call_id):
    """Return full details for one SoiLENZ reading."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    return Response(SoilSaathiReadingSerializer(reading).data)


# ── Recommendations ───────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get fertilizer recommendations',
    description=(
        'Runs the FertilizerCalculation engine against a reading and returns '
        'structured NPK + fertilizer dose recommendations. '
        'Use `?call_id=<id>` to target a specific reading; omit for the latest.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional)')
    ],
    responses={
        200: OpenApiResponse(description='Recommendation data'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_recommendations(request, device_id):
    """Fertilizer & crop recommendations based on NPK readings."""
    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

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


# ── AI crop recommendation ────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='AI crop recommendation (ML model)',
    description=(
        'Runs the ML model against a SoiLENZ reading and returns a crop recommendation. '
        'Use `?call_id=<id>` to target a specific reading; omit for the latest reading.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional; defaults to latest)'),
    ],
    responses={
        200: OpenApiResponse(description='AI recommendation result'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_ai_recommendation(request, device_id):
    """ML-based crop recommendation using N, P, K, pH values from a reading."""
    from predicter.ai_model.model import run_model

    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    soil_nutrients = {
        'N'          : [reading.nitrogen],
        'P'          : [reading.phosphorous],
        'K'          : [reading.potassium],
        'temperature': [10],
        'humidity'   : [10],
        'ph'         : [reading.ph],
        'rainfall'   : [10],
    }
    result = run_model(soil_nutrients)

    return Response({
        'device_id'        : device.id,
        'reading_id'       : reading.id,
        'reading_date'     : reading.created_at,
        'recommended_crop' : result,
        'input_nutrients'  : {
            'nitrogen'   : reading.nitrogen,
            'phosphorous': reading.phosphorous,
            'potassium'  : reading.potassium,
            'ph'         : reading.ph,
        },
    })