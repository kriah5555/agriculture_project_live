import logging
import os
from django.http import HttpResponseBadRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

import requests as _requests

from agri_ai.crop import run_model
from agri_ai.fertilizer import recommend_fertilizer
from agri_ai.crop_recommendation import recommend_crops, get_states as get_crop_rec_states
from .report_builder import build_report_context
from translations import api as tr_api
from .i18n import strings as report_strings


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

def build_recommendation(api_data, climate=None):
    """Run the crop-suitability model for a DeviseApis reading, used by the
    api-overview page's Crop Recommendation tab.

    climate: optional pre-fetched (temperature, humidity, rainfall) tuple —
    pass this when the caller already fetched climate for the same lat/lon
    elsewhere (e.g. also for build_crop_recommendation_v2) to avoid a second
    redundant Open-Meteo round trip on the same page load.
    """
    if not api_data:
        return 'No data found for the provided api id.'

    if climate is not None:
        temperature, humidity, rainfall = climate
    else:
        lat, lon = api_data.latitude, api_data.longitude
        if lat and lon:
            try:
                temperature, humidity, rainfall = _fetch_climate_for_recommendation(lat, lon)
            except RuntimeError:
                temperature, humidity, rainfall = 26.0, 65.0, 750.0
        else:
            temperature, humidity, rainfall = 26.0, 65.0, 750.0

    return run_model({
        'N':           [api_data.nitrogen],
        'P':           [api_data.phosphorous],
        'K':           [api_data.potassium],
        'temperature': [temperature],
        'humidity':    [humidity],
        'ph':          [api_data.ph],
        'rainfall':    [rainfall],
    })


# ── Fertilizer recommendation (api-overview Fertilizer tab + mobile API) ──────

def build_fertilizer_recommendation(api_data, state_override=None, crop_override=None):
    """Run the RDF-based fertilizer engine for a DeviseApis reading, used by the
    api-overview page's Fertilizer tab and its mobile API counterpart.

    State/crop are pulled from the linked Farmer first (the only place state is
    recorded), falling back to the reading's own crop_type. Either can be
    overridden explicitly — needed when a reading has no linked farmer, or the
    auto-detected crop doesn't match the reference dataset's naming.
    """
    if not api_data:
        return {'error': 'no_reading'}

    farmer = api_data.farmer
    state  = (state_override or (farmer.state if farmer else '') or '').strip()
    crop   = (
        crop_override
        or (farmer.crop if farmer and farmer.crop else '')
        or api_data.crop_type.replace('_or_', '/').replace('_', ' ').title()
    ).strip()

    soil_values = {
        'ph':             api_data.ph,
        'ec':             api_data.ec,
        'organic_carbon': api_data.oc,
        'nitrogen':       api_data.nitrogen,
        'phosphorus':     api_data.phosphorous,
        'potassium':      api_data.potassium,
        'sulphur':        api_data.sulphur,
        'calcium':        api_data.calcium,
        'magnesium':      api_data.magnesium,
        'zinc':           api_data.zinc,
        'iron':           api_data.iron,
        'manganese':      api_data.manganese,
        'copper':         api_data.copper,
        'boron':          api_data.boron,
    }

    result = recommend_fertilizer(state, crop, soil_values)
    result.setdefault('state', state)
    result.setdefault('crop', crop)
    return result


# ── Detailed crop recommendation (api-overview Crop Match tab + mobile API) ───

def build_crop_recommendation_v2(api_data, state_override=None, climate=None):
    """Run the rule-based, explainable multi-crop recommender for a DeviseApis
    reading, used by the api-overview page's Crop Match tab and its mobile API
    counterpart. Returns top-5 crops with per-parameter score breakdown,
    deficiencies, and a Crop Guide (duration/season/water/pests/fertilizer/
    harvest), scored against this reading's own ph/ec/oc/npk/micronutrient
    values — no external dataset input required.

    State is pulled from the linked Farmer first (only place state is
    recorded), overridable when there's no linked farmer or it doesn't match
    the reference dataset's state names.

    climate: optional pre-fetched (temperature, humidity, rainfall) tuple —
    pass this when the caller already fetched climate for the same lat/lon
    elsewhere (e.g. also for build_recommendation) to avoid a second
    redundant Open-Meteo round trip on the same page load. When omitted,
    fetches it here same as before; when the fetch fails, temp_current stays
    None (shown as "N/A" rather than a guessed value).
    """
    if not api_data:
        return {'error': 'no_reading'}

    farmer = api_data.farmer
    state  = (state_override or (farmer.state if farmer else '') or '').strip()
    if not state:
        return {'error': 'missing_state'}

    soil_values = {
        'ph': api_data.ph, 'ec': api_data.ec, 'oc': api_data.oc,
        'n':  api_data.nitrogen, 'p': api_data.phosphorous, 'k': api_data.potassium,
        's':  api_data.sulphur, 'ca': api_data.calcium, 'mg': api_data.magnesium,
        'zn': api_data.zinc, 'fe': api_data.iron, 'mn': api_data.manganese,
        'cu': api_data.copper, 'b': api_data.boron,
    }

    if climate is not None:
        temp_current = climate[0]
    else:
        temp_current = None
        lat, lon = api_data.latitude, api_data.longitude
        if lat and lon:
            try:
                temp_current, _humidity, _rainfall = _fetch_climate_for_recommendation(lat, lon)
            except RuntimeError:
                temp_current = None

    result = recommend_crops(state, soil_values, temp_current=temp_current)
    result.setdefault('state', state)
    return result


