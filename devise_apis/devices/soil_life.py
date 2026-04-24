"""
SoilLIFE mobile API endpoints.

All routes are mounted under /api/mobile/devices/<id>/  via mobile_urls.py.
Every write operation checks APICountThreshold before saving.
SoilLIFE shares the DeviseApisFields model with SoilSparsh (atmo_sense);
labeled field names are resolved at serialisation time from SOIL_LIFE_FIELDS.
"""
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from agriapp.models import DeviseApisFields
from devise_apis.mobile_serializers import (
    FieldsReadingSerializer,
    FieldsReadingCreateSerializer,
)
from ._common import check_threshold, DevicePagination, get_user_device


# ── List readings ─────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilLIFE'],
    summary='List SoilLIFE readings',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: FieldsReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soil_life_list(request, device_id):
    """Paginated list of all SoilLIFE readings for a device."""
    device    = get_user_device(request, device_id)
    qs        = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(FieldsReadingSerializer(page, many=True).data)


# ── Create reading ────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilLIFE'],
    summary='Create SoilLIFE reading',
    description=(
        'Submit a new soil bio-sensor reading for a SoilLIFE device. '
        'Fields: field1 (CO₂), field2 (Methane), field3 (Ammonia), '
        'field4 (Hydrogen Sulfide), field5 (Soil Moisture), field6 (Soil Temp), '
        'field7 (pH), field8 (EC). '
        'Threshold is checked before saving.'
    ),
    request=FieldsReadingCreateSerializer,
    responses={
        201: FieldsReadingSerializer,
        400: OpenApiResponse(description='Validation error'),
        403: OpenApiResponse(description='API call threshold exceeded'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def soil_life_create(request, device_id):
    """
    Create a new SoilLIFE reading.
    Threshold is validated against APICountThreshold.red before saving.
    """
    device = get_user_device(request, device_id)

    # ── Threshold guard ──────────────────────────────────────────────────────
    blocked = check_threshold(device)
    if blocked:
        return blocked

    serializer = FieldsReadingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    reading = serializer.save(device=device)
    return Response(FieldsReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


# ── Single reading detail ─────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilLIFE'],
    summary='Get a single SoilLIFE reading',
    responses={
        200: FieldsReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soil_life_detail(request, device_id, call_id):
    """Return full details for one SoilLIFE reading."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(FieldsReadingSerializer(reading).data)