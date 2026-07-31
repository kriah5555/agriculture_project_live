import re

PARAM_CONFIG = [
    ('ph', {
        'label': 'pH', 'unit': '', 'param_type': 'range',
        'bands': [
            ('Strongly acidic (<4.5)', lambda v: v < 4.5),
            ('Moderately acidic (4.5\u20135.5)', lambda v: 4.5 <= v <= 5.5),
            ('Slightly acidic (5.5\u20136.5)', lambda v: 5.5 <= v <= 6.5),
            ('Neutral (6.5\u20137.5)', lambda v: 6.5 <= v <= 7.5),
            ('Alkaline (7.5\u20138.5)', lambda v: 7.5 <= v <= 8.5),
            ('Alkali (>8.5)', lambda v: v > 8.5),
        ]
    }),
    ('ec', {
        'label': 'EC (dS/m)', 'unit': 'dS/m', 'param_type': 'status',
        'bands': [
            ('Low (<0.8)', lambda v: v < 0.8),
            ('Medium (0.8\u20131.6)', lambda v: 0.8 <= v <= 1.6),
            ('High (1.6\u20132.5)', lambda v: 1.6 <= v <= 2.5),
            ('Very High (>2.5)', lambda v: v > 2.5),
        ]
    }),
    ('organic_carbon', {
        'label': 'Organic Carbon (%)', 'unit': '%', 'param_type': 'status',
        'bands': [
            ('Low (<0.5)', lambda v: v < 0.5),
            ('Medium (0.5\u20130.75)', lambda v: 0.5 <= v <= 0.75),
            ('High (>0.75)', lambda v: v > 0.75),
        ]
    }),
    ('nitrogen', {
        'label': 'Nitrogen (kg/ha)', 'unit': 'kg/ha', 'param_type': 'status',
        'bands': [
            ('Low (<280)', lambda v: v < 280),
            ('Medium (280\u2013560)', lambda v: 280 <= v <= 560),
            ('High (>560)', lambda v: v > 560),
        ]
    }),
    ('phosphorus', {
        'label': 'Phosphorus (kg P2O5/ha)', 'unit': 'kg/ha', 'param_type': 'status',
        'bands': [
            ('Low (<22.9)', lambda v: v < 22.9),
            ('Medium (22.9\u201356.3)', lambda v: 22.9 <= v <= 56.3),
            ('High (>56.3)', lambda v: v > 56.3),
        ]
    }),
    ('potassium', {
        'label': 'Potassium (kg K2O/ha)', 'unit': 'kg/ha', 'param_type': 'status',
        'bands': [
            ('Low (<144)', lambda v: v < 144),
            ('Medium (144\u2013336)', lambda v: 144 <= v <= 336),
            ('High (>336)', lambda v: v > 336),
        ]
    }),
    ('calcium', {
        'label': 'Calcium (cmol(+)/kg)', 'unit': 'cmol(+)/kg', 'param_type': 'status',
        'bands': [
            ('Low (<1.5)', lambda v: v < 1.5),
            ('Medium (1.5\u20135.0)', lambda v: 1.5 <= v <= 5.0),
            ('High (>5.0)', lambda v: v > 5.0),
        ]
    }),
    ('magnesium', {
        'label': 'Magnesium (cmol(+)/kg)', 'unit': 'cmol(+)/kg', 'param_type': 'status',
        'bands': [
            ('Low (<1.0)', lambda v: v < 1.0),
            ('Medium (1.0\u20133.0)', lambda v: 1.0 <= v <= 3.0),
            ('High (>3.0)', lambda v: v > 3.0),
        ]
    }),
    ('sulphur', {
        'label': 'Sulphur (ppm)', 'unit': 'ppm', 'param_type': 'status',
        'bands': [
            ('Low (<10)', lambda v: v < 10),
            ('Medium (10\u201320)', lambda v: 10 <= v <= 20),
            ('High (>20)', lambda v: v > 20),
        ]
    }),
    ('iron', {
        'label': 'Iron (ppm)', 'unit': 'ppm', 'param_type': 'deficiency',
        'bands': [
            ('Deficient (<4.5)', lambda v: v < 4.5),
            ('Marginal (4.5\u201310)', lambda v: 4.5 <= v <= 10),
            ('Sufficient (>10)', lambda v: v > 10),
        ]
    }),
    ('manganese', {
        'label': 'Manganese (ppm)', 'unit': 'ppm', 'param_type': 'deficiency',
        'bands': [
            ('Deficient (<2.0)', lambda v: v < 2.0),
            ('Marginal (2\u20134)', lambda v: 2.0 <= v <= 4.0),
            ('Sufficient (>4)', lambda v: v > 4.0),
        ]
    }),
    ('copper', {
        'label': 'Copper (ppm)', 'unit': 'ppm', 'param_type': 'deficiency',
        'bands': [
            ('Deficient (<0.2)', lambda v: v < 0.2),
            ('Marginal (0.2\u20130.4)', lambda v: 0.2 <= v <= 0.4),
            ('Sufficient (>0.4)', lambda v: v > 0.4),
        ]
    }),
    ('zinc', {
        'label': 'Zinc (ppm)', 'unit': 'ppm', 'param_type': 'deficiency',
        'bands': [
            ('Deficient (<0.6)', lambda v: v < 0.6),
            ('Marginal (0.6\u20131.2)', lambda v: 0.6 <= v <= 1.2),
            ('Sufficient (>1.2)', lambda v: v > 1.2),
        ]
    }),
    ('boron', {
        'label': 'Boron (ppm)', 'unit': 'ppm', 'param_type': 'status',
        'bands': [
            ('Low (<0.5)', lambda v: v < 0.5),
            ('Medium (0.5\u20131.0)', lambda v: 0.5 <= v <= 1.0),
            ('High (>1.0)', lambda v: v > 1.0),
        ]
    }),
]