# ── HTML Report preview ───────────────────────────────────────────────────────

def soil_report_html(request):
    """SoiLENZ report (browser view).

    Building the report takes seconds (ML/climate lookups, heatmaps, Esri
    imagery), so by default this returns an instant loading shell that
    fetches ?partial=1 and swaps the finished report in. ?partial=1,
    ?partial=0 (no-JS fallback) and ?full=1 render the full report directly.
    The PDF (soil_report_pdf) never uses the shell.
    """
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    # URL-driven: ?lang= (active language) else the default — never a
    # remembered session/cookie value (see translations.api).
    lang = tr_api.language_from_request(request)
    if request.GET.get('partial') not in ('0', '1') and request.GET.get('full') != '1':
        from agriapp.models import DeviseApis
        if not str(api_id).isdigit() or not DeviseApis.objects.filter(pk=int(api_id)).exists():
            return HttpResponseBadRequest("Reading not found.")
        S = report_strings(lang)
        g = lambda k: S.get(f'report.loading.{k}', k)
        q = request.GET.copy(); q['partial'] = '0'; q['lang'] = lang
        return render(request, 'reports/soil_report_shell.html', {
            'lang': lang,
            'txt': {
                'title': g('title'),
                'steps': [g(f'step{i}') for i in range(1, 6)],
                'error': g('error'), 'retry': g('retry'), 'open_full': g('open_full'),
            },
            'full_url': f"{request.path}?{q.urlencode()}",
        })
    ctx = build_report_context(api_id, lang)
    if ctx is None:
        return HttpResponseBadRequest("Reading not found.")
    return render(request, 'reports/soil_report.html', ctx)


# ── PDF download ──────────────────────────────────────────────────────────────
#
# The downloaded PDF is a print of the very same HTML page the browser shows
# (same template, same build_report_context), rendered by headless Chromium
# through Playwright, so the download looks exactly like /soil-report/.
# WeasyPrint is only a fallback for servers without Playwright/Chromium: it
# has its own layout engine (no JS, different flex/grid sizing), so it can't
# match the browser exactly.

logger = logging.getLogger(__name__)

import mimetypes as _mimetypes
_mimetypes.add_type('font/woff2', '.woff2')


def _local_file_for_url(url, own_host):
    """Map a URL on this site's own /static/ or /media/ to a file on disk, or
    None. Fetching them back over HTTP through nginx made the report slow
    enough to hit the gunicorn worker timeout (502), and with sync workers
    the server could end up waiting on itself."""
    from urllib.parse import urlparse, unquote
    from django.conf import settings
    from django.contrib.staticfiles import finders

    parsed = urlparse(url)
    if parsed.netloc != own_host:
        return None
    static_prefix = settings.STATIC_URL if settings.STATIC_URL.startswith('/') else '/' + settings.STATIC_URL
    media_url     = settings.MEDIA_URL or ''
    media_prefix  = media_url if media_url.startswith('/') else '/' + media_url
    path = unquote(parsed.path)

    if path.startswith(static_prefix):
        rel = path[len(static_prefix):]
        found = finders.find(rel)
        if not found and settings.STATIC_ROOT:
            candidate = os.path.join(settings.STATIC_ROOT, rel)
            found = candidate if os.path.isfile(candidate) else None
        return found
    if settings.MEDIA_ROOT and media_prefix != '/' and path.startswith(media_prefix):
        # Uploaded files (e.g. the farmer photo) — never outside MEDIA_ROOT.
        root = os.path.realpath(settings.MEDIA_ROOT)
        candidate = os.path.realpath(os.path.join(root, path[len(media_prefix):]))
        if candidate.startswith(root + os.sep) and os.path.isfile(candidate):
            return candidate
    return None


def _local_static_fetcher(own_host):
    """WeasyPrint url_fetcher that reads this site's /static/ and /media/
    files from disk (see _local_file_for_url)."""
    import mimetypes
    from weasyprint import default_url_fetcher

    def fetch(url, *args, **kwargs):
        path = _local_file_for_url(url, own_host)
        if path:
            with open(path, 'rb') as f:
                return {
                    'string': f.read(),
                    'mime_type': mimetypes.guess_type(path)[0] or 'application/octet-stream',
                    'redirected_url': url,
                }
        return default_url_fetcher(url, *args, **kwargs)

    return fetch


