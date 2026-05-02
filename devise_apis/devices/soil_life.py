"""SoilLIFE (soil_life) mobile API endpoints."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from devise_apis.mobile_serializers import FieldsReadingSerializer, FieldsReadingCreateSerializer
from ._common import fields_list_view, fields_create_view, fields_detail_view


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
    return fields_list_view(request, device_id)


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
    return fields_create_view(request, device_id)


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
    return fields_detail_view(request, device_id, call_id)