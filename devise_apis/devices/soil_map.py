"""SoilMap mobile API endpoints."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from devise_apis.mobile_serializers import FieldsReadingSerializer, FieldsReadingCreateSerializer
from ._common import fields_list_view, fields_create_view, fields_detail_view


@extend_schema(
    tags=['SoilMap'],
    summary='List SoilMap readings',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: FieldsReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soil_map_list(request, device_id):
    return fields_list_view(request, device_id)


@extend_schema(
    tags=['SoilMap'],
    summary='Create SoilMap reading',
    description=(
        'Submit a new soil map reading for a SoilMap device. '
        'field1=pH, field2=EC, field3=Nitrogen, field4=Phosphorus, field5=Potassium, '
        'field6=Organic Carbon, field7=Sulfur, field8=Fe, field9=Zn, field10=Cu, '
        'field11=B, field12=Mn, field13=Sand%, field14=Clay%, field15=Silt%, '
        'field16=NDVI, field17=Temperature, field18=Rainfall, field19=Elevation. '
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
def soil_map_create(request, device_id):
    return fields_create_view(request, device_id)


@extend_schema(
    tags=['SoilMap'],
    summary='Get a single SoilMap reading',
    responses={
        200: FieldsReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soil_map_detail(request, device_id, call_id):
    return fields_detail_view(request, device_id, call_id)