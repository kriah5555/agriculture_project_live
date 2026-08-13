import io
import os
import sys
import pickle

from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponse

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from agriapp.models    import Devise, DeviseApisFields
from agri_ai.zone      import classify_zone as _classify_zone, classify_global_climate_zone, CLIMATE_ZONE_METADATA
from agri_ai.zone.classifier import get_location_details
from agri_ai.analysis  import analyze_polygon as _analyze_polygon
from agri_ai.gee       import get_crop_coverage_map, CROP_CATALOG
from agri_ai.fertilizer import (
    recommend_fertilizer,
    get_states as get_fertilizer_states,
    get_crops_for_state as get_fertilizer_crops_for_state,
)

# ── ML pipeline setup ─────────────────────────────────────────────────────────
from agri_ai.soil     import load_models, predict_for_point, classify_fertility
from agri_ai.features import get_weather, get_ndvi, get_elevation, get_soil_texture

lgbm_models, rf_model = {}, None
try:
    lgbm_models, rf_model = load_models()
except Exception as e:
    print(f"[soilmap] model load warning: {e}")


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser


class SoilMapDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'soilmap/dashboard.html'

    def get_context_data(self, **kwargs):
        context  = super().get_context_data(**kwargs)
        devices  = Devise.objects.filter(devise_type='soil_map')

        for device in devices:
            device.api_count = DeviseApisFields.objects.filter(device=device).count()

        context['devices']     = devices
        context['active_page'] = 'soil-map'
        return context


@login_required
def soil_map_view(request, device_id):
    """User-facing map — only their own device."""
    device = get_object_or_404(Devise, pk=device_id, user=request.user)
    return render(request, 'soilmap/soil_map.html', {'device': device})


def soil_map_admin_view(request, device_id):
    """Admin-facing map — any device, staff/superuser only."""
    if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)):
        return HttpResponseForbidden()
    device = get_object_or_404(Devise, pk=device_id)
    return render(request, 'soilmap/soil_map.html', {'device': device})


# ── SoilMap API helpers ───────────────────────────────────────────────────────

