"""
CarbonCredits mobile API endpoints.

Routes (all mounted under /api/mobile/ via mobile_urls.py):
  POST  /carbon-credits/calculate/    calculateCarbon  — compute carbon credits (no DB)
  POST  /carbon-credits/analyze/      analyzeFarm      — full farm sustainability analysis (no save)
  GET   /carbon-credits/pdf-report/   buildPdfReportUrl — generate & stream PDF carbon report
"""
from django.http import HttpResponse

from rest_framework import serializers as s
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, inline_serializer
from drf_spectacular.openapi import OpenApiTypes

from devise_apis.carbon_service import calculate_carbon_all, build_pdf_report


# ── Inline schemas for Swagger ────────────────────────────────────────────────

_calculate_request = inline_serializer('CarbonCalculateRequest', fields={
    'crop_type'        : s.CharField(help_text='Crop name, e.g. "wheat"'),
    'farm_size'        : s.FloatField(help_text='Farm area in acres'),
    'soil_score'       : s.FloatField(help_text='Soil health score 0–100'),
    'organic'          : s.BooleanField(help_text='True if organic farming'),
    'state'            : s.CharField(help_text='Indian state name'),
    'irrigation'       : s.CharField(help_text='drip / sprinkler / flood'),
    'fertilizer_usage' : s.CharField(help_text='low / medium / high'),
    'temperature'      : s.FloatField(required=False, help_text='°C (optional, fetched from weather if omitted)'),
    'rainfall'         : s.FloatField(required=False, help_text='mm (optional)'),
    'humidity'         : s.FloatField(required=False, help_text='% (optional)'),
})

_calc_data = inline_serializer('CarbonCalcData', fields={
    'carbon_credits'      : s.FloatField(),
    'co2_offset'          : s.FloatField(),
    'esg_score'           : s.FloatField(),
    'sustainability_score': s.FloatField(),
    'trust_score'         : s.FloatField(),
    'climate_risk'        : s.CharField(help_text='Low / Medium / High'),
    'ndvi_health'         : s.CharField(help_text='Excellent / Healthy / Moderate / Weak'),
    'yearly_projection'   : s.FloatField(),
    'market_rate'         : s.FloatField(),
    'temperature'         : s.FloatField(),
    'rainfall'            : s.FloatField(),
    'weather_source'      : s.CharField(),
    'formula_breakdown'   : s.CharField(),
})

_calculate_response = inline_serializer('CarbonCalculateResponse', fields={
    'message': s.CharField(),
    'data'   : _calc_data,
})

_analyze_request = inline_serializer('FarmAnalyzeRequest', fields={
    'crop_type'       : s.CharField(help_text='Crop name'),
    'farm_size'       : s.FloatField(help_text='Farm area in acres'),
    'soil_score'      : s.FloatField(help_text='Soil health score 0–100'),
    'organic'         : s.BooleanField(help_text='True if organic farming'),
    'rainfall'        : s.FloatField(required=False, help_text='mm (default 60)'),
    'temperature'     : s.FloatField(required=False, help_text='°C (default 30)'),
    'irrigation'      : s.CharField(required=False, help_text='drip / sprinkler / flood (default drip)'),
    'fertilizer_usage': s.CharField(required=False, help_text='low / medium / high (default low)'),
    'state'           : s.CharField(required=False, help_text='State for weather lookup (default Karnataka)'),
})

_analyze_response = inline_serializer('FarmAnalyzeResponse', fields={
    'crop_type'               : s.CharField(),
    'farm_size'               : s.FloatField(),
    'soil_score'              : s.FloatField(),
    'organic'                 : s.BooleanField(),
    'irrigation'              : s.CharField(),
    'fertilizer_usage'        : s.CharField(),
    'temperature'             : s.FloatField(),
    'rainfall'                : s.FloatField(),
    'sustainability_score'    : s.FloatField(),
    'esg_score'               : s.FloatField(),
    'trust_score'             : s.FloatField(),
    'carbon_potential'        : s.CharField(help_text='Low / Medium / High'),
    'estimated_carbon_credits': s.FloatField(),
    'co2_offset'              : s.FloatField(),
    'yearly_projection'       : s.FloatField(),
    'ndvi_health'             : s.CharField(),
    'climate_risk'            : s.CharField(),
    'weather_source'          : s.CharField(),
    'formula_breakdown'       : s.CharField(),
    'recommendations'         : s.ListField(child=s.CharField()),
})


# ── calculateCarbon ───────────────────────────────────────────────────────────

