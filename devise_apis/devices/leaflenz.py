"""LeafLenz (leaflenz) mobile API endpoints — leaf disease detection from a photo."""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from agriapp.models import Devise, DeviseApisFields
from agri_ai.leaf import predict_leaf_disease, parse_class_label, CONFIDENCE_THRESHOLD
from agri_ai.leaf.utils import DISEASE_INFO
from devise_apis.mobile_serializers import LeafLenzReadingSerializer
from ._common import DevicePagination, check_threshold, resolve_farmer


def _resolve_device(request, device_id):
    """
    Returns the Devise for `device_id`, or a 403 Response.
    Staff/superuser may act on any LeafLenz device (admin scan-on-behalf-of-user flow),
    regular users only on their own — matches soilmap's admin/owner split.
    """
    device = get_object_or_404(Devise, pk=device_id, devise_type='leaflenz')
    if not (request.user.is_staff or request.user.is_superuser or device.user_id == request.user.id):
        return Response({'detail': 'You do not have access to this device.'}, status=status.HTTP_403_FORBIDDEN)
    return device


@extend_schema(
    tags=['LeafLenz'],
    summary='List LeafLenz scans',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: LeafLenzReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaflenz_list(request, device_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device
    qs        = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    ctx       = {'request': request}
    return paginator.get_paginated_response(LeafLenzReadingSerializer(page, many=True, context=ctx).data)


@extend_schema(
    tags=['LeafLenz'],
    summary='Scan a leaf photo for disease',
    description=(
        'Upload a leaf photo for a LeafLenz device. Runs ONNX inference (with test-time augmentation) '
        'to classify the plant and disease, then saves the image and prediction as a DeviseApisFields record. '
        '`tag` stores the raw predicted class label, `field1` stores the confidence (0.0-1.0). '
        'Threshold is checked before saving.'
    ),
    request={'multipart/form-data': {'type': 'object', 'properties': {
        'image':       {'type': 'string', 'format': 'binary', 'description': 'Leaf photo'},
        'farmer_id':   {'type': 'integer', 'description': 'Optional farmer to link this scan to'},
        'latitude':    {'type': 'number'},
        'longitude':   {'type': 'number'},
    }, 'required': ['image']}},
    responses={
        201: LeafLenzReadingSerializer,
        400: OpenApiResponse(description='No image provided / validation error'),
        403: OpenApiResponse(description='API call threshold exceeded'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def leaflenz_scan(request, device_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device
    blocked = check_threshold(device)
    if blocked:
        return blocked

    image_file = request.FILES.get('image')
    if not image_file:
        return Response({'detail': "No image file provided. Key must be 'image'."}, status=status.HTTP_400_BAD_REQUEST)

    farmer = resolve_farmer(request, request.data.get('farmer_id'))
    if isinstance(farmer, Response):
        return farmer

    predicted_label, confidence, _top5 = predict_leaf_disease(image_file)
    if confidence < CONFIDENCE_THRESHOLD:
        predicted_label = 'fallback'

    fs = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, 'leaflenz_uploads'),
        base_url=settings.MEDIA_URL + 'leaflenz_uploads/',
    )
    file_name = fs.save(image_file.name, image_file)

    def _to_float(value):
        try:
            return float(value) if value not in (None, '') else None
        except (TypeError, ValueError):
            return None

    reading = DeviseApisFields.objects.create(
        device     = device,
        farmer     = farmer,
        tag        = predicted_label,
        image_path = fs.url(file_name),
        field1     = confidence,
        latitude   = _to_float(request.data.get('latitude')),
        longitude  = _to_float(request.data.get('longitude')),
    )
    return Response(
        LeafLenzReadingSerializer(reading, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=['LeafLenz'],
    summary='Get a single LeafLenz scan',
    responses={
        200: LeafLenzReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaflenz_detail(request, device_id, call_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(LeafLenzReadingSerializer(reading, context={'request': request}).data)


@extend_schema(
    tags=['LeafLenz'],
    summary='LeafLenz scan stats for a device',
    description=(
        'Total scan count and plant-type distribution for a LeafLenz device, derived from `tag` '
        '(the raw predicted class label) on its DeviseApisFields records. No accuracy/feedback '
        'metrics are tracked (LeafLenz reuses the shared readings table, which has no feedback columns).'
    ),
    responses={200: OpenApiResponse(description='Scan stats', response={
        'type': 'object',
        'properties': {
            'total_scans':        {'type': 'integer'},
            'plant_distribution': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {
                    'plant_name': {'type': 'string'},
                    'count':      {'type': 'integer'},
                }},
            },
        },
    })},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaflenz_stats(request, device_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device

    readings = DeviseApisFields.objects.filter(device=device)
    counts = {}
    for tag in readings.values_list('tag', flat=True):
        plant, _ = parse_class_label(tag or 'fallback')
        counts[plant] = counts.get(plant, 0) + 1

    plant_distribution = [
        {'plant_name': plant, 'count': count}
        for plant, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return Response({'total_scans': readings.count(), 'plant_distribution': plant_distribution})


@extend_schema(
    tags=['LeafLenz'],
    summary='LeafLenz disease encyclopedia',
    description='Static plant/disease reference data (description, symptoms, treatment) keyed by raw class label.',
    responses={200: OpenApiResponse(description='Disease encyclopedia dict, keyed by raw class label')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaflenz_diseases(request):
    return Response(DISEASE_INFO)
