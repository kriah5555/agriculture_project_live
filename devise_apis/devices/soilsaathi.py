"""
SoiLENZ (soilsaathi) mobile API endpoints.

Routes (mounted under /api/mobile/devices/<id>/soilsaathi/):
  GET  /                      List readings
  POST /create/               Create reading
  GET  /<cid>/                Reading detail
  GET  /recommendations/      Fertilizer recommendations (FertilizerCalculation engine)
  GET  /ai-recommendation/    ML crop recommendation (?call_id=<id>)
  GET  /fertilizer-recommendation/  RDF-based fertilizer recommendation (?call_id=&state=&crop=)
  GET  /crop-recommendation/  Rule-based top-5 crop recommendation (?call_id=&state=)
  GET  /yield-options/        State/district/crop hierarchy + prefill for the yield estimator (?call_id=)
  GET  /yield-prediction/     District-level yield prediction (?call_id=&district=&crop=&soc=&pH=&N=&P=&K=)
  GET  /<cid>/pdf/            Download soil parameters PDF (from api-overview)
  GET  /<cid>/recommendation-pdf/  Download full 6-page SoiLENZ PDF report

All routes are mounted under /api/mobile/devices/<id>/  via mobile_urls.py.
Every write operation checks APICountThreshold before saving.
"""
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from agriapp.models import DeviseApis
from agriapp import FertilizerCalculation
from devise_apis.mobile_serializers import (
    SoilSaathiReadingSerializer,
    SoilSaathiReadingCreateSerializer,
)
from ._common import (
    check_threshold, DevicePagination, get_user_device, resolve_farmer,
    link_soil_lens_ph_bottle, unlink_soil_lens_ph_bottle,
)


