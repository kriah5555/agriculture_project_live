"""
agri_ai.crop_recommendation
------------------------------
Rule-based, explainable multi-crop recommender (ported from the AgroZone
prototype). Given a state + the soil readings we already collect (ph, ec,
oc, n, p, k, s, ca, mg, zn, fe, mn, cu, b) plus optionally current
temperature, returns the top-5 best-suited crops with a full score
breakdown per parameter, deficiency notes, and a "Crop Guide" (duration,
sowing season, water requirement, pests, fertilizers, harvest time).

No Django models/migrations — crop + crop-guide data are read straight
from the bundled Excel files (data_loader.py / crop_data_mapper.py),
same self-contained pattern as agri_ai.fertilizer.

Usage:
    from agri_ai.crop_recommendation import recommend_crops, get_states

    result = recommend_crops('Karnataka', {
        'ph': 6.8, 'ec': 0.4, 'oc': 0.6,
        'n': 220, 'p': 18, 'k': 160, 's': 12,
        'ca': 9.0, 'mg': 3.5, 'zn': 0.5, 'fe': 14, 'mn': 5, 'cu': 1.0, 'b': 0.4,
    }, temp_current=28.0)
"""
from .data_loader import get_states, get_crops_for_state
from .rule_engine import rank_crops, MAX_SCORE
from .crop_data_mapper import get_mapper

__all__ = ["recommend_crops", "get_states"]


def recommend_crops(state: str, soil_values: dict, temp_current=None, top_n: int = 5) -> dict:
    """
    Full pipeline: load crops for `state` -> score against `soil_values` ->
    enrich top_n with the Crop Guide.

    Returns:
        {
            'state': str,
            'crops_evaluated': int,
            'temp_current': float | None,
            'top_crops': [ {rank, crop_name, category, zone_name, notes,
                            is_notable, temp_range, total_score, max_score,
                            score_pct, nutrient_deficiencies, param_scores,
                            weather_score, additional_info}, ... ],
        }
        or {'error': 'unknown_state' | 'no_crops_for_state'}
    """
    if not state:
        return {'error': 'missing_state'}

    crops = get_crops_for_state(state)
    if not crops:
        return {'error': 'unknown_state' if state not in get_states() else 'no_crops_for_state', 'state': state}

    top_crops = rank_crops(crops, soil_values, temp_current=temp_current, top_n=top_n)

    mapper = get_mapper()
    for crop in top_crops:
        crop['additional_info'] = mapper.lookup(crop['crop_name'], state)

    return {
        'state': state,
        'crops_evaluated': len(crops),
        'temp_current': temp_current,
        'top_crops': top_crops,
    }