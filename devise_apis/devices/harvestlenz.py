"""HarvestLenz (harvestlenz) mobile API endpoints — fruit quality grading from a photo."""
import os

from django.conf import settings
from django.core.files.base import ContentFile
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
from agri_ai.fruit import analyze_fruit_image, FruitAnalysisError, FRUIT_INFO, SUPPORTED_FRUITS
from devise_apis.mobile_serializers import HarvestLenzReadingSerializer, harvestlenz_annotated_path
from ._common import DevicePagination, check_threshold, resolve_farmer


def _resolve_device(request, device_id):
    """
    Returns the Devise for `device_id`, or a 403 Response.
    Staff/superuser may act on any HarvestLenz device (admin scan-on-behalf-of-user flow),
    regular users only on their own — same split as LeafLenz.
    """
    device = get_object_or_404(Devise, pk=device_id, devise_type='harvestlenz')
    if not (request.user.is_staff or request.user.is_superuser or device.user_id == request.user.id):
        return Response({'detail': 'You do not have access to this device.'}, status=status.HTTP_403_FORBIDDEN)
    return device


def _to_float(value):
    try:
        return float(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _to_bool(value, default=True):
    if value in (None, ''):
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


@extend_schema(
    tags=['HarvestLenz'],
    summary='List HarvestLenz scans',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: HarvestLenzReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def harvestlenz_list(request, device_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device
    qs        = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    ctx       = {'request': request}
    return paginator.get_paginated_response(HarvestLenzReadingSerializer(page, many=True, context=ctx).data)


@extend_schema(
    tags=['HarvestLenz'],
    summary='Grade a fruit photo',
    description=(
        'Upload a fruit photo for a HarvestLenz device. Segments each fruit, checks it matches the selected '
        'fruit type, grades it Good / Better / Reject with the per-fruit Keras model, and adds shelf life, '
        'market and price estimates. Saves the photo + an annotated copy and one DeviseApisFields row '
        '(`tag` = fruit type, `field1`..`field10` = summary — see /device-types/harvestlenz/fields/). '
        'The response also contains the per-fruit `analysis.fruits` list, which is not stored. '
        'Threshold is checked before saving.'
    ),
    request={'multipart/form-data': {'type': 'object', 'properties': {
        'image':      {'type': 'string', 'format': 'binary', 'description': 'Fruit photo (JPEG/PNG/WEBP)'},
        'fruit_type': {'type': 'string', 'enum': SUPPORTED_FRUITS + ['auto'],
                       'description': "Selected fruit, or 'auto' to detect it (default 'auto')"},
        'is_single':  {'type': 'boolean', 'description': 'true = one fruit fills the photo (default), false = basket of several'},
        'farmer_id':  {'type': 'integer', 'description': 'Optional farmer to link this scan to'},
        'latitude':   {'type': 'number'},
        'longitude':  {'type': 'number'},
    }, 'required': ['image']}},
    responses={
        201: OpenApiResponse(description='Saved reading (HarvestLenzReadingSerializer) + `analysis` with per-fruit results'),
        400: OpenApiResponse(description='No image / unreadable image / unsupported fruit_type'),
        403: OpenApiResponse(description='API call threshold exceeded'),
        503: OpenApiResponse(description='Grading model not available on the server'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def harvestlenz_scan(request, device_id):
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

    try:
        analysis, annotated_jpeg = analyze_fruit_image(
            image_file,
            fruit_type=request.data.get('fruit_type') or 'auto',
            is_single=_to_bool(request.data.get('is_single'), default=True),
        )
    except FruitAnalysisError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except RuntimeError as e:
        return Response({'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    fs = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, 'harvestlenz_uploads'),
        base_url=settings.MEDIA_URL + 'harvestlenz_uploads/',
    )
    file_name = fs.save(image_file.name, image_file)
    image_url = fs.url(file_name)
    if annotated_jpeg:
        # Must sit at exactly '<saved name>_annotated.jpg' (the serializer derives
        # it from image_path), so replace any stale file instead of letting
        # storage pick a new name.
        annotated_name = harvestlenz_annotated_path(file_name)
        fs.delete(annotated_name)
        fs.save(annotated_name, ContentFile(annotated_jpeg))

    summary = analysis['summary']
    reading = DeviseApisFields.objects.create(
        device     = device,
        farmer     = farmer,
        tag        = analysis['fruit_type'],
        image_path = image_url,
        field1     = analysis['score'],
        field2     = summary['good'],
        field3     = summary['better'],
        field4     = summary['reject'],
        field5     = analysis['total_fruits'],
        field6     = analysis['average_shelf_life'],
        field7     = analysis['total_price'],
        field8     = analysis['estimated_selling_price'],
        field9     = 1.0 if analysis['mismatch'] else 0.0,
        field10    = analysis['average_confidence'],
        latitude   = _to_float(request.data.get('latitude')),
        longitude  = _to_float(request.data.get('longitude')),
    )
    data = HarvestLenzReadingSerializer(reading, context={'request': request}).data
    data['analysis'] = analysis
    return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['HarvestLenz'],
    summary='Get a single HarvestLenz scan',
    responses={
        200: HarvestLenzReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def harvestlenz_detail(request, device_id, call_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(HarvestLenzReadingSerializer(reading, context={'request': request}).data)


@extend_schema(
    tags=['HarvestLenz'],
    summary='HarvestLenz scan stats for a device',
    description='Total scans and fruits graded, grade totals and per-fruit-type scan distribution for a device.',
    responses={200: OpenApiResponse(description='Scan stats', response={
        'type': 'object',
        'properties': {
            'total_scans'       : {'type': 'integer'},
            'total_fruits'      : {'type': 'integer'},
            'grade_totals'      : {'type': 'object', 'properties': {
                'good': {'type': 'integer'}, 'better': {'type': 'integer'}, 'reject': {'type': 'integer'},
            }},
            'mismatch_scans'    : {'type': 'integer'},
            'fruit_distribution': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {
                    'fruit_type': {'type': 'string'},
                    'fruit_name': {'type': 'string'},
                    'count'     : {'type': 'integer'},
                }},
            },
        },
    })},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def harvestlenz_stats(request, device_id):
    device = _resolve_device(request, device_id)
    if isinstance(device, Response):
        return device

    readings = DeviseApisFields.objects.filter(device=device)
    counts = {}
    good = better = reject = total_fruits = mismatches = 0
    for tag, f2, f3, f4, f5, f9 in readings.values_list('tag', 'field2', 'field3', 'field4', 'field5', 'field9'):
        key = (tag or 'unknown').lower()
        counts[key] = counts.get(key, 0) + 1
        good, better, reject = good + int(f2), better + int(f3), reject + int(f4)
        total_fruits += int(f5)
        mismatches += 1 if f9 else 0

    fruit_distribution = [
        {'fruit_type': key, 'fruit_name': FRUIT_INFO.get(key, {}).get('name', key.capitalize()), 'count': count}
        for key, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return Response({
        'total_scans'       : readings.count(),
        'total_fruits'      : total_fruits,
        'grade_totals'      : {'good': good, 'better': better, 'reject': reject},
        'mismatch_scans'    : mismatches,
        'fruit_distribution': fruit_distribution,
    })


@extend_schema(
    tags=['HarvestLenz'],
    summary='HarvestLenz supported fruits',
    description="Fruits that can be graded (for the fruit_type dropdown), with shelf-life and market rules per grade. "
                "'auto' is also accepted as fruit_type.",
    responses={200: OpenApiResponse(description='List of supported fruits')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def harvestlenz_fruits(request):
    return Response({'fruits': [
        {
            'key'            : key,
            'name'           : FRUIT_INFO[key]['name'],
            'scientific'     : FRUIT_INFO[key]['scientific'],
            'shelf_life_days': FRUIT_INFO[key]['shelf_life'],
            'market'         : FRUIT_INFO[key]['market'],
        }
        for key in SUPPORTED_FRUITS
    ]})
