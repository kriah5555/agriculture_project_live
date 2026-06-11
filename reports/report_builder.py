"""
report_builder.py
─────────────────
Builds the full context dict for the SoiLENZ HTML/PDF report.
All parameter info functions, scoring, and display helpers are
imported from agriapp.reports.soilenz_pdf to avoid duplication.
"""
from agriapp.reports.soilenz_pdf import (
    _ph_info, _ec_info, _oc_info, _n_info, _p_info, _k_info,
    _ca_info, _mg_info, _s_info, _fe_info, _mn_info, _cu_info,
    _zn_info, _b_info,
    PARAMS_14, _categorize_nutrients, _soil_health_score, _fertility_label,
)
from agriapp.models import DeviseApis

# ── Parameter definitions (name, unit, key, info_fn, display decimals) ────────
_PARAM_INFO = {
    'ph':             _ph_info,
    'ec':             _ec_info,
    'organic_carbon': _oc_info,
    'n':              _n_info,
    'p':              _p_info,
    'k':              _k_info,
    'ca':             _ca_info,
    'mg':             _mg_info,
    's':              _s_info,
    'fe':             _fe_info,
    'mn':             _mn_info,
    'cu':             _cu_info,
    'zn':             _zn_info,
    'b':              _b_info,
}

# CSS color class names for status
_STATUS_CSS = {
    'Low': 'red', 'Very Low': 'red', 'Deficient': 'red',
    'Acidic': 'orange', 'High EC': 'orange', 'Very High': 'red',
    'Medium': 'yellow', 'Marginal': 'yellow', 'Moderate': 'yellow',
    'Normal': 'green', 'Sufficient': 'green', 'Adequate': 'green',
    'Alkaline': 'red', 'High': 'green',
    'N/A': 'gray',
}

def _css(status):
    for k, v in _STATUS_CSS.items():
        if k in status:
            return v
    return 'gray'

def _fmt(v, dec=2):
    return f'{v:.{dec}f}' if v is not None else 'N/A'


# ── Crop profiles for suitability scoring ────────────────────────────────────
CROP_PROFILES = [
    # (name, emoji, ph_ideal, oc_min, n_min, k_min, notes)
    ('Wheat',           '🌾', (6.0, 8.0), 0.4, 160, 100, 'Suitable; balanced fertility required'),
    ('Paddy',           '🌾', (5.5, 7.0), 0.5, 150, 120, 'Best suited to alkaline pH'),
    ('Sorghum (Jowar)', '🌿', (5.5, 8.5), 0.3, 120,  80, 'Tolerant to alkaline soil & low N'),
    ('Pearl Millet',    '🌿', (6.0, 8.5), 0.3, 100,  80, 'Drought tolerant; adapts well'),
    ('Cotton',          '🌱', (5.8, 8.0), 0.4, 150, 120, 'Performs well with high K & alkaline pH'),
    ('Pigeon Pea (Tur)','🫛', (5.5, 7.5), 0.4, 100,  80, 'Good for soil fertility & low N conditions'),
    ('Groundnut',       '🥜', (6.0, 7.5), 0.4, 100, 100, 'Needs better organic matter'),
    ('Green Gram',      '🫘', (6.0, 7.5), 0.5, 120,  80, 'Sensitive to low Mn & B'),
    ('Tomato',          '🍅', (6.0, 6.8), 0.7, 250, 150, 'Sensitive to high pH, low OC & Mn'),
    ('Brinjal',         '🍆', (5.5, 7.0), 0.5, 200, 120, 'Needs rich organic matter & balanced nutrients'),
    ('Cauliflower',     '🥦', (6.0, 7.0), 0.7, 280, 150, 'Requires low pH & high organic matter'),
]