def _avg(readings, attr):
    vals = [getattr(r, attr) for r in readings if getattr(r, attr) is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


# ── predict_soil ──────────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilMap'],
    summary='AI soil prediction for a point or polygon',
    description=(
        'Run LightGBM inference for a lat/lon point or a drawn polygon (centroid is used). '
        'Returns predicted soil chemistry (pH, EC, N, P, K, OC, S, Fe, Zn, Cu, B, Mn), '
        'environmental factors (NDVI, temperature, rainfall, elevation), '
        'and a fertility assessment (Low / Medium / High).\n\n'
        'Requires trained LightGBM models to be present in agri_ai/soil/models/. Returns 503 if models are not loaded.'
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'lat':     {'type': 'number', 'example': 15.3173, 'description': 'Latitude (use with lon)'},
                'lon':     {'type': 'number', 'example': 75.7139, 'description': 'Longitude (use with lat)'},
                'polygon': {
                    'type': 'array',
                    'items': {'type': 'array', 'items': {'type': 'number'}},
                    'example': [[15.31, 75.71], [15.32, 75.71], [15.32, 75.72], [15.31, 75.72]],
                    'description': 'Array of [lat, lon] pairs (≥3 points). Centroid is used for prediction.',
                },
            },
        }
    },
    responses={
        200: OpenApiResponse(description='Predicted soil metrics', response={
            'type': 'object',
            'properties': {
                'status':                   {'type': 'string', 'example': 'success'},
                'prediction_type':          {'type': 'string', 'example': 'point'},
                'fertility_assessment':     {'type': 'string', 'example': 'Medium'},
                'environmental_factors':    {'type': 'object'},
                'predicted_soil_chemistry': {'type': 'object'},
            },
        }),
        400: OpenApiResponse(description='Bad request — missing or invalid coordinates'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_soil(request):
    try:
        data    = request.data
        polygon = data.get('polygon')

        if polygon and isinstance(polygon, list) and len(polygon) >= 3:
            lat      = sum(p[0] for p in polygon) / len(polygon)
            lon      = sum(p[1] for p in polygon) / len(polygon)
            is_plot  = True
        else:
            lat     = float(data.get('lat', 0))
            lon     = float(data.get('lon', 0))
            is_plot = False

        if lat == 0 and lon == 0:
            return Response({'error': 'Provide valid lat/lon or a polygon.'}, status=status.HTTP_400_BAD_REQUEST)

        if not lgbm_models:
            return Response({'error': 'Prediction models are not loaded on this server.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        preds, env_features = predict_for_point(
            lat, lon, lgbm_models,
            get_weather,
            get_ndvi,
            get_elevation,
            get_soil_texture,
        )
        fertility = classify_fertility(preds, env_features, rf_model)

        response_data = {
            'status':                   'success',
            'coordinates':              {'lat': lat, 'lon': lon},
            'environmental_factors':    env_features,
            'predicted_soil_chemistry': preds,
            'fertility_assessment':     fertility,
            'prediction_type':          'plot_centroid' if is_plot else 'point',
        }
        if is_plot:
            response_data['plot_polygon'] = polygon

        return Response(response_data)

    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ── Fertilizer recommendation for a map point (RDF Rule Book engine) ──────────

@extend_schema(
    tags=['SoilMap'],
    summary='List states + crops for the fertilizer recommendation dropdowns',
    description='Returns every state in the RDF reference dataset and, per state, the crops available for it.',
    responses={200: OpenApiResponse(description='States + crops-by-state', response={
        'type': 'object',
        'properties': {
            'states':         {'type': 'array', 'items': {'type': 'string'}},
            'crops_by_state': {'type': 'object'},
        },
    })},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fertilizer_options(request):
    states = get_fertilizer_states()
    return Response({
        'states':         states,
        'crops_by_state': {s: get_fertilizer_crops_for_state(s) for s in states},
    })


@extend_schema(
    tags=['SoilMap'],
    summary='RDF-based fertilizer recommendation for a map point',
    description=(
        'Runs the same LightGBM soil prediction as /api/predict/ for a lat/lon point '
        '(or polygon centroid), then feeds the result into the RDF Rule Book engine '
        'along with a crop to get per-parameter status, adjusted N:P:K, and Urea/DAP/MOP doses.\n\n'
        'The state is auto-detected via reverse geocoding when not supplied — pass `state` '
        'explicitly to override it (e.g. when detection is wrong or unavailable). '
        '`crop` is required for a full result; call /api/soil-map/fertilizer-options/ to '
        'populate a state/crop picker.\n\n'
        'Note: calcium and magnesium aren\'t part of the ML soil model, so they default to 0.'
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'lat':     {'type': 'number', 'example': 15.3173},
                'lon':     {'type': 'number', 'example': 75.7139},
                'polygon': {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'number'}}},
                'state':   {'type': 'string', 'description': 'Override the auto-detected state'},
                'crop':    {'type': 'string', 'description': 'Crop name (required for a full recommendation)'},
            },
        }
    },
    responses={
        200: OpenApiResponse(description='Fertilizer recommendation (or an {"error": ...} payload when state/crop can\'t be resolved)'),
        400: OpenApiResponse(description='Missing or invalid coordinates'),
        503: OpenApiResponse(description='Prediction models not loaded on this server'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fertilizer_recommendation(request):
    try:
        data    = request.data
        polygon = data.get('polygon')

        if polygon and isinstance(polygon, list) and len(polygon) >= 3:
            lat = sum(p[0] for p in polygon) / len(polygon)
            lon = sum(p[1] for p in polygon) / len(polygon)
        else:
            lat = float(data.get('lat', 0))
            lon = float(data.get('lon', 0))

        if lat == 0 and lon == 0:
            return Response({'error': 'Provide valid lat/lon or a polygon.'}, status=status.HTTP_400_BAD_REQUEST)

        if not lgbm_models:
            return Response({'error': 'Prediction models are not loaded on this server.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        preds, _env_features = predict_for_point(
            lat, lon, lgbm_models,
            get_weather,
            get_ndvi,
            get_elevation,
            get_soil_texture,
        )

        soil_values = {
            'ph':             preds.get('ph') or 0.0,
            'ec':             preds.get('ec') or 0.0,
            'organic_carbon': preds.get('organic_carbon') or 0.0,
            'nitrogen':       preds.get('n') or 0.0,
            'phosphorus':     preds.get('p') or 0.0,
            'potassium':      preds.get('k') or 0.0,
            'sulphur':        preds.get('s') or 0.0,
            'iron':           preds.get('fe') or 0.0,
            'zinc':           preds.get('zn') or 0.0,
            'copper':         preds.get('cu') or 0.0,
            'boron':          preds.get('b') or 0.0,
            'manganese':      preds.get('mn') or 0.0,
            'calcium':        0.0,  # not part of the ML soil model
            'magnesium':      0.0,  # not part of the ML soil model
        }

        state = (data.get('state') or '').strip()
        if not state:
            state = get_location_details(lat, lon).get('address', {}).get('state', '') or ''

        crop = (data.get('crop') or '').strip()

        result = recommend_fertilizer(state, crop, soil_values)
        result.setdefault('state', state)
        result.setdefault('crop', crop)
        result['coordinates']              = {'lat': lat, 'lon': lon}
        result['predicted_soil_chemistry'] = preds
        return Response(result)

    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ── upload_soil_data ──────────────────────────────────────────────────────────

# Column aliases → DeviseApisFields field names
_UPLOAD_ALIAS = {
    'ph':               'field1',
    'ec':               'field2',
    'nitrogen':         'field3',  'n': 'field3',
    'phosphorus':       'field4',  'p': 'field4',
    'potassium':        'field5',  'k': 'field5',
    'organic_carbon':   'field6',  'oc': 'field6',
    'sulfur':           'field7',  's': 'field7',
    'iron':             'field8',  'fe': 'field8',
    'zinc':             'field9',  'zn': 'field9',
    'copper':           'field10', 'cu': 'field10',
    'boron':            'field11', 'b':  'field11',
    'manganese':        'field12', 'mn': 'field12',
    'sand':             'field13',
    'clay':             'field14',
    'silt':             'field15',
    'ndvi':             'field16',
    'temperature':      'field17', 'temp': 'field17',
    'rainfall':         'field18', 'rain': 'field18',
    'elevation':        'field19', 'elev': 'field19',
    'latitude':         'latitude',
    'longitude':        'longitude',
    'lat':              'latitude',
    'lon':              'longitude',
    'lng':              'longitude',
    'tag':              'tag',
}


@extend_schema(
    tags=['SoilMap'],
    summary='Upload soil data CSV/Excel for a SoilMap device',
    description=(
        'Upload a .csv, .xlsx, or .xls file. Each row is saved as a DeviseApisFields record '
        'linked to the given device. Column names are matched by alias — accepted headers include: '
        'ph, ec, nitrogen (n), phosphorus (p), potassium (k), organic_carbon (oc), sulfur (s), '
        'iron (fe), zinc (zn), copper (cu), boron (b), manganese (mn), sand, clay, silt, ndvi, '
        'temperature (temp), rainfall (rain), elevation (elev), latitude (lat), longitude (lon/lng), tag.'
    ),
    request={'multipart/form-data': {'type': 'object', 'properties': {
        'file': {'type': 'string', 'format': 'binary', 'description': '.csv / .xlsx / .xls file'},
    }}},
    responses={
        201: OpenApiResponse(description='Upload summary', response={'type': 'object', 'properties': {
            'status':           {'type': 'string', 'example': 'success'},
            'rows_received':    {'type': 'integer'},
            'rows_ingested':    {'type': 'integer'},
            'rows_rejected':    {'type': 'integer'},
            'rejected_reasons': {'type': 'array', 'items': {'type': 'string'}},
            'retrained':        {'type': 'boolean'},
        }}),
        400: OpenApiResponse(description='No file / unsupported format / parse error'),
        403: OpenApiResponse(description='Not the device owner and not staff'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_soil_data(request, device_id):
    """
    POST /api/soil-map/upload/<device_id>/
    Accepts multipart/form-data with a CSV or Excel file.
    Each row becomes one DeviseApisFields record for the device.
    """
    try:
        import pandas as pd
    except ImportError:
        return Response({'error': 'pandas is not installed on the server'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    device = get_object_or_404(Devise, pk=device_id)

    # Access control — owner or staff
    if not (request.user.is_staff or request.user.is_superuser or device.user == request.user):
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    file = request.FILES.get('file')
    if not file:
        return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

    filename = file.name.lower()
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file.read()))
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file.read()))
        else:
            return Response({'error': 'File must be .csv, .xlsx, or .xls'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': f'Could not parse file: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    # Normalise column headers
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    created = 0
    errors  = []
    for idx, row in df.iterrows():
        kwargs = {'device': device}
        for col, val in row.items():
            field = _UPLOAD_ALIAS.get(col)
            if field and pd.notna(val):
                try:
                    kwargs[field] = float(val) if field not in ('tag',) else str(val)
                except (TypeError, ValueError):
                    pass
        try:
            DeviseApisFields.objects.create(**kwargs)
            created += 1
        except Exception as e:
            errors.append({'row': idx + 2, 'error': str(e)})

    return Response({
        'status'          : 'success',
        'rows_received'   : len(df),
        'rows_ingested'   : created,
        'rows_rejected'   : len(errors),
        'rejected_reasons': [f"Row {e['row']}: {e['error']}" for e in errors],
        'retrained'       : False,
    }, status=status.HTTP_201_CREATED)


# ── SoiLENZ PDF Report ────────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilMap'],
    summary='Generate SoiLENZ 6-page soil health PDF report',
    description=(
        'Runs AI soil prediction for the given lat/lon, then generates and returns '
        'a 6-page SoiLENZ Advisory PDF report covering:\n'
        '1. Soil Health Intelligence cover page\n'
        '2. 12-parameter detailed results table\n'
        '3. Grid-wise field variability heatmaps\n'
        '4. Crop suitability analysis (AI-scored)\n'
        '5. Soil amendment & action plan\n'
        '6. Carbon credit impact dashboard\n\n'
        'Optional metadata: location, crop, field_area, agro_zone, farmer_name, analysis_date.'
    ),
    request={
        'application/json': {
            'type': 'object',
            'required': ['lat', 'lon'],
            'properties': {
                'lat':           {'type': 'number', 'example': 15.3173},
                'lon':           {'type': 'number', 'example': 75.7139},
                'farmer_name':   {'type': 'string',  'example': 'Ramesh Kumar'},
                'location':      {'type': 'string',  'example': 'Dharwad, Karnataka'},
                'field_area':    {'type': 'string',  'example': '2.5 acres'},
                'crop':          {'type': 'string',  'example': 'Bitter Gourd'},
                'agro_zone':     {'type': 'string',  'example': 'Semi-Arid Deccan'},
                'analysis_date': {'type': 'string',  'example': '19 May 2026'},
            },
        }
    },
    responses={
        200: OpenApiResponse(description='PDF file download (application/pdf)'),
        400: OpenApiResponse(description='Bad request — missing or invalid coordinates'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_soil_report_pdf(request):
    try:
        from .pdf_report import generate_pdf
        data = request.data
        lat  = float(data.get('lat', 0))
        lon  = float(data.get('lon', 0))
        if lat == 0 and lon == 0:
            return Response({'error': 'Provide valid lat and lon.'}, status=status.HTTP_400_BAD_REQUEST)

        # Run prediction
        if not lgbm_models:
            return Response({'error': 'Prediction models are not loaded on this server.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        preds, env_features = predict_for_point(
            lat, lon, lgbm_models,
            get_weather,
            get_ndvi,
            get_elevation,
            get_soil_texture,
        )
        fertility = classify_fertility(preds, env_features, rf_model)

        metadata = {
            'farmer_name':   data.get('farmer_name', ''),
            'location':      data.get('location', ''),
            'field_area':    data.get('field_area', ''),
            'crop':          data.get('crop', ''),
            'agro_zone':     data.get('agro_zone', ''),
            'analysis_date': data.get('analysis_date', ''),
        }

        pdf_bytes = generate_pdf(preds, env_features, fertility, metadata)

        farmer_slug = (metadata['farmer_name'] or 'soilenz').replace(' ', '_')
        filename = f'SoiLENZ_Report_{farmer_slug}.pdf'
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        resp['Content-Length'] = len(pdf_bytes)
        return resp

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ── Soil data list ────────────────────────────────────────────────────────────

_SOIL_FIELDS = [
    ('field1',  'pH'),
    ('field2',  'EC (dS/m)'),
    ('field3',  'Nitrogen (kg/ha)'),
    ('field4',  'Phosphorus (kg/ha)'),
    ('field5',  'Potassium (kg/ha)'),
    ('field6',  'Organic Carbon (%)'),
    ('field7',  'Sulfur (ppm)'),
    ('field8',  'Iron/Fe (ppm)'),
    ('field9',  'Zinc/Zn (ppm)'),
    ('field10', 'Copper/Cu (ppm)'),
    ('field11', 'Boron/B (ppm)'),
    ('field12', 'Manganese/Mn (ppm)'),
    ('field13', 'Sand (%)'),
    ('field14', 'Clay (%)'),
    ('field15', 'Silt (%)'),
    ('field16', 'NDVI'),
    ('field17', 'Temperature (°C)'),
    ('field18', 'Rainfall (mm)'),
    ('field19', 'Elevation (m)'),
]


def _record_to_dict(r):
    row = {'id': r.pk, 'tag': r.tag or '', 'lat': r.latitude, 'lon': r.longitude,
           'created_at': r.created_at.strftime('%d %b %Y %H:%M') if r.created_at else ''}
    for field_key, _ in _SOIL_FIELDS:
        row[field_key] = getattr(r, field_key, 0.0)
    return row


@extend_schema(
    tags=['SoilMap'],
    summary='List all soil data records for a device',
    description=(
        'Returns every DeviseApisFields record linked to the given SoilMap device. '
        'Staff/superuser can access any device; regular users can only access their own. '
        'Results include all 19 soil/env fields, lat/lon, tag and timestamp.'
    ),
    responses={
        200: OpenApiResponse(description='Paginated list of soil records', response={
            'type': 'object',
            'properties': {
                'device_id':   {'type': 'integer'},
                'device_name': {'type': 'string'},
                'total':       {'type': 'integer'},
                'records': {
                    'type': 'array',
                    'items': {'type': 'object'},
                },
            },
        }),
        403: OpenApiResponse(description='Forbidden'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_soil_data(request, device_id):
    device = get_object_or_404(Devise, pk=device_id)
    if not (request.user.is_staff or request.user.is_superuser or device.user == request.user):
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    records = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    return Response({
        'device_id':   device.pk,
        'device_name': device.name,
        'total':       records.count(),
        'fields':      [{'key': k, 'label': l} for k, l in _SOIL_FIELDS],
        'records':     [_record_to_dict(r) for r in records],
    })


@extend_schema(
    tags=['SoilMap'],
    summary='Export soil data records as CSV',
    description='Downloads all DeviseApisFields records for the given device as a .csv file.',
    responses={200: OpenApiResponse(description='CSV file download (text/csv)')},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_soil_data_csv(request, device_id):
    import csv
    device = get_object_or_404(Devise, pk=device_id)
    if not (request.user.is_staff or request.user.is_superuser or device.user == request.user):
        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

    records = DeviseApisFields.objects.filter(device=device).order_by('-created_at')

    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="SoilData_{device.name}_{device.pk}.csv"'

    headers = ['#', 'Tag', 'Latitude', 'Longitude', 'Created At'] + [l for _, l in _SOIL_FIELDS]
    writer = csv.writer(resp)
    writer.writerow(headers)
    for r in records:
        row = [r.pk, r.tag or '', r.latitude, r.longitude,
               r.created_at.strftime('%d %b %Y %H:%M') if r.created_at else '']
        row += [getattr(r, k, 0.0) for k, _ in _SOIL_FIELDS]
        writer.writerow(row)

    return resp

# ── Polygon Zone + SAR analysis (sync) ───────────────────────────────────────

@extend_schema(
    tags=['SoilMap'],
    summary='Zone + SAR crop analysis for a drawn polygon',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'coordinates': {'type': 'array', 'description': 'Array of [lon, lat] pairs'},
                'radius_km':   {'type': 'number', 'example': 2},
                'season':      {'type': 'string', 'example': 'kharif'},
            },
        }
    },
    responses={200: OpenApiResponse(description='Zone + crop detection result')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_polygon(request):
    coords    = request.data.get('coordinates', [])
    radius_km = float(request.data.get('radius_km', 2))
    season    = request.data.get('season', 'kharif')
    if len(coords) < 3:
        return Response({'error': 'Provide at least 3 [lon,lat] pairs.'}, status=status.HTTP_400_BAD_REQUEST)
    result = _analyze_polygon(coords, radius_km, season)
    return Response(result)


# ── Climate Zone endpoint ─────────────────────────────────────────────────────

@extend_schema(
    tags=['SoilMap'],
    summary='Classify Köppen-Geiger agroclimatic zone for a point',
    description=(
        'Given a lat/lon, fetches temperature, rainfall and elevation from satellite/weather APIs '
        'and returns the matching Köppen-Geiger climate zone with full metadata: '
        'zone id, color, description, soil types, NDVI range, and growing tips.\n\n'
        'You can also pass `temp`, `rainfall`, and `elevation` directly to skip the API fetch.'
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'lat':       {'type': 'number', 'example': 15.3173},
                'lon':       {'type': 'number', 'example': 75.7139},
                'temp':      {'type': 'number', 'example': 26.5,  'description': 'Override: annual mean temperature (°C)'},
                'rainfall':  {'type': 'number', 'example': 850.0, 'description': 'Override: annual total rainfall (mm)'},
                'elevation': {'type': 'number', 'example': 720.0, 'description': 'Override: elevation (m)'},
            },
        }
    },
    responses={
        200: OpenApiResponse(description='Climate zone result', response={
            'type': 'object',
            'properties': {
                'zone':         {'type': 'string', 'example': 'Tropical Savanna'},
                'id':           {'type': 'string', 'example': 'Aw'},
                'color':        {'type': 'string', 'example': '#9ACD32'},
                'description':  {'type': 'string'},
                'soil_types':   {'type': 'array', 'items': {'type': 'string'}},
                'ndvi_range':   {'type': 'string', 'example': '0.40-0.65'},
                'growing_tips': {'type': 'string'},
                'inputs':       {'type': 'object'},
            },
        }),
        400: OpenApiResponse(description='Missing or invalid coordinates'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def classify_climate_zone(request):
    data = request.data
    lat  = data.get('lat')
    lon  = data.get('lon')

    # If caller supplies raw climate inputs, use the old simple classifier
    temp      = data.get('temp')
    rainfall  = data.get('rainfall')
    elevation = data.get('elevation', 0)

    if temp is not None and rainfall is not None:
        temp, rainfall, elevation = float(temp), float(rainfall), float(elevation)
        zone = classify_global_climate_zone(temp, rainfall, elevation)
        meta = CLIMATE_ZONE_METADATA.get(zone, {})
        return Response({
            'zone': zone, 'id': meta.get('id', ''), 'color': meta.get('color', ''),
            'description': meta.get('description', ''), 'soil_types': meta.get('soil_types', []),
            'ndvi_range': meta.get('ndvi_range', ''), 'growing_tips': meta.get('growing_tips', ''),
            'inputs': {'temp_c': temp, 'rainfall_mm': rainfall, 'elevation_m': elevation},
        })

    # Otherwise derive from lat/lon using the India/Karnataka-aware classifier
    if lat is None or lon is None:
        return Response({'error': 'Provide lat/lon or temp/rainfall.'}, status=status.HTTP_400_BAD_REQUEST)

    zone_name, zone_meta, climate, location = _classify_zone(float(lat), float(lon))
    return Response({
        'zone':         zone_name,
        'id':           zone_meta.get('id', ''),
        'color':        zone_meta.get('color', ''),
        'description':  zone_meta.get('description', ''),
        'soil_types':   zone_meta.get('soil_types', []),
        'ndvi_range':   zone_meta.get('ndvi_range', ''),
        'growing_tips': zone_meta.get('growing_tips', ''),
        'location':     location.get('display_name', ''),
        'inputs': {
            'temp_c':       round(climate.get('average_temp', 0), 1),
            'rainfall_mm':  round(climate.get('annual_rainfall', 0), 1),
            'elevation_m':  round(climate.get('elevation', 0), 1),
            'data_source':  climate.get('data_source', ''),
        },
    })


# ── Crop Coverage Map endpoint ────────────────────────────────────────────────

@extend_schema(
    tags=['SoilMap'],
    summary='Pixel-level crop coverage map for a point + radius',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'lat':        {'type': 'number', 'example': 26.5},
                'lon':        {'type': 'number', 'example': 83.7},
                'radius_km':  {'type': 'number', 'example': 2.0},
                'crop':       {'type': 'string', 'example': 'paddy'},
                'months_back':{'type': 'integer','example': 6},
            },
            'required': ['lat', 'lon'],
        }
    },
    responses={200: OpenApiResponse(description='Crop coverage result with GEE tile URL and area stats')},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def crop_coverage_map(request):
    data       = request.data
    lat        = data.get('lat')
    lon        = data.get('lon')
    if lat is None or lon is None:
        return Response({'error': 'lat and lon are required.'}, status=status.HTTP_400_BAD_REQUEST)
    radius_km  = float(data.get('radius_km',   2.0))
    crop       = data.get('crop', 'paddy')
    months_back = int(data.get('months_back',  6))
    if crop not in CROP_CATALOG:
        return Response({'error': f'Unknown crop "{crop}". Valid: {list(CROP_CATALOG)}'}, status=status.HTTP_400_BAD_REQUEST)
    result = get_crop_coverage_map(float(lat), float(lon), radius_km, crop, months_back)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gee_health(request):
    """
    GEE connectivity probe.
    Reads .env directly every call — no os.environ caching issues,
    no server restart needed after editing .env.
    """
    import os, time, ee
    from dotenv import dotenv_values
    from pathlib import Path
    import agri_ai.gee.service as _svc

    env_path = Path(__file__).resolve().parent.parent / '.env'
    env = dotenv_values(env_path)

    project  = env.get("GEE_PROJECT", "")   or ""
    sa_key   = env.get("SAR_GEE_SA_KEY", "") or ""

    config = {
        'GEE_PROJECT':    project or '(not set)',
        'SAR_GEE_SA_KEY': sa_key  or '(not set)',
        'project_set':    bool(project),
        'sa_key_set':     bool(sa_key),
        'sa_key_exists':  bool(sa_key and os.path.isfile(sa_key)),
    }

    ok = False
    probe_ok = False
    probe_error = None
    init_method = None

    t0 = time.monotonic()
    try:
        if sa_key and os.path.isfile(sa_key):
            creds = ee.ServiceAccountCredentials(email=None, key_file=sa_key)
            ee.Initialize(creds, project=project or None)
            init_method = 'service_account'
        elif project:
            ee.Initialize(project=project)
            init_method = 'adc'
        else:
            raise RuntimeError("GEE_PROJECT not set in .env")

        ok = True
        # Update module cache so the rest of the app uses the now-working credentials
        _svc._GEE_PROJECT     = project
        _svc._SA_KEY_PATH     = sa_key
        _svc._GEE_AVAILABLE   = True
        _svc._GEE_INITIALIZED = True

        try:
            ee.Image("USGS/SRTMGL1_003").getInfo()
            probe_ok = True
        except Exception as e:
            probe_ok = False
            probe_error = str(e)

    except Exception as e:
        probe_error = str(e)
        _svc._GEE_INITIALIZED = False
        _svc._GEE_AVAILABLE   = False

    elapsed_ms = round((time.monotonic() - t0) * 1000)

    return Response({
        'gee_initialized': ok,
        'probe_ok':        probe_ok,
        'probe_error':     probe_error,
        'init_method':     init_method,
        'elapsed_ms':      elapsed_ms,
        'config':          config,
    })
