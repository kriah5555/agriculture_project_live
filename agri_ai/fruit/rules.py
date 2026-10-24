"""
agri_ai.fruit.rules
-------------------
Per-fruit business rules (shelf life, market, price) and the scan summary
maths. Ported from HarvestLenz `config/fruits/*.yaml`, `shelf_service`,
`market_service` and the summary part of `analysis_orchestrator`.

The summary helpers work from grade counts only, so a saved
DeviseApisFields row (good/better/reject counts) can be re-summarised
without the per-fruit list.
"""

# Grade classes, alphabetical (the order Keras `flow_from_directory` used in training).
GRADE_BETTER   = 'Better'
GRADE_GOOD     = 'Good'
GRADE_REJECT   = 'Reject'
GRADE_MISMATCH = 'Mismatch'

GRADE_COLORS = {
    GRADE_GOOD    : '#66BB6A',
    GRADE_BETTER  : '#FFB74D',
    GRADE_REJECT  : '#E57373',
    GRADE_MISMATCH: '#E53935',
}

# Same scoring HarvestLenz uses: Good is the top grade, Better the middle one.
SCORE_MAP           = {GRADE_GOOD: 100, GRADE_BETTER: 75, GRADE_REJECT: 30}
QUALITY_MULTIPLIERS = {GRADE_GOOD: 1.0, GRADE_BETTER: 0.75, GRADE_REJECT: 0.40}

_DEFAULT_SHELF  = {GRADE_GOOD: 5, GRADE_BETTER: 4, GRADE_REJECT: 1}
_DEFAULT_MARKET = {
    GRADE_GOOD  : {'market': 'Export',     'price_range': '₹100-₹150/kg'},
    GRADE_BETTER: {'market': 'Retail',     'price_range': '₹80-₹100/kg'},
    GRADE_REJECT: {'market': 'Processing', 'price_range': '₹10-₹25/kg'},
}

# Only fruits that have trained grading weights in models/weights/.
FRUIT_INFO = {
    'banana': {
        'name': 'Banana', 'scientific': 'Musa acuminata', 'base_price': 35.00,
        'shelf_life': {'Good': 7, 'Better': 5, 'Reject': 1},
        'market': {
            'Good'  : {'market': 'Premium Retail',      'price_range': '₹40-₹60/kg'},
            'Better': {'market': 'Supermarket',         'price_range': '₹30-₹40/kg'},
            'Reject': {'market': 'Processing Industry', 'price_range': '₹5-₹12/kg'},
        },
    },
    'grapes': {
        'name': 'Grapes', 'scientific': 'Vitis vinifera', 'base_price': 45.00,
        'shelf_life': {'Good': 15, 'Better': 10, 'Reject': 1},
        'market': {
            'Good'  : {'market': 'Export',       'price_range': '₹120-₹150/kg'},
            'Better': {'market': 'Retail',       'price_range': '₹90-₹110/kg'},
            'Reject': {'market': 'Winery/Juice', 'price_range': '₹20-₹35/kg'},
        },
    },
    'guava': {
        'name': 'Guava', 'scientific': 'Psidium guajava', 'base_price': 40.00,
        'shelf_life': {'Good': 7, 'Better': 5, 'Reject': 1},
        'market': {
            'Good'  : {'market': 'Premium Retail',      'price_range': '₹60-₹100/kg'},
            'Better': {'market': 'Supermarket',         'price_range': '₹40-₹60/kg'},
            'Reject': {'market': 'Processing Industry', 'price_range': '₹8-₹15/kg'},
        },
    },
    'mango': {
        'name': 'Mango', 'scientific': 'Mangifera indica', 'base_price': 52.50,
        'shelf_life': {'Good': 7, 'Better': 5, 'Reject': 1},
        'market': {
            'Good'  : {'market': 'Export',              'price_range': '₹150-₹200/kg'},
            'Better': {'market': 'Supermarket',         'price_range': '₹100-₹140/kg'},
            'Reject': {'market': 'Processing Industry', 'price_range': '₹15-₹30/kg'},
        },
    },
    'orange': {
        'name': 'Orange', 'scientific': 'Citrus sinensis', 'base_price': 40.00,
        'shelf_life': {'Good': 14, 'Better': 10, 'Reject': 1},
        'market': {
            'Good'  : {'market': 'Premium Retail',      'price_range': '₹80-₹120/kg'},
            'Better': {'market': 'Supermarket',         'price_range': '₹60-₹80/kg'},
            'Reject': {'market': 'Processing Industry', 'price_range': '₹10-₹20/kg'},
        },
    },
    'pineapple': {
        'name': 'Pineapple', 'scientific': 'Ananas comosus', 'base_price': 85.00,
        'shelf_life': {'Good': 12, 'Better': 8, 'Reject': 1},
        'market': {
            'Good'  : {'market': 'Export',     'price_range': '₹90-₹120/kg'},
            'Better': {'market': 'Retail',     'price_range': '₹70-₹90/kg'},
            'Reject': {'market': 'Processing', 'price_range': '₹15-₹25/kg'},
        },
    },
    'pomegranate': {
        'name': 'Pomegranate', 'scientific': 'Punica granatum', 'base_price': 40.00,
        'shelf_life': {'Good': 30, 'Better': 20, 'Reject': 3},
        'market': {
            'Good'  : {'market': 'Export',         'price_range': '₹180-₹220/kg'},
            'Better': {'market': 'Retail',         'price_range': '₹120-₹160/kg'},
            'Reject': {'market': 'Juice Industry', 'price_range': '₹20-₹45/kg'},
        },
    },
    'strawberry': {
        'name': 'Strawberry', 'scientific': 'Fragaria x ananassa', 'base_price': 25.00,
        'shelf_life': _DEFAULT_SHELF,
        'market': _DEFAULT_MARKET,
    },
}

