"""
reports/i18n.py
───────────────
Report-specific layer over the app-wide `translations` app.

Keys (module "report"):
  report.<name>          static template text     {% t "report.name" %}
  report.loading.<name>  the loading screen
  report.fmt.<name>      phrase templates with {placeholders} used by the builder
  report.phrase.<slug>_<hash>
                         phrases produced by report_builder / soilenz_pdf
                         (ratings, interpretations, crops, amendments …). The
                         key derives from the English source text, so the code
                         translates any phrase with tp(); unknown phrases fall
                         back to English unchanged.

Seed data: reports/translation_seed/ (catalog.json + en/kn/hi.json).
live_catalog() lists every phrase the code can currently emit; the
seed_translations command uses it to add new ones.
"""
import hashlib
import re

from translations import api as tr_api

MODULE = 'report'

FMT = {
    'report.fmt.field_area_acres': ('{area} acres', 'Field area, page 1/3'),
    'report.fmt.step2_no_change':  ('{status} — no change', 'Fertilizer step 2 adjustment note'),
    'report.fmt.step2_low':        ('Low soil → +25%', 'Fertilizer step 2 adjustment note'),
    'report.fmt.step2_high':       ('High soil → -25%', 'Fertilizer step 2 adjustment note'),
}


def strings(lang):
    """{key: text} of the report module in `lang` (default-language fallback)."""
    return tr_api.get_strings(MODULE, lang)


def phrase_key(text):
    """Stable key for a dynamic English phrase (readable slug + short hash, so
    'Low' and 'LOW' or two sentences with the same opening never clash)."""
    text = str(text)
    slug = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:48].strip('_') or 'x'
    return f"report.phrase.{slug}_{hashlib.md5(text.encode('utf-8')).hexdigest()[:5]}"


def t(S, key, **values):
    return tr_api.fmt(S.get(key) or FMT.get(key, (key,))[0], **values)


def tp(S, text):
    """Translate a dynamic English phrase (unknown phrases are returned as-is)."""
    if text is None or text == '':
        return text
    return S.get(phrase_key(text), text)


# Standard agro-climatic zone names (Karnataka's 10 zones). Zones outside this
# list are shown in English.
AGRO_ZONES = [
    'North Eastern Transition Zone', 'North Eastern Dry Zone', 'Northern Dry Zone',
    'Central Dry Zone', 'Eastern Dry Zone', 'Southern Dry Zone',
    'Southern Transition Zone', 'Northern Transition Zone', 'Hilly Zone', 'Coastal Zone',
]

# Common farmer-entered crops (meta.crop), in addition to the crop profiles.
COMMON_CROPS = [
    'Onion', 'Maize', 'Sugarcane', 'Ragi', 'Rice', 'Chilli', 'Potato', 'Banana',
    'Soybean', 'Turmeric', 'Coconut', 'Arecanut', 'Coffee', 'Grapes', 'Pomegranate',
    'Mango', 'Sunflower', 'Bengal Gram', 'Black Gram', 'Mustard', 'Cabbage',
    'Carrot', 'Beans', 'Okra', 'Garlic', 'Ginger', 'Tea', 'Jowar', 'Bajra',
]

# Soil amendment table rows built inline in build_report_context (page 5).
AMENDMENT_PHRASES = [
    'FYM / Compost', 'Improve organic matter & soil biology',
    'Vermicompost', 'Improve microbial activity & soil health',
    'Gypsum / Dolomite', 'Improve Mg deficiency & soil balance',
    'Urea (46% N)', 'Nitrogen supply (N is low)', 'Nitrogen supply (N is medium)',
    'DAP (18-46-0)', 'Basal phosphorus supply',
    'MOP (0-0-60)', 'No Need', 'Potassium already high, no need', 'Potassium supply',
    'Magnesium Sulphate (MgSO4)', 'Correct Mg deficiency',
    'Ferrous Sulphate (FeSO4)', 'Correct iron deficiency',
    'MnSO4', 'Improve Mn availability',
    'Boron', 'Correct boron deficiency',
    'Micronutrient Mix', 'As per label', 'Balanced micronutrient support',
    'Pre sowing', 'Split dose', 'Basal', 'Foliar',
    'HIGH', 'MEDIUM', 'LOW',
]


def dynamic_phrases():
    """[(english, notes)] of every phrase report_builder can emit."""
    from agriapp.reports.soilenz_pdf import PARAMS_14, SOIL_SAATHI_FIELD_THRESHOLDS
    from reports import report_builder as rb

    out = []
    add = lambda text, note: out.append((text, note))

    for name, unit, key, fn in PARAMS_14:
        add(name, 'Parameter name')
        th_key = rb._THRESHOLD_KEY.get(key, key)
        th = SOIL_SAATHI_FIELD_THRESHOLDS.get(th_key, {})
        lo, hi = th.get('min'), th.get('max')
        samples = [None]
        if lo is not None:
            samples.append(lo - abs(lo) - 1)
        if hi is not None:
            samples.append(hi + abs(hi) + 1)
        if lo is not None and hi is not None:
            samples.append((lo + hi) / 2)
        for v in samples:
            status, _css, _ideal, interp = fn(v)
            add(status, 'Parameter status')
            add(interp, f'Interpretation for {name}')
    for s in ('Low', 'Medium', 'High', 'N/A'):
        add(s, 'Low/Medium/High status')
    for lbl, *_ in rb.HM_PARAMS:
        add(lbl, 'Grid map title (page 3)')
    for s in ('GOOD', 'MODERATE', 'LOW'):
        add(s, 'Soil health score label')
    for s in ('Excellent', 'Good', 'Moderate'):
        add(s, 'Carbon health score label')
    for s in ('Highly Recommended', 'Recommended', 'Moderately Suitable',
              'Low Recommended', 'Lightly Recommended'):
        add(s, 'Crop suitability status')
    for cp in rb.CROP_PROFILES:
        add(cp[0], 'Crop name')
        add(cp[6], f'Crop note ({cp[0]})')
    for c in COMMON_CROPS:
        add(c, 'Crop name (farmer entry)')
    for p in AMENDMENT_PHRASES:
        add(p, 'Soil amendment table')
    for row in rb.ORGANIC_ADVISORY:
        name, typ, _color, method, dose, freq, shelf = row
        add(name, 'Organic advisory: product')
        add(typ, 'Organic advisory: type')
        add(method, f'Organic advisory: method ({name})')
        if re.search(r'[A-Za-z]{3,}', dose):
            add(dose, f'Organic advisory: dose ({name})')
        add(freq, 'Organic advisory: frequency')
        add(shelf, 'Organic advisory: shelf life')
    for z in AGRO_ZONES:
        add(z, 'Agro-climatic zone')
    return out



def live_catalog():
    """{key: (english, context)} for every builder phrase (AppConfig hook)."""
    cat = {k: v for k, v in FMT.items()}
    for en, note in dynamic_phrases():
        cat.setdefault(phrase_key(en), (en, note))
    return cat
