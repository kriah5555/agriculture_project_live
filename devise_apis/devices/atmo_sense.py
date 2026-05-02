"""SoilSparsh (atmo_sense) mobile API endpoints."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from devise_apis.mobile_serializers import FieldsReadingSerializer, FieldsReadingCreateSerializer
from ._common import fields_list_view, fields_create_view, fields_detail_view


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
    return fields_list_view(request, device_id)


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
    return fields_create_view(request, device_id)


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
    return fields_detail_view(request, device_id, call_id)