"""
agri_ai.crop_recommendation.rule_engine
-----------------------------------------
Ported from the AgroZone prototype's rule-based, explainable crop scorer.

5-gate scoring (100 pts total):
  pH               20 pts
  OC + EC          10 pts
  N, P, K, S       35 pts
  Micronutrients   20 pts
  Weather (temp)   15 pts

Ranking then enforces category diversity: the best-scoring crop from each
category is picked first, so the top 5 always span different crop groups
instead of one category monopolising all slots.
"""
import math
import re

GATE3_PARAMS = {"oc": 5.0, "ec": 5.0}
GATE4_PARAMS = {"n": 10.0, "p": 9.0, "k": 9.0, "s": 7.0}
GATE5_PARAMS = {
    "fe": 3.0, "mn": 3.0, "cu": 3.0, "zn": 3.0,
    "b": 2.0, "ca": 3.0, "mg": 3.0,
}
PH_WEIGHT = 20.0
WEATHER_WEIGHT = 15.0
MAX_SCORE = 100.0

PARAM_LABELS = {
    "oc": "Organic Carbon", "ec": "EC",
    "n": "Nitrogen", "p": "P₂O₅", "k": "Potassium", "s": "Sulphur",
    "fe": "Iron", "mn": "Manganese", "cu": "Copper", "zn": "Zinc",
    "b": "Boron", "ca": "Calcium", "mg": "Magnesium",
}
PARAM_UNITS = {
    "oc": "%", "ec": "dS/m",
    "n": "kg/ha", "p": "kg/ha", "k": "kg/ha", "s": "ppm",
    "fe": "ppm", "mn": "ppm", "cu": "ppm", "zn": "ppm",
    "b": "ppm", "ca": "meq/100g", "mg": "meq/100g",
}

CATEGORY_PRIORITY = [
    "Cereals & Millets", "Cash Crops", "Fruits", "Vegetables",
    "Pulses", "Oilseeds", "Spices", "Plantation Crops", "Flowers",
]


def _score_param(value, lo, hi) -> float:
    if value is None:
        return 0.75  # neutral — don't penalise missing inputs
    width = hi - lo
    if width <= 0:
        return 1.0 if value == lo else 0.5
    if lo <= value <= hi:
        return 1.0
    dist = (lo - value) if value < lo else (value - hi)
    return round(max(0.1, math.exp(-dist / max(width, 1.0))), 4)


def _status(value, lo, hi) -> str:
    if value is None: return "missing"
    if value < lo:    return "low"
    if value > hi:    return "high"
    return "ok"


def _deficiency_label(param, value, lo, hi):
    if value is None:
        return None
    name = PARAM_LABELS.get(param, param)
    unit = PARAM_UNITS.get(param, "")
    if value < lo:
        return f"{name} low ({round(value, 4)} {unit} < {round(lo, 4)} {unit})".strip()
    if value > hi:
        return f"{name} high ({round(value, 4)} {unit} > {round(hi, 4)} {unit})".strip()
    return None


def score_weather(temp_current, temp_range_str) -> dict:
    """Score current temperature against a crop's ideal range string, e.g. '20-35°C'."""
    match = re.search(r"([\d.]+)\s*[-–]\s*([\d.]+)", temp_range_str or "")

    if not match or temp_current is None:
        return {
            "score": round(WEATHER_WEIGHT * 0.5, 2), "max": WEATHER_WEIGHT,
            "pct": 50.0, "status": "missing", "ideal_range": temp_range_str or "N/A",
        }

    lo, hi = float(match.group(1)), float(match.group(2))
    width = hi - lo

    if lo <= temp_current <= hi:
        s, status = 1.0, "ok"
    else:
        dist = (lo - temp_current) if temp_current < lo else (temp_current - hi)
        s = max(0.0, 1.0 - dist / max(width, 1.0))
        status = "low" if temp_current < lo else "high"

    return {
        "score": round(s * WEATHER_WEIGHT, 2), "max": WEATHER_WEIGHT,
        "pct": round(s * 100, 1), "status": status, "ideal_range": f"{lo}–{hi}°C",
    }


def score_crop(crop: dict, soil: dict, temp_current=None) -> dict:
    """soil: dict with keys ph, oc, ec, n, p, k, s, fe, mn, cu, zn, b, ca, mg (values may be None)."""
    total = 0.0
    param_scores = {}
    deficiencies = []

    ph_s = _score_param(soil.get('ph'), crop['ph_lo'], crop['ph_hi'])
    total += ph_s * PH_WEIGHT

    for gate_params in (GATE3_PARAMS, GATE4_PARAMS, GATE5_PARAMS):
        for param, weight in gate_params.items():
            value = soil.get(param)
            lo, hi = crop[f'{param}_lo'], crop[f'{param}_hi']
            s = _score_param(value, lo, hi)
            pts = round(s * weight, 4)
            total += pts
            param_scores[param] = {
                "label": PARAM_LABELS.get(param, param),
                "score": round(pts, 2), "max": weight, "pct": round(s * 100, 1),
                "value": round(value, 4) if value is not None else None,
                "lo": round(lo, 4), "hi": round(hi, 4),
                "unit": PARAM_UNITS.get(param, ""), "status": _status(value, lo, hi),
            }
            defic = _deficiency_label(param, value, lo, hi)
            if defic:
                deficiencies.append(defic)

    weather_score = score_weather(temp_current, crop.get('temp_range'))
    total += weather_score['score']

    return {
        'crop_name':   crop['crop_name'],
        'category':    crop['category'],
        'zone_name':   crop['zone_name'],
        'notes':       crop['notes'],
        'is_notable':  crop['is_notable'],
        'temp_range':  crop['temp_range'],
        'sheet_order': crop['sheet_order'],
        'total_score': round(total, 2),
        'max_score':   MAX_SCORE,
        'score_pct':   round(total / MAX_SCORE * 100, 1),
        'nutrient_deficiencies': deficiencies,
        'param_scores': param_scores,
        'weather_score': weather_score,
    }


def rank_crops(crops: list, soil: dict, temp_current=None, top_n: int = 5) -> list:
    """Score every crop, then enforce category diversity: best crop per
    category first, then top_n sorted by score — guarantees variety."""
    all_scored = [score_crop(c, soil, temp_current) for c in crops]

    all_scored.sort(key=lambda r: (
        -r['weather_score'].get('pct', 50),
        -r['total_score'],
        -int(r['is_notable']),
        r['sheet_order'],
    ))

    seen_categories = {}
    for r in all_scored:
        cat = r['category']
        if cat not in seen_categories:
            seen_categories[cat] = r

    def cat_sort_key(item):
        cat, best = item
        priority = CATEGORY_PRIORITY.index(cat) if cat in CATEGORY_PRIORITY else 99
        return (-best['total_score'], -best['weather_score'].get('pct', 50), priority)

    sorted_categories = sorted(seen_categories.items(), key=cat_sort_key)
    top = [r for _, r in sorted_categories[:top_n]]

    for i, r in enumerate(top):
        r['rank'] = i + 1
    return top