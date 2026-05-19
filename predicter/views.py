from django.http import HttpResponseBadRequest, HttpResponse
from .ai_model.model import run_model
from agriapp.models import DeviseApis
from django.shortcuts import get_object_or_404, render


def get_recommendation(request):
    api_id   = request.GET.get("api_id")
    api_data = ''
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    try:
        api_id   = int(api_id)
        api_data = DeviseApis.objects.select_related('farmer').filter(pk=api_id).first()
    except ValueError:
        return HttpResponseBadRequest("Invalid 'api_id' parameter.")

    if api_data:
        soil_nutrients = {
            'N': [api_data.nitrogen], 'P': [api_data.phosphorous],
            'K': [api_data.potassium], 'temperature': [10],
            'humidity': [10], 'ph': [api_data.ph], 'rainfall': [10],
        }
        result = run_model(soil_nutrients)
    else:
        result = 'No data found for the provided api id.'
    return render(request, 'predicter/crop_recom_dashb.html', {
        'recommendation': result,
        'soil_nutrients': api_data,
    })


def download_recommendation_pdf(request):
    """Generate and download the SoiLENZ 6-page PDF for a DeviseApis reading."""
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    try:
        api_id   = int(api_id)
        api_data = DeviseApis.objects.select_related('farmer', 'device').filter(pk=api_id).first()
    except ValueError:
        return HttpResponseBadRequest("Invalid api_id.")

    if not api_data:
        return HttpResponseBadRequest("Reading not found.")

    from soilmap.pdf_report import generate_pdf

    def _v(val):
        """Return float if non-zero, else None (treat 0.0 as missing)."""
        return float(val) if val else None

    # Build preds from device data — all 12 parameters available
    preds = {
        'ph':             _v(api_data.ph),
        'ec':             _v(api_data.ec or api_data.electrical_conduction),
        'organic_carbon': _v(api_data.oc or api_data.organic_carboa),
        'n':              _v(api_data.nitrogen),
        'p':              _v(api_data.phosphorous),
        'k':              _v(api_data.potassium),
        's':              _v(api_data.sulphur),
        'fe':             _v(api_data.iron),
        'mn':             _v(api_data.manganese),
        'cu':             _v(api_data.copper),
        'zn':             _v(api_data.zinc),
        'b':              _v(api_data.boron),
    }

    lat = api_data.latitude  or 0.0
    lon = api_data.longitude or 0.0

    # Try to enrich from soilmap ML if lat/lon available
    if lat and lon:
        try:
            import sys, os, pickle
            _ML_DIR    = os.path.join(os.path.dirname(__file__), '..', 'soilmap', 'ml_pipeline')
            _MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'soilmap', 'models')
            if _ML_DIR not in sys.path:
                sys.path.insert(0, os.path.abspath(_ML_DIR))
            import weather as weather_mod
            import ndvi    as ndvi_mod
            import add_elevation_to_dataset as elev_mod
            import add_soilgrids_to_dataset as texture_mod
            from map_utils import predict_for_point, dummy_predictions, classify_fertility, dummy_fertility

            REGRESSION_TARGETS = ["ph","ec","n","p","k","organic_carbon","s","fe","zn","cu","b","mn"]
            lgbm_models = {}
            for t in REGRESSION_TARGETS:
                p_path = os.path.join(_MODEL_DIR, f"lgbm_{t}.pkl")
                if os.path.exists(p_path):
                    with open(p_path, "rb") as f:
                        lgbm_models[t] = pickle.load(f)
            rf_path = os.path.join(_MODEL_DIR, "rf_fertility.pkl")
            rf_model = pickle.load(open(rf_path, "rb")) if os.path.exists(rf_path) else None

            if lgbm_models:
                ml_preds, env_features = predict_for_point(
                    lat, lon, lgbm_models,
                    weather_mod.get_weather, ndvi_mod.get_ndvi,
                    elev_mod.get_elevation, texture_mod.get_soil_texture,
                )
                fertility = classify_fertility(ml_preds, env_features, rf_model)
            else:
                ml_preds, env_features = dummy_predictions(lat, lon)
                fertility = dummy_fertility(lat, lon)

            # Overlay actual device measurements (higher priority than ML estimates)
            for key, val in preds.items():
                if val is not None:
                    ml_preds[key] = val
            preds = ml_preds
        except Exception:
            env_features = {
                'ndvi': 0.55, 'temperature_c': 28.0,
                'rainfall_mm': 950.0, 'elevation_m': 200.0,
            }
            fertility = 'Medium'
    else:
        env_features = {
            'ndvi': 0.55, 'temperature_c': 28.0,
            'rainfall_mm': 950.0, 'elevation_m': 200.0,
        }
        fertility = 'Medium'

    # Build metadata from farmer / devise
    farmer = api_data.farmer
    crop   = (farmer.crop if farmer and farmer.crop else
              (api_data.crop_type or ''))
    metadata = {
        'farmer_name':   farmer.farmer_name if farmer else (api_data.area_name or ''),
        'location':      (f"{farmer.village}, {farmer.district}, {farmer.state}" if farmer else ''),
        'field_area':    (f"{farmer.land_area} acres" if farmer and farmer.land_area else ''),
        'crop':          crop,
        'agro_zone':     '',
        'analysis_date': (api_data.created_at.strftime('%d %b %Y') if api_data.created_at else ''),
    }

    pdf_bytes = generate_pdf(preds, env_features, fertility, metadata)

    slug = (metadata['farmer_name'] or 'report').replace(' ', '_')
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="SoiLENZ_Report_{slug}.pdf"'
    resp['Content-Length'] = len(pdf_bytes)
    return resp
