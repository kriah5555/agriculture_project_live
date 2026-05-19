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

from agriapp.models import Devise, DeviseApisFields

# ── ML pipeline setup ─────────────────────────────────────────────────────────
_ML_DIR    = os.path.join(os.path.dirname(__file__), 'ml_pipeline')
_MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

if _ML_DIR not in sys.path:
    sys.path.insert(0, _ML_DIR)

import weather as weather_mod
import ndvi as ndvi_mod
import add_elevation_to_dataset as elev_mod
import add_soilgrids_to_dataset as texture_mod
from map_utils import predict_for_point, dummy_predictions, classify_fertility, dummy_fertility

REGRESSION_TARGETS = ["ph", "ec", "n", "p", "k", "organic_carbon", "s", "fe", "zn", "cu", "b", "mn"]
lgbm_models = {}
rf_model    = None

try:
    for t in REGRESSION_TARGETS:
        p = os.path.join(_MODEL_DIR, f"lgbm_{t}.pkl")
        if os.path.exists(p):
            with open(p, "rb") as f:
                lgbm_models[t] = pickle.load(f)
    rf_path = os.path.join(_MODEL_DIR, "rf_fertility.pkl")
    if os.path.exists(rf_path):
        with open(rf_path, "rb") as f:
            rf_model = pickle.load(f)
except Exception as e:
    print(f"[soilmap] model load warning: {e}")

try:
    elev_mod.init_gee()
except Exception:
    pass


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
        'If no trained models are loaded, returns deterministic dummy values based on coordinates.'
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

        if lgbm_models:
            preds, env_features = predict_for_point(
                lat, lon, lgbm_models,
                weather_mod.get_weather,
                ndvi_mod.get_ndvi,
                elev_mod.get_elevation,
                texture_mod.get_soil_texture,
            )
            fertility = classify_fertility(preds, env_features, rf_model)
        else:
            preds, env_features = dummy_predictions(lat, lon)
            fertility = dummy_fertility(lat, lon)

        response_data = {
            'status':                  'success',
            'coordinates':             {'lat': lat, 'lon': lon},
            'environmental_factors':   env_features,
            'predicted_soil_chemistry': preds,
            'fertility_assessment':    fertility,
            'prediction_type':         'plot_centroid' if is_plot else 'point',
        }
        if is_plot:
            response_data['plot_polygon'] = polygon

        return Response(response_data)

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
        if lgbm_models:
            preds, env_features = predict_for_point(
                lat, lon, lgbm_models,
                weather_mod.get_weather,
                ndvi_mod.get_ndvi,
                elev_mod.get_elevation,
                texture_mod.get_soil_texture,
            )
            fertility = classify_fertility(preds, env_features, rf_model)
        else:
            preds, env_features = dummy_predictions(lat, lon)
            fertility = dummy_fertility(lat, lon)

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