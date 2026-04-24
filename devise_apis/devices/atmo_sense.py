"""
SoilSparsh (atmo_sense) mobile API endpoints.

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

from agriapp.models import DeviseApisFields
from devise_apis.mobile_serializers import (
    FieldsReadingSerializer,
    FieldsReadingCreateSerializer,
)
from ._common import check_threshold, DevicePagination, get_user_device


# ── List readings ─────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilSparsh'],
    summary='List SoilSparsh readings',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: FieldsReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def atmo_sense_list(request, device_id):
    """Paginated list of all SoilSparsh (AtmoSense) readings for a device."""
    device    = get_user_device(request, device_id)
    qs        = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(FieldsReadingSerializer(page, many=True).data)


# ── Create reading ────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilSparsh'],
    summary='Create SoilSparsh reading',
    description=(
        'Submit a new atmospheric sensor reading for a SoilSparsh device. '
        'Fields: field1 (Soil Temp), field2 (Soil Moisture), field3 (Atmos Temp), '
        'field4 (Atmos Humidity), field5 (Light Intensity). '
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
def atmo_sense_create(request, device_id):
    """
    Create a new SoilSparsh reading.
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
    tags=['SoilSparsh'],
    summary='Get a single SoilSparsh reading',
    responses={
        200: FieldsReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def atmo_sense_detail(request, device_id, call_id):
    """Return full details for one SoilSparsh reading."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(FieldsReadingSerializer(reading).data)