@extend_schema(
    tags=['CarbonCredits'],
    summary='Calculate carbon credits',
    description=(
        'Computes carbon credits, ESG score, sustainability score, CO₂ offset, '
        'climate risk, and yearly income projection. All data is computed from the '
        'request — nothing is persisted to the database.'
    ),
    request=_calculate_request,
    responses={
        200: _calculate_response,
        400: OpenApiResponse(description='Missing or invalid fields'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_carbon(request):
    data     = request.data
    required = ['crop_type', 'farm_size', 'soil_score', 'organic', 'state', 'irrigation', 'fertilizer_usage']
    missing  = [f for f in required if f not in data]
    if missing:
        return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    calc = calculate_carbon_all(data)

    return Response({
        'message': 'Carbon credits calculated',
        'data'   : calc,
    })


# ── analyzeFarm ───────────────────────────────────────────────────────────────

def _recommendations(data: dict, calc: dict) -> list:
    recs = []
    soil_score  = float(data.get('soil_score', 50))
    organic     = bool(data.get('organic', False))
    irrigation  = str(data.get('irrigation', 'drip')).lower()
    fertilizer  = str(data.get('fertilizer_usage', 'low')).lower()
    credits     = calc['carbon_credits']

    carbon_potential = 'High' if credits > 50 else ('Medium' if credits > 25 else 'Low')

    if soil_score >= 85:
        recs.append('Excellent soil health supports strong carbon sequestration.')
    elif soil_score >= 70:
        recs.append('Moderate sustainability performance detected.')
    else:
        recs.append('Low soil quality detected. Organic restoration recommended.')

    if organic:
        recs.append('Organic farming improves ESG and carbon marketplace value.')
    else:
        recs.append('Reduce synthetic chemical dependency for better sustainability.')

    if irrigation == 'drip':
        recs.append('Drip irrigation improves water efficiency and carbon optimization.')
    elif irrigation == 'flood':
        recs.append('Flood irrigation increases methane and water waste.')

    if fertilizer == 'low':
        recs.append('Low fertilizer dependency supports regenerative farming.')
    else:
        recs.append('Balanced fertilizer optimization recommended.')

    return carbon_potential, recs


@extend_schema(
    tags=['CarbonCredits'],
    summary='Analyze farm sustainability',
    description=(
        'Full farm sustainability analysis — returns all scores, projections, '
        'weather data, formula breakdown, and actionable recommendations. '
        'Does not save a report.'
    ),
    request=_analyze_request,
    responses={
        200: _analyze_response,
        400: OpenApiResponse(description='Missing or invalid fields'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_farm(request):
    data = request.data
    required = ['crop_type', 'farm_size', 'soil_score', 'organic']
    missing  = [f for f in required if f not in data]
    if missing:
        return Response({'error': f'Missing required fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

    calc = calculate_carbon_all(data)
    carbon_potential, recs = _recommendations(data, calc)

    return Response({
        'crop_type'               : data.get('crop_type'),
        'farm_size'               : data.get('farm_size'),
        'soil_score'              : data.get('soil_score'),
        'organic'                 : data.get('organic'),
        'irrigation'              : data.get('irrigation', 'drip'),
        'fertilizer_usage'        : data.get('fertilizer_usage', 'low'),
        'temperature'             : calc['temperature'],
        'rainfall'                : calc['rainfall'],
        'sustainability_score'    : calc['sustainability_score'],
        'esg_score'               : calc['esg_score'],
        'trust_score'             : calc['trust_score'],
        'carbon_potential'        : carbon_potential,
        'estimated_carbon_credits': calc['carbon_credits'],
        'co2_offset'              : calc['co2_offset'],
        'yearly_projection'       : calc['yearly_projection'],
        'ndvi_health'             : calc['ndvi_health'],
        'climate_risk'            : calc['climate_risk'],
        'weather_source'          : calc['weather_source'],
        'formula_breakdown'       : calc['formula_breakdown'],
        'recommendations'         : recs,
    })


# ── buildPdfReportUrl ─────────────────────────────────────────────────────────

@extend_schema(
    tags=['CarbonCredits'],
    summary='Generate carbon credit PDF report',
    description=(
        'Streams a PDF carbon credit report. '
        'Pipe-delimit multiple recommendations: "Reduce chemicals|Use drip irrigation".'
    ),
    parameters=[
        OpenApiParameter('farmer_name',            OpenApiTypes.STR,   description='Farmer / partner name (default: "Arkashine Climate Partner")'),
        OpenApiParameter('crop_type',              OpenApiTypes.STR,   description='Crop name (default: "Crop")'),
        OpenApiParameter('state',                  OpenApiTypes.STR,   description='State (default: "Unknown")'),
        OpenApiParameter('soil_score',             OpenApiTypes.FLOAT, description='Soil health score 0–100 (default: 0.0)'),
        OpenApiParameter('carbon_credits',         OpenApiTypes.FLOAT, description='Carbon credits (default: 0.0)'),
        OpenApiParameter('esg_score',              OpenApiTypes.FLOAT, description='ESG score (default: 0.0)'),
        OpenApiParameter('sustainability_score',   OpenApiTypes.FLOAT, description='Sustainability score (default: 0.0)'),
        OpenApiParameter('co2_offset',             OpenApiTypes.FLOAT, description='CO₂ offset (default: 0.0)'),
        OpenApiParameter('yearly_projection',      OpenApiTypes.FLOAT, description='Yearly income projection (default: 0.0)'),
        OpenApiParameter('verification_status',    OpenApiTypes.STR,   description='Verification label (default: "AI VERIFIED")'),
        OpenApiParameter('carbon_credit_potential',OpenApiTypes.STR,   description='Low / Medium / High (default: "Medium")'),
        OpenApiParameter('recommendations',        OpenApiTypes.STR,   description='Pipe-delimited recommendation strings (default: "")'),
    ],
    responses={
        200: OpenApiResponse(description='PDF file (application/pdf)'),
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def build_pdf_report_url(request):
    def _f(key, default=0.0):
        try:
            return float(request.GET.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    raw_recs = request.GET.get('recommendations', '')
    recs     = [r.strip() for r in raw_recs.split('|') if r.strip()]

    pdf = build_pdf_report(
        farmer_name             = request.GET.get('farmer_name', 'Arkashine Climate Partner'),
        crop_type               = request.GET.get('crop_type', 'Crop'),
        state                   = request.GET.get('state', 'Unknown'),
        soil_score              = _f('soil_score'),
        carbon_credits          = _f('carbon_credits'),
        esg_score               = _f('esg_score'),
        sustainability_score    = _f('sustainability_score'),
        co2_offset              = _f('co2_offset'),
        yearly_projection       = _f('yearly_projection'),
        verification_status     = request.GET.get('verification_status', 'AI VERIFIED'),
        carbon_credit_potential = request.GET.get('carbon_credit_potential', 'Medium'),
        recommendations         = recs,
    )

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=arkashine_carbon_report.pdf'
    return response