SUPPORTED_FRUITS = sorted(FRUIT_INFO)


def fruit_display_name(fruit_type):
    info = FRUIT_INFO.get((fruit_type or '').lower())
    return info['name'] if info else (fruit_type or 'Unknown').capitalize()


def predict_shelf_life(fruit_type, grade, defect_score=0.0):
    """Shelf-life days for one fruit, shortened by its defect score."""
    rules     = FRUIT_INFO.get(fruit_type, {}).get('shelf_life', _DEFAULT_SHELF)
    base_days = int(rules.get(grade, rules.get(GRADE_GOOD, 3)))
    if defect_score > 0.0:
        return max(1, int(base_days * (1.0 - defect_score)))
    return base_days


def recommend_market(fruit_type, grade):
    """{'market': ..., 'price_range': ...} for one fruit."""
    rules = FRUIT_INFO.get(fruit_type, {}).get('market', _DEFAULT_MARKET)
    return rules.get(grade, rules[GRADE_GOOD])


def fruit_price(fruit_type, grade):
    base = FRUIT_INFO.get(fruit_type, {}).get('base_price', 40.0)
    return round(base * QUALITY_MULTIPLIERS.get(grade, 1.0), 2)


def overall_from_counts(fruit_type, good, better, reject, mismatch=False):
    """
    Overall grade, score, market, prices and recommendations from grade counts.
    `reject` includes mismatched fruits (as HarvestLenz counts them).
    """
    total = good + better + reject
    if mismatch:
        overall_grade, score = GRADE_MISMATCH, 0
    elif total == 0:
        overall_grade, score = GRADE_REJECT, 0
    else:
        score = round((good * SCORE_MAP[GRADE_GOOD] + better * SCORE_MAP[GRADE_BETTER]
                       + reject * SCORE_MAP[GRADE_REJECT]) / total)
        overall_grade = 'Premium' if score >= 90 else (GRADE_GOOD if score >= 70 else GRADE_REJECT)

    if mismatch:
        total_price = round(fruit_price(fruit_type, GRADE_GOOD) * good
                            + fruit_price(fruit_type, GRADE_BETTER) * better, 2)
    else:
        total_price = round(fruit_price(fruit_type, GRADE_GOOD) * good
                            + fruit_price(fruit_type, GRADE_BETTER) * better
                            + fruit_price(fruit_type, GRADE_REJECT) * reject, 2)

    if overall_grade in ('Premium', GRADE_GOOD):
        selling_price = round(total_price * 1.30, 2)
        profit        = round(selling_price - total_price, 2)
    else:
        selling_price = round(total_price * 0.20, 2)
        profit        = 0.0

    recommended_market = (
        'Export' if overall_grade == 'Premium' else
        'Supermarket' if overall_grade == GRADE_GOOD else
        'Processing Industry'
    )

    name = fruit_display_name(fruit_type)
    recommendations = []
    if mismatch:
        recommendations.append(
            f"Fruit Mismatch: Uploaded image does not appear to match '{name}'. "
            f"Please select the matching fruit or upload a valid image."
        )
    elif reject:
        recommendations.append('Discard rejected fruit(s) immediately to prevent cross-contamination.')
    if better:
        recommendations.append(f'Sell or consume {name} within 2 days or keep refrigerated.')
    if good:
        recommendations.append(f'Premium quality {name} detected. Suitable for export or high-end retail.')

    def pct(n):
        return round(n / total * 100, 1) if total else 0.0

    return {
        'overall_grade'          : overall_grade,
        'score'                  : score,
        'recommended_market'     : recommended_market,
        'total_price'            : total_price,
        'estimated_selling_price': selling_price,
        'profit_estimation'      : profit,
        'good_percentage'        : pct(good),
        'better_percentage'      : pct(better),
        'reject_percentage'      : pct(reject),
        'ai_recommendations'     : recommendations,
    }
