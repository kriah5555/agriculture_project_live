"""
Server-side needle geometry for the SoiLENZ report's analog SVG gauges.

The needle position used to be set by a <script> in soil_report.html after
page load. WeasyPrint (the PDF download) does not run JavaScript, so every
needle in the downloaded report stayed at its default straight-up (50%)
position regardless of the reading. Computing x2/y2 here makes the browser
view and the PDF identical.
"""
import math

from django import template
from django.utils.html import format_html

register = template.Library()

# Gauge scale (min, max) per parameter key — the same ranges the old
# client-side script used.
GAUGE_RANGES = {
    'ph': (0, 14), 'ec': (0, 4), 'n': (0, 560), 'p': (0, 112), 'k': (0, 1120),
    'organic_carbon': (0, 2), 'ca': (0, 30), 'mg': (0, 15), 's': (0, 60),
    'fe': (0, 30), 'mn': (0, 15), 'cu': (0, 3), 'zn': (0, 6), 'b': (0, 3),
}


def gauge_pct(key, value):
    """0-100 needle position for a parameter value (50 when unknown)."""
    rng = GAUGE_RANGES.get(key)
    try:
        val = float(value)
    except (TypeError, ValueError):
        return 50.0
    if not rng or math.isnan(val):
        return 50.0
    lo, hi = rng
    return max(0.0, min(100.0, (val - lo) / (hi - lo) * 100))


@register.simple_tag
def gauge_needle(pct, cx=50, cy=55, r=33):
    """Render the x2/y2 attributes of a gauge needle for a 0-100 position."""
    try:
        pct = max(0.0, min(100.0, float(pct)))
    except (TypeError, ValueError):
        pct = 50.0
    a = math.radians(180 + pct * 1.8)
    x2 = f'{cx + r * math.cos(a):.2f}'
    y2 = f'{cy + r * math.sin(a):.2f}'
    return format_html('x2="{}" y2="{}"', x2, y2)