PARAM_MAP = {k: v for k, v in PARAM_CONFIG}

def get_soil_status(param_key, value):
    config = PARAM_MAP.get(param_key)
    if not config:
        return 'Unknown', '', ''
    for status_name, test_fn in config['bands']:
        if test_fn(value):
            short = status_name.split('(')[0].strip().rstrip(' \u2013')
            if not short:
                short = status_name.split('(')[0].strip().rstrip(' \u2013')
            return short, status_name, config['label']
    return 'Unknown', '', config['label']

def get_npk_adjustment_factor(soil_status):
    s = soil_status.lower()
    if s in ('low', 'deficient'):
        return 1.25
    elif s in ('high', 'sufficient'):
        return 0.75
    else:
        return 1.0

def parse_rdf_ratio(ratio_str):
    parts = re.split(r'[:/]', str(ratio_str))
    nums = []
    for p in parts:
        try:
            nums.append(float(p.strip()))
        except ValueError:
            nums.append(0.0)
    while len(nums) < 3:
        nums.append(0.0)
    return nums[0], nums[1], nums[2]

def adjust_npk(n_rdf, p_rdf, k_rdf, n_status, p_status, k_status):
    n_adj = n_rdf * get_npk_adjustment_factor(n_status)
    p_adj = p_rdf * get_npk_adjustment_factor(p_status)
    k_adj = k_rdf * get_npk_adjustment_factor(k_status)
    return n_adj, p_adj, k_adj

def convert_to_fertilizer(n_kg, p_kg, k_kg):
    urea = n_kg / 0.46
    dap = (p_kg * 2.29) / 0.46
    mop = (k_kg * 1.20) / 0.60
    return round(urea, 2), round(dap, 2), round(mop, 2)

def estimate_yield(n_adj, n_rdf, p_adj, p_rdf, k_adj, k_rdf, base_yield=3500):
    n_ratio = n_adj / n_rdf if n_rdf else 1.0
    p_ratio = p_adj / p_rdf if p_rdf else 1.0
    k_ratio = k_adj / k_rdf if k_rdf else 1.0
    composite = (n_ratio + p_ratio + k_ratio) / 3.0
    rec_yield = base_yield * composite
    normal_yield = base_yield * 0.75
    return round(normal_yield, 0), round(rec_yield, 0)

def match_rule_for_param(param_key, soil_status_short, rules):
    param_rules = rules.get(param_key, [])
    for rule in param_rules:
        rstatus = rule['status'].lower()
        if soil_status_short.lower() in rstatus or rstatus in soil_status_short.lower():
            return rule
    return None
