"""
PHBottle mobile API endpoints.

Fields:
  field1 — pH Value
  field2 — pH Voltage (mV)
  field3 — EC Value (mS/cm)
  field4 — EC Voltage (mV)

All routes are mounted under /api/mobile/devices/<id>/ph-bottle/ via mobile_urls.py.
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
    tags=['PHBottle'],
    summary='List PHBottle readings',
    description=(
        'Returns paginated pH and EC sensor readings for a PHBottle device. '
        'Each record contains `field1` (pH Value), `field2` (pH Voltage mV), '
        '`field3` (EC Value mS/cm), `field4` (EC Voltage mV), plus a '
        '`labeled_fields` map for easy display.'
    ),
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number (default 1)'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (default 50, max 200)'),
    ],
    responses={200: FieldsReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ph_bottle_list(request, device_id):
    """Paginated list of all PHBottle readings for a device."""
    device    = get_user_device(request, device_id)
    qs        = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(FieldsReadingSerializer(page, many=True).data)


# ── Create reading ────────────────────────────────────────────────────────────

@extend_schema(
    tags=['PHBottle'],
    summary='Create PHBottle reading',
    description=(
        'Submit a new pH and EC reading for a PHBottle device. '
        'Send these fields:\n\n'
        '| Field   | Description          |\n'
        '|---------|----------------------|\n'
        '| field1  | pH Value             |\n'
        '| field2  | pH Voltage (mV)      |\n'
        '| field3  | EC Value (mS/cm)     |\n'
        '| field4  | EC Voltage (mV)      |\n\n'
        'Optional: `tag`. '
        'The API call threshold is validated before saving.'
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
def ph_bottle_create(request, device_id):
    """Create a new PHBottle reading with threshold enforcement."""
    device = get_user_device(request, device_id)

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
    tags=['PHBottle'],
    summary='Get a single PHBottle reading',
    responses={
        200: FieldsReadingSerializer,
        404: OpenApiResponse(description='Reading not found or not accessible'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ph_bottle_detail(request, device_id, call_id):
    """Return full details for one PHBottle reading."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(FieldsReadingSerializer(reading).data)