"""PHBottle (ph_bottle) mobile API endpoints."""
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from agriapp.models import DeviseApis, DeviseApisFields
from devise_apis.mobile_serializers import (
    FieldsReadingSerializer, FieldsReadingCreateSerializer, SoilSaathiReadingSerializer,
)
from ._common import (
    fields_list_view, fields_create_view, fields_detail_view, get_user_device,
    link_soil_lens_ph_bottle, unlink_soil_lens_ph_bottle,
)


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


# ── Link / unlink to a SoiLENZ reading ────────────────────────────────────────

@extend_schema(
    tags=['PHBottle'],
    summary='Link/unlink this PHBottle reading and a SoiLENZ reading',
    description=(
        '**POST** links this PHBottle reading to an existing SoiLENZ reading you own '
        '(pass its id as `soil_lens_id`), copying `field1` (pH) and `field3` (EC) '
        'into the SoiLENZ reading\'s `ph`/`ec` fields. Works regardless of which '
        'reading was created first — the same relationship can also be made from '
        'the SoiLENZ side via its own link-ph-bottle endpoint.\n\n'
        'If this would overwrite different pH/EC values already on the SoiLENZ '
        'reading (or replace an existing link), POST returns **409** with '
        'a `warning` describing the current vs incoming values instead of saving — '
        'show that as a confirmation popup, then resubmit with `confirm: true`.\n\n'
        '**DELETE** clears the link (the SoiLENZ reading keeps its last-synced pH/EC values).'
    ),
    request={'application/json': {'type': 'object', 'properties': {
        'soil_lens_id': {'type': 'integer'}, 'confirm': {'type': 'boolean'},
    }, 'required': ['soil_lens_id']}},
    responses={
        200: SoilSaathiReadingSerializer,
        400: OpenApiResponse(description='soil_lens_id missing'),
        404: OpenApiResponse(description='SoiLENZ reading not found or not owned by you'),
        409: OpenApiResponse(description='Confirmation needed, or already linked elsewhere'),
    },
)
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def ph_bottle_link_soil_lens(request, device_id, call_id):
    device    = get_user_device(request, device_id)
    ph_bottle = get_object_or_404(DeviseApisFields, pk=call_id, device=device)

    if request.method == 'DELETE':
        try:
            soil_lens = ph_bottle.linked_soil_lens
        except DeviseApis.DoesNotExist:
            return Response(
                {'detail': 'This PHBottle reading is not linked to any SoiLENZ reading.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return unlink_soil_lens_ph_bottle(soil_lens)

    soil_lens_id = request.data.get('soil_lens_id')
    if not soil_lens_id:
        return Response({'detail': 'soil_lens_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    soil_lens = DeviseApis.objects.filter(pk=soil_lens_id, device__user=request.user).first()
    if not soil_lens:
        return Response(
            {'detail': 'SoiLENZ reading not found or not owned by you.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    confirm = str(request.data.get('confirm', False)).lower() in ('1', 'true', 'yes')
    return link_soil_lens_ph_bottle(request, soil_lens, ph_bottle.pk, confirm)