# ── List readings ─────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='List SoiLENZ readings',
    parameters=[
        OpenApiParameter('page',     OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('per_page', OpenApiTypes.INT, description='Records per page (max 200)'),
    ],
    responses={200: SoilSaathiReadingSerializer(many=True)},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_list(request, device_id):
    """Paginated list of all SoiLENZ readings for a device."""
    device    = get_user_device(request, device_id)
    qs        = DeviseApis.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(SoilSaathiReadingSerializer(page, many=True).data)


# ── Create reading ────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Create SoiLENZ reading',
    description=(
        'Submit a new soil sensor reading for a SoiLENZ device. '
        'The API call threshold is checked **before** saving — if the device '
        'has reached its red-limit the request is rejected with HTTP 403.'
    ),
    request=SoilSaathiReadingCreateSerializer,
    responses={
        201: SoilSaathiReadingSerializer,
        400: OpenApiResponse(description='Validation error'),
        403: OpenApiResponse(description='API call threshold exceeded'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def soilsaathi_create(request, device_id):
    """
    Create a new SoiLENZ reading.
    Threshold is validated against APICountThreshold.red before the record is saved.
    """
    device = get_user_device(request, device_id)

    # ── Threshold guard ──────────────────────────────────────────────────────
    blocked = check_threshold(device)
    if blocked:
        return blocked

    farmer = resolve_farmer(request, request.data.get('farmer_id'))
    if isinstance(farmer, Response):
        return farmer

    serializer = SoilSaathiReadingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    reading = serializer.save(
        device    = device,
        devise_id = device.devise_id,
        serial_no = device.serial_no,
        farmer    = farmer,
    )
    return Response(SoilSaathiReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


# ── Single reading detail ─────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get a single SoiLENZ reading',
    responses={
        200: SoilSaathiReadingSerializer,
        404: OpenApiResponse(description='Not found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_detail(request, device_id, call_id):
    """Return full details for one SoiLENZ reading."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    return Response(SoilSaathiReadingSerializer(reading).data)


# ── Link / unlink to a PHBottle reading ───────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Link/unlink this SoiLENZ reading and a PHBottle reading',
    description=(
        '**POST** links this SoiLENZ reading to an existing PHBottle reading you own '
        '(pass its id as `ph_bottle_id`), copying the bottle\'s `field1` (pH) and '
        '`field3` (EC) into this reading\'s `ph`/`ec` fields. Works regardless of '
        'which reading was created first — the same relationship can also be made '
        'from the PHBottle side via its own link-soil-lens endpoint.\n\n'
        'If this would overwrite different pH/EC values already on this reading '
        '(or replace an existing link), POST returns **409** with a '
        '`warning` describing the current vs incoming values instead of saving — '
        'show that as a confirmation popup, then resubmit with `confirm: true`.\n\n'
        '**DELETE** clears the link (this reading keeps its last-synced pH/EC values).'
    ),
    request={'application/json': {'type': 'object', 'properties': {
        'ph_bottle_id': {'type': 'integer'}, 'confirm': {'type': 'boolean'},
    }, 'required': ['ph_bottle_id']}},
    responses={
        200: SoilSaathiReadingSerializer,
        400: OpenApiResponse(description='ph_bottle_id missing'),
        404: OpenApiResponse(description='PHBottle reading not found or not owned by you'),
        409: OpenApiResponse(description='Confirmation needed, or already linked elsewhere'),
    },
)
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def soilsaathi_link_ph_bottle(request, device_id, call_id):
    device    = get_user_device(request, device_id)
    soil_lens = get_object_or_404(DeviseApis, pk=call_id, device=device)

    if request.method == 'DELETE':
        if not soil_lens.ph_bottle_reading_id:
            return Response(
                {'detail': 'This SoiLENZ reading is not linked to any PHBottle reading.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return unlink_soil_lens_ph_bottle(soil_lens)

    ph_bottle_id = request.data.get('ph_bottle_id')
    if not ph_bottle_id:
        return Response({'detail': 'ph_bottle_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    confirm = str(request.data.get('confirm', False)).lower() in ('1', 'true', 'yes')
    return link_soil_lens_ph_bottle(request, soil_lens, ph_bottle_id, confirm)


# ── Recommendations ───────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get fertilizer recommendations',
    description=(
        'Runs the FertilizerCalculation engine against a reading and returns '
        'structured NPK + fertilizer dose recommendations. '
        'Use `?call_id=<id>` to target a specific reading; omit for the latest.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional)')
    ],
    responses={
        200: OpenApiResponse(description='Recommendation data'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_recommendations(request, device_id):
    """Fertilizer & crop recommendations based on NPK readings."""
    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    crops_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(
        reading.nitrogen, reading.phosphorous, reading.potassium,
        reading.ph, reading.ec, reading.oc, reading.crop_type,
    )

    return Response({
        'device_id'      : device.id,
        'reading_id'     : reading.id,
        'reading_date'   : reading.created_at,
        'crop_type'      : reading.crop_type,
        'npk'            : {
            'nitrogen'   : reading.nitrogen,
            'phosphorous': reading.phosphorous,
            'potassium'  : reading.potassium,
            'ph'         : reading.ph,
            'ec'         : reading.ec,
            'oc'         : reading.oc,
        },
        'recommendations': crops_data,
    })


# ── AI crop recommendation ────────────────────────────────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='AI crop recommendation (ML model)',
    description=(
        'Runs the ML model against a SoiLENZ reading and returns a crop recommendation. '
        'Use `?call_id=<id>` to target a specific reading; omit for the latest reading.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional; defaults to latest)'),
    ],
    responses={
        200: OpenApiResponse(description='AI recommendation result'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_ai_recommendation(request, device_id):
    """ML-based crop recommendation using N, P, K, pH values from a reading."""
    from agri_ai.crop import run_model

    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    # Fetch real climate for device location — required for the model
    from reports.views import _fetch_climate_for_recommendation
    from agriapp.models import DeviseLocation
    loc = DeviseLocation.objects.filter(devise=device).first()
    if not (loc and loc.latitude and loc.longitude):
        return Response(
            {'detail': 'Device has no GPS location set. Cannot run crop recommendation.'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    temperature, humidity, rainfall = _fetch_climate_for_recommendation(
        float(loc.latitude), float(loc.longitude)
    )

    soil_nutrients = {
        'N'          : [reading.nitrogen],
        'P'          : [reading.phosphorous],
        'K'          : [reading.potassium],
        'temperature': [temperature],
        'humidity'   : [humidity],
        'ph'         : [reading.ph],
        'rainfall'   : [rainfall],
    }
    result = run_model(soil_nutrients)

    return Response({
        'device_id'        : device.id,
        'reading_id'       : reading.id,
        'reading_date'     : reading.created_at,
        'recommended_crop' : result,
        'input_nutrients'  : {
            'nitrogen'   : reading.nitrogen,
            'phosphorous': reading.phosphorous,
            'potassium'  : reading.potassium,
            'ph'         : reading.ph,
        },
    })


# ── Fertilizer recommendation (RDF Rule Book engine) ──────────────────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get RDF-based fertilizer recommendation',
    description=(
        'Runs the RDF Rule Book engine against a reading and returns per-parameter '
        'soil status, adjusted N:P:K, and Urea/DAP/MOP doses. State/crop are taken '
        'from the linked farmer profile (falling back to the reading\'s crop_type) '
        'unless explicitly overridden with `state`/`crop` — use the override when '
        'the reading has no linked farmer or the auto-detected crop name doesn\'t '
        'match the reference dataset.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional; defaults to latest)'),
        OpenApiParameter('state', OpenApiTypes.STR, description='Override state (must match the reference dataset)'),
        OpenApiParameter('crop', OpenApiTypes.STR, description='Override crop name'),
    ],
    responses={
        200: OpenApiResponse(description='Fertilizer recommendation result (or an {"error": ...} payload when state/crop can\'t be resolved)'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_fertilizer_recommendation(request, device_id):
    """RDF-based fertilizer recommendation for a SoiLENZ reading."""
    from reports.views import build_fertilizer_recommendation

    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    result = build_fertilizer_recommendation(
        reading,
        state_override=request.query_params.get('state'),
        crop_override=request.query_params.get('crop'),
    )

    return Response({
        'device_id'   : device.id,
        'reading_id'  : reading.id,
        'reading_date': reading.created_at,
        **result,
    })


# ── Detailed crop recommendation (rule-based, explainable, top-5) ─────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get detailed crop recommendation (rule-based, top 5)',
    description=(
        'Runs the rule-based, explainable multi-crop recommender against a reading\'s '
        'own pH, EC, OC, N-P-K and micronutrient values. Returns the top 5 best-suited '
        'crops for the state, each with a per-parameter score breakdown, deficiency '
        'notes, and a Crop Guide (duration, sowing season, water requirement, pests, '
        'recommended fertilizers, harvest time). State is taken from the linked farmer '
        'profile unless explicitly overridden with `state` — use the override when the '
        'reading has no linked farmer or the auto-detected state doesn\'t match the '
        'reference dataset.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional; defaults to latest)'),
        OpenApiParameter('state', OpenApiTypes.STR, description='Override state (must match the reference dataset)'),
    ],
    responses={
        200: OpenApiResponse(description='Top-5 crop recommendation result (or an {"error": ...} payload when state can\'t be resolved)'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_crop_recommendation(request, device_id):
    """Rule-based top-5 crop recommendation for a SoiLENZ reading."""
    from reports.views import build_crop_recommendation_v2

    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    result = build_crop_recommendation_v2(
        reading,
        state_override=request.query_params.get('state'),
    )

    return Response({
        'device_id'   : device.id,
        'reading_id'  : reading.id,
        'reading_date': reading.created_at,
        **result,
    })


# ── Yield prediction (district-level, formula-based + live NDVI) ─────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Get state/district/crop hierarchy + prefill for the yield estimator',
    description=(
        'Returns the full State -> District -> [crops] hierarchy used to drive the '
        'yield estimator\'s cascading dropdowns, plus a prefill block (state/district/crop '
        'auto-detected from the linked farmer + reading, and soc/pH/N/P/K taken from the '
        'reading\'s own soil values) so the mobile client can preselect everything.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional; defaults to latest)'),
    ],
    responses={
        200: OpenApiResponse(description='Hierarchy + prefill payload'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_yield_options(request, device_id):
    """Hierarchy + prefill for the yield estimator (mirrors the web tab's initial context)."""
    from agri_ai.yield_estimator import get_hierarchy

    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    hierarchy = get_hierarchy()
    farmer    = reading.farmer

    state = next((s for s in hierarchy if farmer and s.lower() == (farmer.state or '').lower()), '')
    district = ''
    if state and farmer:
        district = next((d for d in hierarchy[state] if d.lower() == (farmer.district or '').lower()), '')
    crop = ''
    if district:
        crop = next((c for c in hierarchy[state][district] if c.lower() == (reading.crop_type or '').lower()), '')

    return Response({
        'device_id'  : device.id,
        'reading_id' : reading.id,
        'hierarchy'  : hierarchy,
        'prefill'    : {
            'state'   : state,
            'district': district,
            'crop'    : crop,
            'soc'     : reading.oc or 0.5,
            'pH'      : reading.ph or 6.5,
            'N'       : reading.nitrogen or 200,
            'P'       : reading.phosphorous or 20,
            'K'       : reading.potassium or 150,
            'lat'     : reading.latitude,
            'lon'     : reading.longitude,
        },
    })


@extend_schema(
    tags=['SoiLENZ'],
    summary='Get predicted crop yield for a district/crop',
    description=(
        'predicted_yield = potential_yield (historical district-crop average) * soil_factor '
        '(from soc/pH/N/P/K) * water_factor (rainfall + irrigation) * ndvi_factor (live MODIS '
        'NDVI at the reading\'s own lat/lon via GEE, defaulting to 0.7 if unavailable). '
        'soc/pH/N/P/K default to the reading\'s own values when not passed explicitly.'
    ),
    parameters=[
        OpenApiParameter('call_id', OpenApiTypes.INT, description='Specific reading ID (optional; defaults to latest)'),
        OpenApiParameter('district', OpenApiTypes.STR, description='District name (required, must match reference dataset)'),
        OpenApiParameter('crop', OpenApiTypes.STR, description='Crop name (required, must match reference dataset)'),
        OpenApiParameter('soc', OpenApiTypes.FLOAT, description='Soil organic carbon % (default: reading value)'),
        OpenApiParameter('pH', OpenApiTypes.FLOAT, description='Soil pH (default: reading value)'),
        OpenApiParameter('N', OpenApiTypes.FLOAT, description='Nitrogen kg/ha (default: reading value)'),
        OpenApiParameter('P', OpenApiTypes.FLOAT, description='Phosphorus kg/ha (default: reading value)'),
        OpenApiParameter('K', OpenApiTypes.FLOAT, description='Potassium kg/ha (default: reading value)'),
    ],
    responses={
        200: OpenApiResponse(description='Yield prediction result (or {"status": "not_available", ...} when no data for the district/crop)'),
        400: OpenApiResponse(description='Missing district/crop'),
        404: OpenApiResponse(description='No readings found'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_yield_prediction(request, device_id):
    """District-level yield prediction for a SoiLENZ reading."""
    from agri_ai.yield_estimator import estimate_yield

    device  = get_user_device(request, device_id)
    call_id = request.query_params.get('call_id')

    if call_id:
        reading = get_object_or_404(DeviseApis, pk=call_id, device=device)
    else:
        reading = DeviseApis.objects.filter(device=device).order_by('-created_at').first()
        if not reading:
            return Response({'detail': 'No readings found for this device.'}, status=status.HTTP_404_NOT_FOUND)

    district = request.query_params.get('district', '').strip()
    crop     = request.query_params.get('crop', '').strip()
    if not district or not crop:
        return Response({'detail': 'district and crop are required.'}, status=status.HTTP_400_BAD_REQUEST)

    def _param(name, fallback):
        raw = request.query_params.get(name)
        return float(raw) if raw not in (None, '') else fallback

    result = estimate_yield(
        district, crop,
        soc=_param('soc', reading.oc or 0.5),
        pH=_param('pH', reading.ph or 6.5),
        N=_param('N', reading.nitrogen or 200),
        P=_param('P', reading.phosphorous or 20),
        K=_param('K', reading.potassium or 150),
        lat=reading.latitude, lon=reading.longitude,
    )

    return Response({
        'device_id'   : device.id,
        'reading_id'  : reading.id,
        'reading_date': reading.created_at,
        **result,
    })


# ── Soil parameters PDF (mirrors /download_api_response_pdf/<pk>/) ────────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Download soil parameters PDF for a reading',
    description='Returns a PDF of the soil test parameters for the given reading. Same report shown on the api-overview page.',
    responses={200: OpenApiResponse(description='PDF file download')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_pdf(request, device_id, call_id):
    device  = get_user_device(request, device_id)
    get_object_or_404(DeviseApis, pk=call_id, device=device)

    from agriapp.views import _build_api_response_pdf
    return _build_api_response_pdf(call_id)


# ── Full 6-page SoiLENZ PDF report (mirrors /crop-recommendation-pdf/) ────────

@extend_schema(
    tags=['SoiLENZ'],
    summary='Download full SoiLENZ 6-page PDF report for a reading',
    description='Generates the complete SoiLENZ PDF report (soil chemistry, fertility assessment, recommendations). Same report available on the crop-recommendation-dashboard page.',
    responses={200: OpenApiResponse(description='PDF file download')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def soilsaathi_recommendation_pdf(request, device_id, call_id):
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApis, pk=call_id, device=device)

    from reports.views import download_recommendation_pdf
    request.GET = request.GET.copy()
    request.GET['api_id'] = str(call_id)
    return download_recommendation_pdf(request)