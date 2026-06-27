"""
Carbon credit calculation engine and PDF report generator.
Ported from Carbon-Credit-App/backend/services/.
"""
import io
import requests as http
from django.conf import settings

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors


# ── Settings ──────────────────────────────────────────────────────────────────

def _market_rate() -> float:
    return float(getattr(settings, 'CARBON_MARKET_RATE', 1400.0))

def _weather_api_key() -> str:
    return getattr(settings, 'OPENWEATHERMAP_API_KEY', '')


# ── Weather ───────────────────────────────────────────────────────────────────

_STATE_CITY = {
    'karnataka':   'Bangalore',
    'maharashtra': 'Mumbai',
    'punjab':      'Ludhiana',
}

def _state_to_city(state: str) -> str:
    s = state.strip().lower()
    for k, v in _STATE_CITY.items():
        if k in s:
            return v
    return 'Bangalore'

def _get_weather(city: str, fallback: dict) -> dict:
    api_key = _weather_api_key()
    if not api_key:
        return {**fallback, 'source': 'user_input'}
    try:
        resp = http.get(
            'https://api.openweathermap.org/data/2.5/weather',
            params={'q': city, 'appid': api_key, 'units': 'metric'},
            timeout=5,
        )
        resp.raise_for_status()
        d = resp.json()
        return {
            'temperature': float(d['main']['temp']),
            'humidity':    float(d['main']['humidity']),
            'rainfall':    float(d.get('rain', {}).get('1h', 0.0)),
            'source':      'live',
        }
    except Exception:
        return {**fallback, 'source': 'user_input_fallback'}


# ── Score calculations ────────────────────────────────────────────────────────

def _sustainability_score(soil_score, organic, irrigation, fertilizer) -> float:
    irr  = irrigation.strip().lower()
    fert = fertilizer.strip().lower()
    irr_val  = 100 if irr  == 'drip'    else (80 if irr  == 'sprinkler' else 50)
    fert_val = 100 if fert == 'low'     else (70 if fert == 'medium'    else 40)
    org_val  = 100 if organic else 60
    return round(
        soil_score * 0.40 + org_val * 0.25 + irr_val * 0.20 + fert_val * 0.15, 2
    )

def _esg_score(soil_score, organic, irrigation, fertilizer) -> float:
    irr  = irrigation.strip().lower()
    fert = fertilizer.strip().lower()
    org_val  = 100 if organic else 60
    irr_val  = 100 if irr  == 'drip'    else (80 if irr  == 'sprinkler' else 50)
    fert_val = 100 if fert == 'low'     else (70 if fert == 'medium'    else 40)
    env_impact = soil_score * 0.50 + org_val * 0.50
    carbon_red = org_val  * 0.50 + fert_val * 0.50
    if organic and irr == 'drip':       sust_prac = 100
    elif organic and irr == 'sprinkler': sust_prac = 90
    elif organic and irr == 'flood':    sust_prac = 70
    elif irr == 'drip':                 sust_prac = 80
    elif irr == 'sprinkler':            sust_prac = 70
    else:                               sust_prac = 50
    return round(env_impact * 0.50 + irr_val * 0.20 + carbon_red * 0.20 + sust_prac * 0.10, 2)

def _trust_score(esg, sustainability) -> float:
    return round((esg + sustainability) / 2.0, 2)

def _climate_risk(soil_score, temp, rain, crop_type) -> str:
    pts = 0
    if soil_score < 30: pts += 4
    elif soil_score < 50: pts += 2
    if temp >= 38: pts += 3
    elif temp >= 35: pts += 1
    elif temp < 10: pts += 2
    if rain < 40: pts += 3
    elif rain < 60: pts += 1
    elif rain > 120: pts += 2
    crop = crop_type.strip().lower()
    if crop in ('rice', 'sugarcane') and rain < 60: pts += 2
    elif crop == 'cotton' and rain > 100: pts += 2
    return 'Low' if pts <= 2 else ('Medium' if pts <= 5 else 'High')

def _ndvi_health(sustainability) -> str:
    if sustainability >= 90: return 'Excellent'
    if sustainability >= 75: return 'Healthy'
    if sustainability >= 60: return 'Moderate'
    return 'Weak'


# ── Main calculator ───────────────────────────────────────────────────────────

