from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

import requests as _requests

from agri_ai.crop import run_model
from .report_builder import build_report_context
from agriapp.models import DeviseApis


def _fetch_climate_for_recommendation(lat, lon):
    """
    Fetch temperature (°C), humidity (%), and annual rainfall (mm) from Open-Meteo.
    Raises RuntimeError if the data cannot be retrieved.
    """
    temperature = humidity = rainfall = None

    try:
        r = _requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m",
                    "timezone": "auto"},
            timeout=6,
        )
        r.raise_for_status()
        current = r.json().get("current", {})
        if current.get("temperature_2m") is not None:
            temperature = float(current["temperature_2m"])
        if current.get("relative_humidity_2m") is not None:
            humidity = float(current["relative_humidity_2m"])
    except Exception:
        pass

    try:
        r = _requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={"latitude": lat, "longitude": lon,
                    "start_date": "2024-01-01", "end_date": "2024-12-31",
                    "daily": "temperature_2m_mean,precipitation_sum",
                    "timezone": "auto"},
            timeout=8,
        )
        r.raise_for_status()
        daily = r.json().get("daily", {})
        temps   = [t for t in daily.get("temperature_2m_mean", []) if t is not None]
        precips = [p for p in daily.get("precipitation_sum",   []) if p is not None]
        if temps:
            temperature = round(sum(temps) / len(temps), 1)
        if precips:
            rainfall = round(sum(precips), 1)
    except Exception:
        pass

    if temperature is None or humidity is None or rainfall is None:
        raise RuntimeError("Could not fetch climate data from Open-Meteo for the given location.")

    return temperature, humidity, rainfall


# ── Dashboard (existing AI recommendation page) ───────────────────────────────

def get_recommendation(request):
    api_id   = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    try:
        api_id   = int(api_id)
        api_data = DeviseApis.objects.select_related('farmer').filter(pk=api_id).first()
    except ValueError:
        return HttpResponseBadRequest("Invalid 'api_id' parameter.")

    if api_data:
        lat, lon = api_data.latitude, api_data.longitude
        if not (lat and lon):
            return HttpResponseBadRequest("Reading has no GPS coordinates. Cannot run crop recommendation.")
        try:
            temperature, humidity, rainfall = _fetch_climate_for_recommendation(lat, lon)
        except RuntimeError as e:
            return HttpResponseBadRequest(str(e))
        result = run_model({
            'N':           [api_data.nitrogen],
            'P':           [api_data.phosphorous],
            'K':           [api_data.potassium],
            'temperature': [temperature],
            'humidity':    [humidity],
            'ph':          [api_data.ph],
            'rainfall':    [rainfall],
        })
    else:
        result = 'No data found for the provided api id.'
    return render(request, 'reports/crop_recom_dashb.html', {
        'recommendation': result,
        'soil_nutrients': api_data,
    })


# ── HTML Report preview ───────────────────────────────────────────────────────

def soil_report_html(request):
    """Render the full SoiLENZ 6-page report as HTML (browser preview)."""
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    ctx = build_report_context(api_id)
    if ctx is None:
        return HttpResponseBadRequest("Reading not found.")
    return render(request, 'reports/soil_report.html', ctx)


# ── WeasyPrint PDF download ───────────────────────────────────────────────────

def soil_report_pdf(request):
    """Generate and download the SoiLENZ PDF using WeasyPrint from the HTML template."""
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    ctx = build_report_context(api_id)
    if ctx is None:
        return HttpResponseBadRequest("Reading not found.")

    html_str = render_to_string('reports/soil_report.html', ctx, request=request)
    try:
        from weasyprint import HTML as WP_HTML
        pdf_bytes = WP_HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf()
    except Exception as e:
        return HttpResponseBadRequest(f"PDF generation failed: {e}")

    farmer_name = ctx['meta'].get('farmer_name') or 'report'
    slug = farmer_name.replace(' ', '_')
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="SoiLENZ_Report_{slug}.pdf"'
    resp['Content-Length'] = len(pdf_bytes)
    return resp


# ── Legacy endpoint (keeps /crop-recommendation-pdf/ working) ─────────────────

def download_recommendation_pdf(request):
    return soil_report_pdf(request)