CHROMIUM_TIMEOUT_MS = 60_000
_SYSTEM_CHROME = '/usr/bin/google-chrome'


def _html_to_pdf_chromium(html_str, base_url, own_host):
    """Print the report HTML to PDF with headless Chromium (Playwright).
    Launches its own browser per call: Playwright's sync API is bound to the
    thread that started it, and this also runs from pdf_cache's background
    threads. Raises on any failure so the caller can fall back."""
    import mimetypes
    from playwright.sync_api import sync_playwright

    # Resolve the template's root-relative /static/ and /media/ URLs.
    base_tag = f'<base href="{base_url}">'
    html_str = html_str.replace('<head>', '<head>\n' + base_tag, 1) if '<head>' in html_str else base_tag + html_str

    def route(r):
        path = _local_file_for_url(r.request.url, own_host)
        if path:
            with open(path, 'rb') as f:
                return r.fulfill(status=200, body=f.read(),
                                 content_type=mimetypes.guess_type(path)[0] or 'application/octet-stream')
        if r.request.url.startswith(base_url):
            return r.abort()          # never call back into this server
        return r.continue_()          # external CDN assets (Font Awesome)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(timeout=CHROMIUM_TIMEOUT_MS)
        except Exception:
            if not os.path.exists(_SYSTEM_CHROME):
                raise
            browser = p.chromium.launch(executable_path=_SYSTEM_CHROME, timeout=CHROMIUM_TIMEOUT_MS)
        try:
            page = browser.new_page()
            page.set_default_timeout(CHROMIUM_TIMEOUT_MS)
            page.route('**/*', route)
            try:
                page.set_content(html_str, wait_until='networkidle', timeout=CHROMIUM_TIMEOUT_MS)
            except Exception:
                # e.g. an unreachable CDN never going idle — print what loaded
                logger.warning('SoiLENZ PDF: page did not reach network idle; printing anyway')
            page.evaluate('document.fonts && document.fonts.ready')
            return page.pdf(
                format='A4', print_background=True, prefer_css_page_size=True,
                margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
            )
        finally:
            browser.close()


def _html_to_pdf_weasyprint(html_str, base_url, own_host):
    from weasyprint import HTML as WP_HTML
    return WP_HTML(
        string=html_str,
        base_url=base_url,
        url_fetcher=_local_static_fetcher(own_host),
    ).write_pdf()


def soil_report_pdf(request):
    """Generate and download the SoiLENZ PDF using WeasyPrint from the HTML template."""
    api_id = request.GET.get("api_id")
    if not api_id:
        return HttpResponseBadRequest("Missing api_id parameter.")
    try:
        result = render_soil_report_pdf(api_id, request.build_absolute_uri('/'), request.get_host(),
                                        lang=tr_api.language_from_request(request))
    except Exception as e:
        return HttpResponseBadRequest(f"PDF generation failed: {e}")
    if result is None:
        return HttpResponseBadRequest("Reading not found.")
    return pdf_response(*result)


def render_soil_report_pdf(api_id, base_url, own_host, lang='en'):
    """Build the SoiLENZ report PDF. Returns (pdf_bytes, filename), or None
    if the reading doesn't exist. Doesn't need the request, so it can also
    run in a background thread (see reports/pdf_cache.py)."""
    lang = tr_api.normalize_lang(lang)
    ctx = build_report_context(api_id, lang)
    if ctx is None:
        return None
    # Exactly what soil_report_html renders.
    html_str = render_to_string('reports/soil_report.html', ctx)
    try:
        pdf_bytes = _html_to_pdf_chromium(html_str, base_url, own_host)
    except Exception as e:
        logger.warning(
            'SoiLENZ PDF: headless Chromium unavailable/failed (%s); falling back to '
            'WeasyPrint, which will not match the on-screen report exactly. Install with: '
            'pip install playwright && playwright install --with-deps chromium', e)
        pdf_bytes = _html_to_pdf_weasyprint(html_str, base_url, own_host)
    farmer_name = ctx['meta'].get('farmer_name') or 'report'
    suffix = '' if lang == tr_api.default_language_code() else f'_{lang.upper()}'
    return pdf_bytes, f"SoiLENZ_Report_{farmer_name.replace(' ', '_')}{suffix}.pdf"


def pdf_response(pdf_bytes, filename):
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    resp['Content-Length'] = len(pdf_bytes)
    return resp


# ── Legacy endpoint (keeps /crop-recommendation-pdf/ working) ─────────────────

def download_recommendation_pdf(request):
    return soil_report_pdf(request)