def calculate_carbon_all(data: dict) -> dict:
    farm_size   = float(data.get('farm_size', 1.0))
    crop_type   = str(data.get('crop_type', 'Rice')).strip()
    soil_score  = float(data.get('soil_score', 50.0))
    organic     = bool(data.get('organic', False))
    state       = str(data.get('state', 'Karnataka')).strip()
    irrigation  = str(data.get('irrigation', 'Flood')).strip()
    fertilizer  = str(data.get('fertilizer_usage', 'Medium')).strip()

    user_temp = data.get('temperature')
    user_rain = data.get('rainfall')
    user_hum  = data.get('humidity')

    fallback = {
        'temperature': float(user_temp) if user_temp is not None else 25.0,
        'humidity':    float(user_hum)  if user_hum  is not None else 60.0,
        'rainfall':    float(user_rain) if user_rain is not None else 0.0,
    }

    weather   = _get_weather(_state_to_city(state), fallback)
    temp, rain, hum = weather['temperature'], weather['rainfall'], weather['humidity']
    w_source  = 'Live API' if weather.get('source') == 'live' else 'User-Provided'

    sust  = _sustainability_score(soil_score, organic, irrigation, fertilizer)
    esg   = _esg_score(soil_score, organic, irrigation, fertilizer)
    trust = _trust_score(esg, sust)
    risk  = _climate_risk(soil_score, temp, rain, crop_type)
    ndvi  = _ndvi_health(sust)

    crop_factors = {'rice': 1.2, 'sugarcane': 2.0, 'millet': 1.8, 'cotton': 1.0}
    c_factor = crop_factors.get(crop_type.lower(), 1.2)
    o_factor = 1.3 if organic else 1.0
    irr_factors  = {'drip': 1.4, 'sprinkler': 1.2, 'flood': 1.0}
    i_factor = irr_factors.get(irrigation.lower(), 1.0)
    fert_factors = {'low': 1.3, 'medium': 1.0, 'high': 0.7}
    f_factor = fert_factors.get(fertilizer.lower(), 1.0)

    clim = 1.0
    if temp > 35:   clim -= 0.15
    elif temp < 15: clim -= 0.10
    if rain < 50:   clim -= 0.20
    elif rain > 120: clim -= 0.10
    if hum > 80 or hum < 30: clim -= 0.05
    if 20 <= temp <= 30 and 60 <= rain <= 100: clim += 0.10
    clim = max(0.5, min(1.3, clim))

    credits      = round(farm_size * c_factor * (soil_score / 100.0) * o_factor * i_factor * f_factor * clim, 2)
    co2_offset   = round(credits * 0.35, 2)
    rate         = _market_rate()
    yearly       = round(credits * rate, 2)
    breakdown    = (
        f"Credits = Size({farm_size}) × CropFactor({c_factor}) × SoilHealth({soil_score}/100) × "
        f"OrganicFactor({o_factor}) × IrrigationFactor({i_factor}) × FertilizerFactor({f_factor}) × "
        f"ClimateFactor({clim:.2f})"
    )

    return {
        'carbon_credits':       credits,
        'co2_offset':           co2_offset,
        'esg_score':            esg,
        'sustainability_score': sust,
        'trust_score':          trust,
        'climate_risk':         risk,
        'ndvi_health':          ndvi,
        'yearly_projection':    yearly,
        'market_value':         yearly,
        'market_rate':          rate,
        'temperature':          temp,
        'rainfall':             rain,
        'humidity':             hum,
        'weather_source':       w_source,
        'formula_breakdown':    breakdown,
    }


# ── PDF generator ─────────────────────────────────────────────────────────────

def build_pdf_report(
    farmer_name, crop_type, state, soil_score,
    carbon_credits, esg_score, sustainability_score,
    co2_offset, yearly_projection, verification_status,
    carbon_credit_potential, recommendations,
) -> bytes:
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=letter)

    c.setFont('Helvetica-Bold', 22)
    c.setFillColor(colors.HexColor('#065f46'))
    c.drawString(50, 750, 'ARKASHINE CLIMATE ASSESSMENT')

    c.setFont('Helvetica', 12)
    c.setFillColor(colors.HexColor('#4b5563'))
    c.drawString(50, 730, 'AI Climate Intelligence & Carbon Credit Ecosystem')

    c.setStrokeColor(colors.HexColor('#d1d5db'))
    c.setLineWidth(1)
    c.line(50, 715, 562, 715)

    c.setFont('Helvetica-Bold', 14)
    c.setFillColor(colors.HexColor('#111827'))
    c.drawString(50, 685, 'Farmer & Land Profile')

    c.setFont('Helvetica', 11)
    c.drawString(50, 660, f'Farmer Name: {farmer_name}')
    c.drawString(50, 640, f'Crop Type: {str(crop_type).capitalize()}')
    c.drawString(50, 620, f'Location State: {str(state).capitalize()}')

    c.setFont('Helvetica-Bold', 14)
    c.drawString(320, 685, 'Climate & Carbon Metrics')

    c.setFont('Helvetica', 11)
    c.drawString(320, 660, f'Carbon Credits (ICU): {carbon_credits:.2f}')
    c.drawString(320, 640, f'CO2 Offset: {co2_offset:.2f} Tons')
    c.drawString(320, 620, f'Estimated Carbon Income: INR {yearly_projection:,.2f}')

    c.line(50, 595, 562, 595)

    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, 565, 'Sustainability Assessment')

    c.setFont('Helvetica', 11)
    c.drawString(50, 540, f'ESG Score: {esg_score:.1f}%')
    c.drawString(50, 520, f'Soil Score: {soil_score:.1f}/100')
    c.drawString(50, 500, f'Verification: {verification_status}')
    c.drawString(50, 480, f'Carbon Credit Potential: {carbon_credit_potential}')

    c.line(50, 455, 562, 455)

    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, 425, 'AI Rule-Based Recommendations')

    c.setFont('Helvetica', 10)
    y = 400
    if recommendations:
        for rec in recommendations:
            c.drawString(60, y, f'- {rec}')
            y -= 18
            if y < 80:
                break
    else:
        c.drawString(60, y, 'No recommendations needed at this time.')

    c.setFont('Helvetica-Oblique', 9)
    c.setFillColor(colors.HexColor('#9ca3af'))
    c.drawString(50, 50, 'Generated by Arkashine Climate Intelligence Platform.')

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()
    return pdf