def _crop_score(profile, preds, env):
    _, _, ph_ideal, oc_min, n_min, k_min, _ = profile
    ph  = preds.get('ph') or 7.0; oc = preds.get('organic_carbon') or 0.0
    n   = preds.get('n') or 0.0;  k  = preds.get('k') or 0.0
    s = 10.0
    if ph < ph_ideal[0]:   s -= (ph_ideal[0] - ph) * 1.5
    elif ph > ph_ideal[1]: s -= (ph - ph_ideal[1]) * 2.0
    if oc < oc_min:        s -= (oc_min - oc) * 3.0
    if n  < n_min:         s -= (n_min - n) / max(n_min, 1) * 2.5
    if k  < k_min:         s -= (k_min - k) / max(k_min, 1) * 1.0
    s += (env.get('ndvi', 0.5) - 0.4) * 2.0
    return round(max(0.0, min(10.0, s)), 1)


# ── Main builder ──────────────────────────────────────────────────────────────

def build_report_context(api_id):
    """
    Load a DeviseApis reading by pk and return a complete context dict
    ready to render soil_report.html (or pass to the ReportLab PDF).

    Returns None if the reading is not found.
    """
    try:
        api_id   = int(api_id)
        api_data = DeviseApis.objects.select_related('farmer', 'device').filter(pk=api_id).first()
    except (ValueError, TypeError):
        return None
    if not api_data:
        return None

    def _v(val):
        return float(val) if val else None

    preds = {
        'ph':             _v(api_data.ph),
        'ec':             _v(api_data.ec or api_data.electrical_conduction),
        'organic_carbon': _v(api_data.oc or api_data.organic_carboa),
        'n':              _v(api_data.nitrogen),
        'p':              _v(api_data.phosphorous),
        'k':              _v(api_data.potassium),
        'ca':             _v(api_data.calcium),
        'mg':             _v(api_data.magnesium),
        's':              _v(api_data.sulphur),
        'fe':             _v(api_data.iron),
        'mn':             _v(api_data.manganese),
        'cu':             _v(api_data.copper),
        'zn':             _v(api_data.zinc),
        'b':              _v(api_data.boron),
    }

    lat = api_data.latitude  or 0.0
    lon = api_data.longitude or 0.0

    # ML enrichment (optional; falls back to defaults)
    env = {'ndvi': 0.55, 'temperature_c': 28.0, 'rainfall_mm': 950.0, 'elevation_m': 200.0}
    fertility = 'Medium'
    try:
        from agri_ai.soil     import load_models, predict_for_point, classify_fertility
        from agri_ai.features import get_weather, get_ndvi, get_elevation, get_soil_texture
        if lat and lon:
            lgbm, rf = load_models()
            if lgbm:
                ml_preds, env = predict_for_point(lat, lon, lgbm, get_weather, get_ndvi, get_elevation, get_soil_texture)
                fertility = classify_fertility(ml_preds, env, rf)
                for k2, v2 in preds.items():
                    if v2 is not None: ml_preds[k2] = v2
                preds = ml_preds
    except Exception:
        pass

    farmer = api_data.farmer
    crop   = (farmer.crop if farmer and farmer.crop else (api_data.crop_type or ''))

    farmer_image_url = ''
    try:
        if farmer and farmer.farmer_image:
            farmer_image_url = farmer.farmer_image.url
    except Exception:
        pass

    meta = {
        'api_id':             api_data.pk,
        'farmer_name':        farmer.farmer_name if farmer else (api_data.area_name or ''),
        'farmer_mobile':      farmer.phone       if farmer else '',
        'farmer_image_url':   farmer_image_url,
        'farmer_image_path':  farmer.farmer_image.path if (farmer and farmer.farmer_image) else '',
        'location':           (f"{farmer.village}, {farmer.district}, {farmer.state}" if farmer else ''),
        'lat':                lat,
        'lon':                lon,
        'field_area':         (f"{farmer.land_area} acres" if farmer and farmer.land_area else '–'),
        'crop':               crop,
        'agro_zone':          '–',
        'analysis_date':      api_data.created_at.strftime('%d %b %Y')          if api_data.created_at else '',
        'analysis_date_long': api_data.created_at.strftime('%d %B %Y')          if api_data.created_at else '',
        'report_time':        api_data.created_at.strftime('%d/%m/%Y %I:%M %p') if api_data.created_at else '',
        'lab_name':           'Arkashine Labs',
        'ai_crop':            '',
    }

    # AI recommendation
    try:
        from agri_ai.crop import run_model
        ai_in = {'N': [float(preds.get('n') or 100)], 'P': [float(preds.get('p') or 20)],
                 'K': [float(preds.get('k') or 100)], 'temperature': [float(env.get('temperature_c', 25))],
                 'humidity': [60.0], 'ph': [float(preds.get('ph') or 7.0)],
                 'rainfall': [float(env.get('rainfall_mm', 500))]}
        meta['ai_crop'] = run_model(ai_in) or ''
    except Exception:
        pass

    # ── Pre-compute all display values ────────────────────────────────────────

    # 14-parameter table rows
    DEFS = [(n, u, k2, d) for n, u, k2, _ in PARAMS_14 for d in [3 if k2 in ('ph','ec','ca','mg','s','fe','mn','cu','zn','b') else 2]]
    params_display = []
    for name, unit, key, _ in PARAMS_14:
        val = preds.get(key)
        dec = 3 if key in ('ph','ec','ca','mg','s','fe','mn','cu','zn','b') else 2
        status, _, ideal, interp = _PARAM_INFO[key](val)
        params_display.append({
            'name':   name,    'unit':   unit,  'key':    key,
            'value':  _fmt(val, dec),            'status': status,
            'css':    _css(status),              'ideal':  ideal,
            'interp': interp,
        })

    # Nutrient categories
    low_i, med_i, high_i, suff_i, adeq_i = _categorize_nutrients(preds)

    # Soil health score & gauge
    score = _soil_health_score(preds, env)
    slabel, _ = _fertility_label(score)
    if score >= 75:   s_css = 'green'
    elif score >= 55: s_css = 'yellow'
    elif score >= 35: s_css = 'orange'
    else:             s_css = 'red'

    # Carbon credit
    oc = preds.get('organic_carbon') or 0.3
    ndvi = env.get('ndvi', 0.5) or 0.5
    oc_after   = round(min(oc + 0.42, 1.5), 2)
    bio_before = round(1.0 + ndvi * 3, 1)
    bio_after  = round(bio_before * 1.6, 1)
    oc_seq     = round((oc_after - oc) / 0.1 * 50)
    bio_seq    = round(bio_after * 120)
    total_co2  = int(oc_seq + bio_seq)
    c_score    = min(100, int(50 + ndvi * 30 + oc * 15))
    c_label    = 'Excellent' if c_score >= 80 else ('Good' if c_score >= 60 else 'Moderate')

    # Amendment plan
    _ph = preds.get('ph') or 7.0; _n = preds.get('n') or 0; _p = preds.get('p') or 0
    _k  = preds.get('k') or 0;    _s = preds.get('s') or 0; _mn = preds.get('mn') or 0
    _mg = preds.get('mg') or 0;   _b = preds.get('b') or 0; _fe = preds.get('fe') or 0
    amends = [
        {'name':'FYM / Compost',           'dose':'1500–2000 kg','purpose':'Improve organic matter & soil biology',      'timing':'Pre sowing','pri':'HIGH',  'pcss':'red'},
        {'name':'Vermicompost',             'dose':'500 kg',      'purpose':'Improve microbial activity & soil health',    'timing':'Pre sowing','pri':'HIGH',  'pcss':'red'},
    ]
    if _ph > 7.5 or _mg < 1.0:
        amends.append({'name':'Gypsum / Dolomite','dose':'100 kg','purpose':'Improve Mg deficiency & soil balance','timing':'Pre sowing','pri':'HIGH','pcss':'red'})
    if _n < 280:
        amends.append({'name':'Urea (46% N)',   'dose':'55 kg',   'purpose':f'Nitrogen supply (N is {"low" if _n<140 else "medium"})', 'timing':'Split dose','pri':'HIGH','pcss':'red'})
    if _p < 70:
        amends.append({'name':'DAP (18-46-0)',  'dose':'40 kg' if _p<22 else '25 kg','purpose':'Basal phosphorus supply','timing':'Basal','pri':'MEDIUM','pcss':'orange'})
    amends.append({'name':'MOP (0-0-60)','dose':'No Need' if _k>=280 else '35 kg','purpose':'Potassium already high, no need' if _k>=280 else 'Potassium supply','timing':'Basal','pri':'LOW' if _k>=280 else 'MEDIUM','pcss':'green' if _k>=280 else 'orange'})
    if _mg < 1.0:
        amends.append({'name':'Magnesium Sulphate (MgSO4)','dose':'25 kg','purpose':'Correct Mg deficiency','timing':'Basal','pri':'HIGH','pcss':'red'})
    if _fe < 4.5:
        amends.append({'name':'Ferrous Sulphate (FeSO4)',  'dose':'10 kg','purpose':'Correct iron deficiency', 'timing':'Basal','pri':'HIGH','pcss':'red'})
    if _mn < 2.0:
        amends.append({'name':'MnSO4',  'dose':'10 kg','purpose':'Improve Mn availability','timing':'Basal','pri':'HIGH','pcss':'red'})
    if _b < 0.5:
        amends.append({'name':'Boron',  'dose':'1 kg', 'purpose':'Correct boron deficiency','timing':'Basal','pri':'HIGH','pcss':'red'})
    amends.append({'name':'Micronutrient Mix','dose':'As per label','purpose':'Balanced micronutrient support','timing':'Foliar','pri':'MEDIUM','pcss':'orange'})

    # Crop suitability
    crops_scored = []
    for cp in CROP_PROFILES:
        sc = _crop_score(cp, preds, env)
        if sc >= 8.0:   st, scss = 'Highly Recommended', 'green'
        elif sc >= 7.0: st, scss = 'Recommended',        'lt-green'
        elif sc >= 5.0: st, scss = 'Moderately Suitable','orange'
        else:           st, scss = 'Not Recommended',    'red'
        crops_scored.append({'name':cp[0],'icon':cp[1],'score':sc,'bar_pct':int(sc*10),'status':st,'scss':scss,'notes':cp[6]})
    crops_scored.sort(key=lambda x: -x['score'])
    top_crops = [c['name'] for c in crops_scored if c['score'] >= 6.0][:4]

    # Important corrections
    corrections = []
    if _n < 280:  corrections.append('Low N – apply urea in split doses.')
    if _p < 70:   corrections.append('Medium P – apply basal DAP.' if _p>=22 else 'Low P – apply DAP at basal dose.')
    if _k >= 280: corrections.append('High K – no potash needed.')
    if _s < 10:   corrections.append('Low S – apply sulfur (gypsum) & MgSO4.')
    if _mn < 2.0: corrections.append('Low Mn – apply MnSO4.')
    if _b < 0.5:  corrections.append('Medium-Low B – apply boron.')
    corrections.append('Maintain organic matter with FYM/Compost.')

    # Fertilizer recommendations (FertilizerCalculation engine)
    fertilizer_recs = []
    try:
        from agriapp import FertilizerCalculation
        fert_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(
            preds.get('n') or 0, preds.get('p') or 0, preds.get('k') or 0,
            preds.get('ph') or 7.0, preds.get('ec') or 0.5,
            preds.get('organic_carbon') or 0.3, crop or 'wheat'
        )
        if isinstance(fert_data, list):
            for item in fert_data[:3]:
                if isinstance(item, list):
                    fertilizer_recs.extend(item[:4])
                elif isinstance(item, str):
                    fertilizer_recs.append(item)
    except Exception:
        pass

    # Recommendation bullets
    rec_bullets = []
    if (preds.get('organic_carbon') or 0) < 0.5:
        rec_bullets.append('Soil fertility is medium. Improve organic matter and address nutrient deficiencies.')
    if low_i: rec_bullets.append(f'{", ".join(low_i[:3])} are low – apply as recommended.')
    ph_st, _, _, _ = _ph_info(preds.get('ph'))
    if 'Alkaline' in ph_st: rec_bullets.append('Alkaline pH – apply gypsum to balance soil pH.')
    if _p >= 22: rec_bullets.append('Phosphorus is medium – apply basal P (DAP).')
    if _k >= 280: rec_bullets.append('Potassium is very high – no additional potash needed.')
    rec_bullets.append('Use quality FYM/Compost and green manuring to improve soil health.')
    rec_bullets.append('Balanced fertilisation and timely irrigation will improve yield and soil health.')
    if meta.get('ai_crop'): rec_bullets.append(f'AI Recommendation: {meta["ai_crop"].title()} crop is best suited to this soil.')

    # Heatmap images for page 3 — matplotlib bicubic maps, cached in /tmp by value-hash
    import base64, hashlib, os as _os
    from agriapp.reports.soilenz_pdf import _heatmap_img

    def _hm_b64(key2, vmin, vmax, avg, rev):
        """Return base64 PNG, generating once and caching to /tmp."""
        tag = hashlib.md5(f"{key2}{vmin}{vmax}{round(avg,3)}{rev}".encode()).hexdigest()[:10]
        cache = f"/tmp/soilenz_hm_{tag}.b64"
        if _os.path.exists(cache):
            with open(cache) as f:
                return f.read()
        buf = _heatmap_img(4, 4, vmin, vmax, avg, reverse=rev, w_in=1.3, h_in=1.3)
        b64 = base64.b64encode(buf.read()).decode('utf-8')
        try:
            with open(cache, 'w') as f:
                f.write(b64)
        except Exception:
            pass
        return b64

    hm_params = [
        ('pH (0-14)',            'ph',             0,   14,   True),
        ('EC (dS/m)',            'ec',             0,   30,   True),
        ('Organic Carbon (%)',   'organic_carbon', 0,   1,    False),
        ('Nitrogen (kg/ha)',     'n',              125, 800,  False),
        ('Phosphorus (kg/ha)',   'p',              1,   200,  False),
        ('Potassium (kg/ha)',    'k',              20,  1000, False),
        ('Calcium (meq/100g)',   'ca',             1,   100,  False),
        ('Magnesium (meq/100g)', 'mg',             1,   50,   False),
        ('Sulfur (ppm)',         's',              2,   250,  False),
        ('Iron (ppm)',           'fe',             1,   50,   False),
        ('Zinc (ppm)',           'zn',             0.2, 10,   False),
        ('Manganese (ppm)',      'mn',             1,   25,   False),
        ('Copper (ppm)',         'cu',             0.1, 10,   False),
        ('Boron (ppm)',          'b',              0.1, 10,   False),
    ]
    hm_data = []
    for lbl, key2, vmin, vmax, rev in hm_params:
        avg = preds.get(key2) or ((vmin + vmax) / 2)
        img_b64 = _hm_b64(key2, vmin, vmax, avg, rev)
        stat, _, _, _ = _PARAM_INFO[key2](avg)
        hm_data.append({
            'label': lbl, 'key': key2,
            'vmin': _fmt(vmin, 0), 'vmax': _fmt(vmax, 0), 'avg': _fmt(avg, 2),
            'img_b64': img_b64,
            'status': stat, 'css': _css(stat),
        })

    return {
        # Raw data
        'preds':        preds,
        'env':          env,
        'fertility':    fertility,
        'meta':         meta,
        # Pre-computed display
        'params_display':   params_display,
        'soil_score':       score,
        'score_label':      slabel,
        'score_css':        s_css,
        'gauge_pct':        score,
        'low_list':         ', '.join(low_i),   'low_items':  low_i,
        'med_list':         ', '.join(med_i),   'med_items':  med_i,
        'high_list':        ', '.join(high_i),  'high_items': high_i,
        'suff_list':        ', '.join(suff_i),  'suff_items': suff_i,
        'adeq_list':        ', '.join(adeq_i),  'adeq_items': adeq_i,
        'amendments':       amends,
        'crops_scored':     crops_scored,
        'top_crops':        top_crops,
        'corrections':      corrections,
        'rec_bullets':      rec_bullets,
        'fertilizer_recs':  fertilizer_recs,
        'hm_data':          hm_data,
        # Carbon
        'total_co2':        total_co2,
        'oc_seq':           int(oc_seq),
        'bio_seq':          int(bio_seq),
        'bio_before':       bio_before,
        'bio_after':        bio_after,
        'oc_after':         oc_after,
        'carbon_score':     c_score,
        'carbon_label':     c_label,
    }