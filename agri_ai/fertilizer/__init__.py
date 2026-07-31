"""
agri_ai.fertilizer
-------------------
Rule-based fertilizer recommendation engine (RDF Rule Book + state/crop
NPK datasets). No ML, no Django dependency here — pure math over static
reference tables, driven entirely by soil-parameter values the caller
already has (e.g. from a DeviseApis reading) plus a state/crop.

Usage:
    from agri_ai.fertilizer import recommend_fertilizer, get_states, get_crops_for_state

    result = recommend_fertilizer('Karnataka', 'Rice', {
        'ph': 6.8, 'ec': 0.3, 'organic_carbon': 0.6,
        'nitrogen': 240, 'phosphorus': 18, 'potassium': 120,
        'sulphur': 8, 'calcium': 1.2, 'magnesium': 0.8,
        'zinc': 0.5, 'iron': 4.0, 'manganese': 1.5,
        'copper': 0.15, 'boron': 0.4,
    })
"""
from .data_loader import load_rules, load_crop_dataset, load_fertilizer_dataset
from .engine import (
    PARAM_CONFIG, get_soil_status, parse_rdf_ratio, adjust_npk,
    convert_to_fertilizer, estimate_yield, match_rule_for_param,
)

__all__ = ["recommend_fertilizer", "get_states", "get_crops_for_state"]

_rules     = load_rules()
_crop_data = load_crop_dataset()
_fert_data = load_fertilizer_dataset()


def get_states():
    all_states = set(s for s in _crop_data.keys() if _crop_data[s])
    all_states.update(s for s in _fert_data.keys() if _fert_data[s])
    return sorted(all_states)


def get_crops_for_state(state):
    seen = set()
    crops = []
    for r in _crop_data.get(state, []):
        name = r['crop']
        if name and name not in seen:
            seen.add(name)
            crops.append(name)
    for r in _fert_data.get(state, []):
        name = r['crop']
        if name and name not in seen:
            seen.add(name)
            crops.append(name)
    return crops


def _find_record(records, name):
    nl = name.strip().lower()
    for rec in records:
        if rec['crop'].lower().strip() == nl:
            return rec
    base = nl.split('(')[0].strip()
    if base:
        for rec in records:
            rc_base = rec['crop'].lower().strip().split('(')[0].strip()
            if rc_base == base:
                return rec
    for rec in records:
        rc = rec['crop'].lower().strip()
        if len(rc) >= 5 and rc in nl:
            return rec
    return None


def _build_param_results(soil_values):
    results = []
    for key, _ in PARAM_CONFIG:
        value = soil_values.get(key, 0.0)
        short_status, full_status, label = get_soil_status(key, value)
        rule = match_rule_for_param(key, short_status, _rules)
        results.append({
            'key':      key,
            'label':    label,
            'value':    value,
            'status':   short_status + (' (' + full_status.split('(')[1] if '(' in full_status else ''),
            'practice': rule['practice'] if rule else '',
            'dose':     rule['dose'] if rule else '',
        })
    return results


def recommend_fertilizer(state, crop, soil_values):
    """
    state, crop: plain strings resolved by the caller (e.g. from Farmer/DeviseApis).
    soil_values: dict keyed by the 14 PARAM_CONFIG keys (ph, ec, organic_carbon,
                 nitrogen, phosphorus, potassium, sulphur, calcium, magnesium,
                 zinc, iron, manganese, copper, boron).

    Returns a dict of recommendation results, or {'error': <code>, ...} when
    state/crop can't be resolved against the reference datasets — the caller
    is expected to let the user pick from `states`/`crops` in that case.
    """
    if not state or not crop:
        return {'error': 'missing_state_or_crop', 'states': get_states()}

    if state not in get_states():
        return {'error': 'unknown_state', 'states': get_states()}

    crop_records = _crop_data.get(state, [])
    rdf_rec = _find_record(crop_records, crop)
    if not rdf_rec:
        return {'error': 'crop_not_found', 'states': get_states(), 'crops': get_crops_for_state(state)}

    param_results = _build_param_results(soil_values)

    n_rdf, p_rdf, k_rdf = parse_rdf_ratio(rdf_rec['rdf_ratio'])
    n_status = get_soil_status('nitrogen', soil_values.get('nitrogen', 0))[0]
    p_status = get_soil_status('phosphorus', soil_values.get('phosphorus', 0))[0]
    k_status = get_soil_status('potassium', soil_values.get('potassium', 0))[0]

    n_adj, p_adj, k_adj = adjust_npk(n_rdf, p_rdf, k_rdf, n_status, p_status, k_status)
    urea, dap, mop = convert_to_fertilizer(n_adj, p_adj, k_adj)
    normal_yield, rec_yield = estimate_yield(n_adj, n_rdf, p_adj, p_rdf, k_adj, k_rdf)

    default_found = _find_record(_fert_data.get(state, []), crop)
    current_urea  = default_found['urea'] if default_found else 0
    current_dap   = default_found['dap'] if default_found else 0
    current_mop   = default_found['mop'] if default_found else 0

    return {
        'state':         state,
        'crop':          crop,
        'param_results': param_results,
        'rdf_ratio':     rdf_rec['rdf_ratio'],
        'n_rdf':         n_rdf,
        'p_rdf':         p_rdf,
        'k_rdf':         k_rdf,
        'n_adj':         round(n_adj, 2),
        'p_adj':         round(p_adj, 2),
        'k_adj':         round(k_adj, 2),
        'urea':          urea,
        'dap':           dap,
        'mop':           mop,
        'current_urea':  current_urea,
        'current_dap':   current_dap,
        'current_mop':   current_mop,
        'normal_yield':  normal_yield,
        'rec_yield':     rec_yield,
    }