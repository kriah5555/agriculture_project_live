from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .ai_model.model import run_model
from .report_builder import build_report_context
from agriapp.models import DeviseApis


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
        result = run_model({
            'N': [api_data.nitrogen], 'P': [api_data.phosphorous],
            'K': [api_data.potassium], 'temperature': [10],
            'humidity': [10], 'ph': [api_data.ph], 'rainfall': [10],
        })
    else:
        result = 'No data found for the provided api id.'
    return render(request, 'predicter/crop_recom_dashb.html', {
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
    return render(request, 'predicter/soil_report.html', ctx)


# ── WeasyPrint PDF download ───────────────────────────────────────────────────

def soil_report_pdf(request):
    """Generate and download the SoiLENZ PDF using WeasyPrint from the HTML template."""
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    ctx = build_report_context(api_id)
    if ctx is None:
        return HttpResponseBadRequest("Reading not found.")

    html_str = render_to_string('predicter/soil_report.html', ctx, request=request)
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