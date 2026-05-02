"""PHBottle (ph_bottle) mobile API endpoints."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from devise_apis.mobile_serializers import FieldsReadingSerializer, FieldsReadingCreateSerializer
from ._common import fields_list_view, fields_create_view, fields_detail_view


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
    return fields_list_view(request, device_id)


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
    return fields_create_view(request, device_id)


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
    return fields_detail_view(request, device_id, call_id)