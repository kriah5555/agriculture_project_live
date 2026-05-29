"""
SoiLENZ Soil Health Intelligence Report – PDF Generator (14-parameter edition)
Uses ReportLab canvas + Matplotlib for charts.
"""
import io
import os
import math
from datetime import date, datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors as rl_colors

PAGE_W, PAGE_H = A4   # 595.28 x 841.89 pt

# ─── Brand colours ────────────────────────────────────────────────────────────
_DK_GREEN  = (0.08, 0.27, 0.12)   # #154420
_MED_GREEN = (0.18, 0.49, 0.20)   # #2e7d32
_LT_GREEN  = (0.88, 0.96, 0.88)   # #e0f5e0
_ORANGE    = (0.90, 0.32, 0.00)
_RED       = (0.78, 0.16, 0.16)
_YELLOW    = (0.98, 0.66, 0.15)
_BLUE      = (0.08, 0.40, 0.75)
_LGRAY     = (0.95, 0.95, 0.95)
_GRAY      = (0.45, 0.45, 0.45)
_DGRAY     = (0.25, 0.25, 0.25)
_WHITE     = (1.0, 1.0, 1.0)
_BLACK     = (0.0, 0.0, 0.0)


# ─── Parameter info functions ────────────────────────────────────────────────

def _ph_info(v):
    if v is None: return 'N/A', _GRAY, '6.0-7.5', 'No data'
    if v > 7.5:   return 'Alkaline', _RED,    '6.0-7.5', 'Alkaline soil; limits nutrient availability'
    if v < 6.0:   return 'Acidic',   _ORANGE, '6.0-7.5', 'Acidic soil; apply lime to correct'
    return 'Normal', _MED_GREEN, '6.0-7.5', 'Optimal pH for most crops'

def _ec_info(v):
    if v is None: return 'N/A', _GRAY, '< 4.0', 'No data'
    if v >= 4.0:  return 'Very High', _RED,    '< 4.0', 'Severe salinity; strongly restricts growth'
    if v >= 2.0:  return 'High',      _ORANGE, '< 4.0', 'Salinity stress; sensitive crops affected'
    if v >= 1.0:  return 'Moderate',  _YELLOW, '< 4.0', 'Slight salinity; monitor tolerant crops'
    return 'Normal', _MED_GREEN, '< 4.0', 'Good; no salinity stress'

def _oc_info(v):
    if v is None:  return 'N/A', _GRAY, '> 0.75', 'No data'
    if v >= 0.75:  return 'Sufficient', _MED_GREEN, '> 0.75', 'Good organic matter level'
    if v >= 0.50:  return 'Medium',     _YELLOW,    '> 0.75', 'Marginal; add organic amendments'
    return 'Low', _RED, '> 0.75', 'Low organic matter; apply FYM/compost'

def _n_info(v):
    if v is None:  return 'N/A', _GRAY, '> 280', 'No data'
    if v >= 280:   return 'Sufficient', _MED_GREEN, '> 280 kg/ha', 'Adequate nitrogen supply'
    if v >= 140:   return 'Medium',     _YELLOW,    '> 280 kg/ha', 'Moderate; apply split-dose urea'
    return 'Low', _RED, '> 280 kg/ha', 'Deficient; apply urea in split doses'

def _p_info(v):
    if v is None: return 'N/A', _GRAY, '20-70', 'No data'
    if 20 <= v <= 70: return 'Medium', _YELLOW, '20-70 kg/ha', 'Marginal; apply basal P (DAP)'
    if v > 70:    return 'Sufficient', _MED_GREEN, '20-70 kg/ha', 'High phosphorus; no addition needed'
    return 'Low', _RED, '20-70 kg/ha', 'Deficient; apply DAP at basal dose'

def _k_info(v):
    if v is None: return 'N/A', _GRAY, '> 120', 'No data'
    if v >= 280:  return 'Sufficient', _MED_GREEN, '> 120 kg/ha', 'High potassium; sufficient for crop'
    if v >= 120:  return 'Medium',     _YELLOW,    '> 120 kg/ha', 'Adequate; monitor crop response'
    return 'Low', _RED, '> 120 kg/ha', 'Deficient; apply MOP at basal dose'

def _ca_info(v):
    if v is None: return 'N/A', _GRAY, '> 1.5', 'No data'
    if v >= 2.0:  return 'Sufficient', _MED_GREEN, '> 1.5 meq/100g', 'Calcium sufficient for crop'
    if v >= 1.5:  return 'Adequate',   _MED_GREEN, '> 1.5 meq/100g', 'Adequate; maintain with dolomite'
    if v >= 1.0:  return 'Low',        _ORANGE,    '> 1.5 meq/100g', 'Marginal; apply gypsum or dolomite'
    return 'Very Low', _RED, '> 1.5 meq/100g', 'Deficient; apply calcium carbonate'

def _mg_info(v):
    if v is None: return 'N/A', _GRAY, '> 1.0', 'No data'
    if v >= 1.0:  return 'Sufficient', _MED_GREEN, '> 1.0 meq/100g', 'Magnesium sufficient for crop'
    if v >= 0.5:  return 'Low',        _ORANGE,    '> 1.0 meq/100g', 'Marginal; apply magnesium sulphate'
    return 'Very Low', _RED, '> 1.0 meq/100g', 'Deficient; apply MgSO4 at 25 kg/acre'

def _s_info(v):
    if v is None: return 'N/A', _GRAY, '> 10', 'No data'
    if v >= 20:   return 'Sufficient', _MED_GREEN, '> 10 ppm', 'Adequate sulfur'
    if v >= 10:   return 'Medium',     _YELLOW,    '> 10 ppm', 'Borderline; apply gypsum if needed'
    return 'Low', _RED, '> 10 ppm', 'Deficient; apply gypsum or sulfate fertilizer'

def _fe_info(v):
    if v is None: return 'N/A', _GRAY, '> 4.5', 'No data'
    if v >= 4.5:  return 'Sufficient', _MED_GREEN, '> 4.5 ppm', 'Adequate iron content'
    return 'Low', _RED, '> 4.5 ppm', 'Deficient; apply ferrous sulphate'

def _mn_info(v):
    if v is None: return 'N/A', _GRAY, '> 2.0', 'No data'
    if v >= 2.0:  return 'Sufficient', _MED_GREEN, '> 2.0 ppm', 'Adequate manganese'
    return 'Low', _RED, '> 2.0 ppm', 'Deficient; apply MnSO4'

def _cu_info(v):
    if v is None: return 'N/A', _GRAY, '> 0.6', 'No data'
    if v >= 0.6:  return 'Sufficient', _MED_GREEN, '> 0.6 ppm', 'Adequate copper'
    return 'Low', _RED, '> 0.6 ppm', 'Deficient; apply copper sulphate'

def _zn_info(v):
    if v is None: return 'N/A', _GRAY, '> 0.6', 'No data'
    if v >= 0.6:  return 'Sufficient', _MED_GREEN, '> 0.6 ppm', 'Adequate zinc'
    if v >= 0.2:  return 'Medium',     _YELLOW,    '> 0.6 ppm', 'Marginal; apply zinc sulphate'
    return 'Low', _RED, '> 0.6 ppm', 'Deficient; apply zinc sulphate at 25 kg/ha'

def _b_info(v):
    if v is None: return 'N/A', _GRAY, '> 0.5', 'No data'
    if v >= 0.5:  return 'Sufficient', _MED_GREEN, '> 0.5 ppm', 'Adequate boron'
    return 'Low', _RED, '> 0.5 ppm', 'Deficient; apply borax at 1 kg/ha'


PARAMS_14 = [
    # (display_name, unit, key, info_fn)
    ('pH (0-14)',                    'pH',          'ph',             _ph_info),
    ('Electrical Conductivity (EC)', 'dS/m',        'ec',             _ec_info),
    ('Organic Carbon (OC)',          '%',           'organic_carbon', _oc_info),
    ('Nitrogen (N)',                 'kg/ha',       'n',              _n_info),
    ('Phosphorus (P)',               'kg/ha',       'p',              _p_info),
    ('Potassium (K)',                'kg/ha',       'k',              _k_info),
    ('Calcium (Ca)',                 'meq/100g',    'ca',             _ca_info),
    ('Magnesium (Mg)',               'meq/100g',    'mg',             _mg_info),
    ('Sulfur (S)',                   'ppm',         's',              _s_info),
    ('Iron (Fe)',                    'ppm',         'fe',             _fe_info),
    ('Manganese (Mn)',               'ppm',         'mn',             _mn_info),
    ('Copper (Cu)',                  'ppm',         'cu',             _cu_info),
    ('Zinc (Zn)',                    'ppm',         'zn',             _zn_info),
    ('Boron (B)',                    'ppm',         'b',              _b_info),
]


# ─── Nutrient categorisation ─────────────────────────────────────────────────

def _categorize_nutrients(preds):
    low, medium, high, sufficient, adequate = [], [], [], [], []
    checks = [
        ('N',  'n',  _n_info),  ('P',  'p',  _p_info),  ('K',  'k',  _k_info),
        ('S',  's',  _s_info),  ('Fe', 'fe', _fe_info),  ('Mn', 'mn', _mn_info),
        ('Cu', 'cu', _cu_info), ('Zn', 'zn', _zn_info),  ('B',  'b',  _b_info),
        ('Ca', 'ca', _ca_info), ('Mg', 'mg', _mg_info),
    ]
    for name, key, fn in checks:
        status, *_ = fn(preds.get(key))
        s = status.lower()
        if 'very low' in s or 'deficient' in s:
            low.append(name)
        elif 'low' in s or 'marginal' in s:
            low.append(name)
        elif 'medium' in s:
            medium.append(name)
        elif 'high' in s:
            high.append(name)
        elif 'adequate' in s:
            adequate.append(name)
        else:
            sufficient.append(name)
    return low, medium, high, sufficient, adequate


# ─── Soil health score ────────────────────────────────────────────────────────

def _soil_health_score(preds, env):
    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    ph  = preds.get('ph') or 7.0
    ec  = preds.get('ec') or 0.5
    n   = preds.get('n') or 100
    p   = preds.get('p') or 20
    k   = preds.get('k') or 100
    oc  = preds.get('organic_carbon') or 0.4
    ndv = env.get('ndvi', 0.5) or 0.5

    ph_s = 100 if 6.0 <= ph <= 7.5 else (70 if 5.5 <= ph <= 8.0 else 35)
    ec_s = 100 if ec < 0.4 else (75 if ec < 1.0 else (45 if ec < 2.0 else 15))
    n_s  = clamp((n / 280) * 100, 0, 100)
    p_s  = 100 if 20 <= p <= 70 else (clamp((p / 70) * 90, 0, 90) if p < 20 else 85)
    k_s  = clamp((k / 280) * 100, 0, 100)
    oc_s = clamp((oc / 1.5) * 100, 0, 100)
    nd_s = clamp(ndv * 100, 0, 100)

    score = (
        ph_s * 0.15 + ec_s * 0.10 +
        n_s  * 0.22 + p_s  * 0.13 +
        k_s  * 0.15 + oc_s * 0.15 +
        nd_s * 0.10
    )
    return round(score)


def _fertility_label(score):
    if score >= 75: return 'HIGH', _MED_GREEN
    if score >= 55: return 'MEDIUM', _YELLOW
    if score >= 35: return 'LOW', _ORANGE
    return 'VERY LOW', _RED


def _param_score_100(key, value):
    """Normalise one parameter to 0-100 for mini-gauge."""
    if value is None: return 50
    if key == 'ph':             return 100 if 6.0 <= value <= 7.5 else max(0, 100 - abs(value - 6.75) * 30)
    if key == 'ec':             return max(0, min(100, (1 - value / 4.0) * 100))
    if key == 'organic_carbon': return min(100, (value / 1.5) * 100)
    if key == 'n':              return min(100, (value / 560) * 100)
    if key == 'p':              return min(100, (value / 70) * 100)
    if key == 'k':              return min(100, (value / 500) * 100)
    return 50


# ─── Matplotlib helpers ───────────────────────────────────────────────────────

def _gauge_img(score, max_val=100, w_in=2.8, h_in=1.8):
    fig, ax = plt.subplots(figsize=(w_in, h_in), facecolor='none')
    ax.set_xlim(-1.4, 1.4); ax.set_ylim(-0.8, 1.4)
    ax.set_aspect('equal'); ax.axis('off')

    N = 360
    theta = np.linspace(np.pi, 0, N)
    for i in range(N - 1):
        frac = i / (N - 2)
        r = 1.0 - frac * 0.5
        g = frac * 0.8
        b = 0.1
        ax.plot([np.cos(theta[i]), np.cos(theta[i+1])],
                [np.sin(theta[i]), np.sin(theta[i+1])],
                color=(r, g, b), linewidth=10, solid_capstyle='round')

    ax.plot(np.cos(theta)*0.78, np.sin(theta)*0.78,
            color='#e0e0e0', linewidth=5, alpha=0.4)

    angle = np.pi - (score / max_val) * np.pi
    nx, ny = 0.72 * np.cos(angle), 0.72 * np.sin(angle)
    ax.annotate('', xy=(nx, ny), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', color='#212121', lw=2.5))
    ax.add_patch(plt.Circle((0, 0), 0.07, color='#333', zorder=6))

    ax.text(0, -0.25, str(score), ha='center', va='center',
            fontsize=22, fontweight='bold', color='#1a1a1a')
    ax.text(0, -0.52, '/100', ha='center', va='center',
            fontsize=10, color='#666')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=160, bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _mini_gauge_img(value_pct, w_in=1.2, h_in=0.85):
    """Mini semicircle gauge, value_pct in [0, 100]."""
    fig, ax = plt.subplots(figsize=(w_in, h_in), facecolor='none')
    ax.set_xlim(-1.3, 1.3); ax.set_ylim(-0.6, 1.2)
    ax.set_aspect('equal'); ax.axis('off')

    theta_bg = np.linspace(np.pi, 0, 180)
    ax.plot(np.cos(theta_bg), np.sin(theta_bg), color='#e0e0e0', linewidth=7)

    frac = max(0.0, min(1.0, value_pct / 100))
    theta_fg = np.linspace(np.pi, np.pi - frac * np.pi, max(2, int(frac * 180)))
    col = '#ef5350' if frac < 0.35 else ('#ffa726' if frac < 0.65 else '#43a047')
    if len(theta_fg) > 1:
        ax.plot(np.cos(theta_fg), np.sin(theta_fg), color=col, linewidth=7, solid_capstyle='round')

    angle = np.pi - frac * np.pi
    ax.annotate('', xy=(0.68 * np.cos(angle), 0.68 * np.sin(angle)),
                xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', color='#212121', lw=1.8))
    ax.add_patch(plt.Circle((0, 0), 0.05, color='#333', zorder=5))

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _heatmap_img(rows, cols, vmin, vmax, avg, cmap='RdYlGn', w_in=1.7, h_in=1.7, reverse=False):
    """Generate a grid heatmap seeded from avg with natural spread."""
    rng = np.random.default_rng(seed=int(abs(avg * 100)))
    spread = (vmax - vmin) * 0.35
    raw = rng.normal(loc=avg, scale=spread, size=(rows, cols))
    data = np.clip(raw, vmin, vmax)

    fig, ax = plt.subplots(figsize=(w_in, h_in), facecolor='white')
    cmap_use = cmap + '_r' if reverse else cmap
    im = ax.imshow(data, cmap=cmap_use, aspect='auto', vmin=vmin, vmax=vmax, interpolation='bicubic')
    for i in range(rows + 1):
        ax.axhline(i - 0.5, color='white', linewidth=1.0)
    for j in range(cols + 1):
        ax.axvline(j - 0.5, color='white', linewidth=1.0)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    plt.tight_layout(pad=0.1)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf


def _bar_chart_img(crops, scores, w_in=5.0, h_in=2.8):
    fig, ax = plt.subplots(figsize=(w_in, h_in), facecolor='white')
    colors_list = []
    for s in scores:
        if s >= 7:   colors_list.append('#43a047')
        elif s >= 5: colors_list.append('#ffa726')
        else:        colors_list.append('#ef5350')

    y = range(len(crops))
    bars = ax.barh(list(y), scores, color=colors_list, height=0.55, edgecolor='none')
    ax.set_xlim(0, 10)
    ax.set_yticks(list(y))
    ax.set_yticklabels(crops, fontsize=9)
    ax.set_xlabel('Score (0-10)', fontsize=8)
    ax.tick_params(axis='x', labelsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.invert_yaxis()
    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                f'{score:.1f}', va='center', fontsize=8, color='#333')
    plt.tight_layout(pad=0.3)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf


def _carbon_gauge_img(score, w_in=2.2, h_in=1.5):
    return _gauge_img(score, 100, w_in, h_in)


# ─── Canvas helpers ───────────────────────────────────────────────────────────

def _set_rgb(c, rgb):
    c.setFillColorRGB(*rgb)


def _draw_page_header(c, page_num):
    """Dark-green header band + page number circle."""
    c.saveState()
    _set_rgb(c, _DK_GREEN)
    c.rect(0, PAGE_H - 48, PAGE_W, 48, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Oblique', 9)
    c.drawString(20, PAGE_H - 30, 'ARKASHINE INNOVATIONS  |  SoiLENZ Advisory Report')

    cx, cy, r = PAGE_W - 26, 26, 14
    _set_rgb(c, _DK_GREEN)
    c.circle(cx, cy, r, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(cx, cy - 4, str(page_num))
    c.restoreState()


def _draw_rounded_card(c, x, y, w, h, radius=8):
    p = c.beginPath()
    p.moveTo(x + radius, y)
    p.lineTo(x + w - radius, y)
    p.arcTo(x + w - 2*radius, y, x + w, y + 2*radius, -90, 90)
    p.lineTo(x + w, y + h - radius)
    p.arcTo(x + w - 2*radius, y + h - 2*radius, x + w, y + h, 0, 90)
    p.lineTo(x + radius, y + h)
    p.arcTo(x, y + h - 2*radius, x + 2*radius, y + h, 90, 90)
    p.lineTo(x, y + radius)
    p.arcTo(x, y, x + 2*radius, y + 2*radius, 180, 90)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def _embed_img(c, buf, x, y, w, h):
    buf.seek(0)
    ir = ImageReader(buf)
    c.drawImage(ir, x, y, width=w, height=h, mask='auto')


def _draw_status_badge(c, text, rgb, x, y, w=52, h=14):
    c.saveState()
    r, g, b = rgb
    c.setFillColorRGB(r * 0.18 + 0.82, g * 0.18 + 0.82, b * 0.18 + 0.82)
    _draw_rounded_card(c, x, y, w, h, radius=4)
    c.setFillColorRGB(*rgb)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(x + w/2, y + 4, str(text))
    c.restoreState()


def _draw_farmer_avatar(c, cx, cy, r):
    """Draw a simple head+body farmer icon in light grey."""
    c.saveState()
    c.setFillColorRGB(0.75, 0.75, 0.75)
    # Head (circle)
    c.circle(cx, cy + r * 0.6, r * 0.55, fill=1, stroke=0)
    # Body (rectangle)
    bw = r * 1.0
    bh = r * 0.9
    c.roundRect(cx - bw/2, cy - r * 0.55, bw, bh, 4, fill=1, stroke=0)
    c.restoreState()


# ─── Page 1: Cover with full redesign ────────────────────────────────────────

def _page1(c, preds, env, fertility, meta):
    _draw_page_header(c, 1)

    # Green title band below header
    c.saveState()
    _set_rgb(c, _DK_GREEN)
    c.rect(0, PAGE_H - 80, PAGE_W, 32, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(20, PAGE_H - 66, 'SOIL HEALTH / INTELLIGENCE REPORT')
    c.setFont('Helvetica', 7.5)
    c.drawRightString(PAGE_W - 20, PAGE_H - 60, 'Powered by SoiLENZ')
    c.drawRightString(PAGE_W - 20, PAGE_H - 70, 'Advanced Soil Intelligence from Arkashine Labs')
    c.restoreState()

    # ── Farmer Info Box (left half, top) ──────────────────────────────────────
    fi_x, fi_y = 14, PAGE_H - 138
    fi_w, fi_h = (PAGE_W - 28) / 2 - 4, 54
    c.saveState()
    _set_rgb(c, _LGRAY)
    _draw_rounded_card(c, fi_x, fi_y, fi_w, fi_h, radius=6)
    # Header strip
    _set_rgb(c, _DK_GREEN)
    c.roundRect(fi_x, fi_y + fi_h - 16, fi_w, 16, 4, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(fi_x + 6, fi_y + fi_h - 11, 'FARMER INFORMATION')
    # Content
    _set_rgb(c, _DGRAY)
    c.setFont('Helvetica', 7)
    farmer_name   = str(meta.get('farmer_name', '') or '')
    farmer_mobile = str(meta.get('farmer_mobile', '') or '')
    lat_val = env.get('lat', 0.0) or 0.0
    lon_val = env.get('lon', 0.0) or 0.0
    crop_val = str(meta.get('crop', '') or '')
    c.drawString(fi_x + 6, fi_y + fi_h - 28, f'Name : {farmer_name}')
    c.drawString(fi_x + 6, fi_y + fi_h - 38, f'Mobile : {farmer_mobile}')
    c.drawString(fi_x + 6, fi_y + fi_h - 48, f'Crop : {crop_val}')

    # Farmer avatar / image (top-right of box)
    img_x = fi_x + fi_w - 42
    img_y = fi_y + fi_h - 48
    farmer_img_path = meta.get('farmer_image_path', '')
    if farmer_img_path and os.path.isfile(str(farmer_img_path)):
        try:
            ir = ImageReader(str(farmer_img_path))
            c.drawImage(ir, img_x, img_y, width=36, height=36, mask='auto')
        except Exception:
            _draw_farmer_avatar(c, img_x + 18, img_y + 18, 18)
    else:
        _draw_farmer_avatar(c, img_x + 18, img_y + 18, 18)
    c.restoreState()

    # ── Report Details Box (right half, top) ──────────────────────────────────
    rd_x = fi_x + fi_w + 8
    rd_y = fi_y
    rd_w = fi_w
    rd_h = fi_h
    c.saveState()
    _set_rgb(c, _LGRAY)
    _draw_rounded_card(c, rd_x, rd_y, rd_w, rd_h, radius=6)
    _set_rgb(c, _DK_GREEN)
    c.roundRect(rd_x, rd_y + rd_h - 16, rd_w, 16, 4, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(rd_x + 6, rd_y + rd_h - 11, 'REPORT DETAILS')
    _set_rgb(c, _DGRAY)
    analysis_date = str(meta.get('analysis_date', '') or date.today().strftime('%d %b %Y'))
    lab_name      = str(meta.get('lab_name', 'Arkashine Labs') or 'Arkashine Labs')
    report_time   = str(meta.get('report_time', '') or '')
    # Small square icons + text
    icon_y_positions = [rd_y + rd_h - 28, rd_y + rd_h - 38, rd_y + rd_h - 48]
    icon_labels = [
        (f'Date of Analysis : {analysis_date}',),
        (f'Lab Name : {lab_name}',),
        (f'Report Time : {report_time}',),
    ]
    for iy, (label_text,) in zip(icon_y_positions, icon_labels):
        _set_rgb(c, _MED_GREEN)
        c.rect(rd_x + 6, iy - 1, 4, 4, fill=1, stroke=0)
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica', 7)
        c.drawString(rd_x + 14, iy, label_text)
    c.restoreState()

    # ── Main body area ────────────────────────────────────────────────────────
    body_top = fi_y - 6
    body_bot = 232
    # heights of main body
    left_x  = 14
    left_w  = 130
    mid_x   = left_x + left_w + 4
    mid_w   = 170
    right_x = mid_x + mid_w + 4
    right_w = PAGE_W - right_x - 14

    # ── LEFT COLUMN: Field info icons ─────────────────────────────────────────
    left_items = [
        ('Location',           f"{lat_val:.4f} / {lon_val:.4f}"),
        ('Field Area',         str(meta.get('field_area') or '-')),
        ('Crop (Current)',     crop_val),
        ('Agro Climatic Zone', str(meta.get('agro_zone') or '-')),
        ('Elevation',          '-'),
        ('Rainfall',           f"{env.get('rainfall_mm', '-')} mm" if env.get('rainfall_mm') else '-'),
        ('Temperature',        f"{env.get('temperature_c', '-')} C" if env.get('temperature_c') else '-'),
        ('NDVI',               str(env.get('ndvi', '-'))),
    ]
    item_y = body_top - 4
    item_spacing = 26
    c.saveState()
    for label, value in left_items:
        if item_y < body_bot: break
        # green square icon
        _set_rgb(c, _MED_GREEN)
        c.rect(left_x, item_y - 2, 8, 8, fill=1, stroke=0)
        _set_rgb(c, _GRAY)
        c.setFont('Helvetica', 7)
        c.drawString(left_x + 12, item_y + 2, label)
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(left_x + 12, item_y - 9, str(value))
        item_y -= item_spacing
    c.restoreState()

    # ── CENTER: Soil oval illustration ────────────────────────────────────────
    cx_mid = mid_x + mid_w / 2
    ov_cy  = (body_top + body_bot) / 2
    ov_rw  = mid_w / 2 - 6
    ov_rh  = (body_top - body_bot) / 2 - 10

    c.saveState()
    # Upper half (green sky)
    c.setFillColorRGB(0.75, 0.93, 0.75)
    c.ellipse(cx_mid - ov_rw, ov_cy - ov_rh, cx_mid + ov_rw, ov_cy + ov_rh, fill=1, stroke=0)
    # Lower half (soil brown)
    c.setFillColorRGB(0.48, 0.30, 0.10)
    c.ellipse(cx_mid - ov_rw, ov_cy - ov_rh, cx_mid + ov_rw, ov_cy, fill=1, stroke=0)
    # Plant stem
    c.setStrokeColorRGB(*_MED_GREEN)
    c.setLineWidth(1.5)
    stem_bot = ov_cy
    stem_top = ov_cy + ov_rh * 0.65
    c.line(cx_mid, stem_bot, cx_mid, stem_top)
    # Branch lines
    c.setLineWidth(1.0)
    mid_y = (stem_bot + stem_top) / 2
    c.line(cx_mid, mid_y, cx_mid - 14, mid_y + 10)
    c.line(cx_mid, mid_y + 12, cx_mid + 14, mid_y + 22)
    # Leaves (small ellipses)
    c.setFillColorRGB(*_MED_GREEN)
    c.ellipse(cx_mid - 22, mid_y + 5, cx_mid - 6, mid_y + 18, fill=1, stroke=0)
    c.ellipse(cx_mid + 6, mid_y + 18, cx_mid + 22, mid_y + 30, fill=1, stroke=0)
    c.ellipse(cx_mid - 8, stem_top - 4, cx_mid + 8, stem_top + 8, fill=1, stroke=0)
    c.restoreState()

    # Fertility badge at bottom of oval
    score   = _soil_health_score(preds, env)
    f_label, f_color = _fertility_label(score)
    badge_h = 30
    badge_w = ov_rw * 2 - 4
    badge_x = cx_mid - badge_w / 2
    badge_y = ov_cy - ov_rh + 2

    c.saveState()
    c.setFillColorRGB(0.10, 0.10, 0.10)
    _draw_rounded_card(c, badge_x, badge_y, badge_w, badge_h, radius=6)
    c.setFillColorRGB(*_LT_GREEN)
    _draw_rounded_card(c, badge_x + 1, badge_y + 1, badge_w - 2, badge_h - 2, radius=5)
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 6.5)
    c.drawCentredString(cx_mid, badge_y + badge_h - 10, 'OVERALL SOIL FERTILITY')
    c.setFillColorRGB(*f_color)
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(cx_mid, badge_y + 6, f_label)
    c.restoreState()

    # ── RIGHT COLUMN: Score + Indicators + OC ─────────────────────────────────
    # 1. Soil Health Score card
    sc_h = 110
    sc_y = body_top - sc_h
    c.saveState()
    c.setFillColorRGB(*_WHITE)
    _draw_rounded_card(c, right_x, sc_y, right_w, sc_h, radius=7)
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.7)
    c.roundRect(right_x, sc_y, right_w, sc_h, 7, fill=0, stroke=1)
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(right_x + right_w/2, sc_y + sc_h - 11, 'SOIL HEALTH SCORE')
    gauge_buf = _gauge_img(score)
    g_w = min(right_w - 10, 120)
    g_h = 76
    _embed_img(c, gauge_buf, right_x + (right_w - g_w)/2, sc_y + 16, g_w, g_h)
    s_label = ('EXCELLENT' if score >= 80 else 'GOOD' if score >= 65
               else 'MODERATE' if score >= 50 else 'LOW')
    s_color = (_MED_GREEN if score >= 65 else _YELLOW if score >= 50 else _ORANGE)
    c.setFillColorRGB(*s_color)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawCentredString(right_x + right_w/2, sc_y + 6, s_label)
    c.restoreState()

    # 2. Soil Health Indicators card
    ind_h = 110
    ind_y = sc_y - ind_h - 4
    c.saveState()
    c.setFillColorRGB(*_WHITE)
    _draw_rounded_card(c, right_x, ind_y, right_w, ind_h, radius=7)
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.7)
    c.roundRect(right_x, ind_y, right_w, ind_h, 7, fill=0, stroke=1)
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(right_x + right_w/2, ind_y + ind_h - 11, 'SOIL HEALTH INDICATORS')

    # 5 indicators: pH, EC, N, P, K in a 3+2 layout
    ind_params = [
        ('pH',  'ph',             preds.get('ph'),             _ph_info),
        ('EC',  'ec',             preds.get('ec'),             _ec_info),
        ('N',   'n',              preds.get('n'),              _n_info),
        ('P',   'p',              preds.get('p'),              _p_info),
        ('K',   'k',              preds.get('k'),              _k_info),
    ]
    col_count = 3
    cell_w_i = (right_w - 8) / col_count
    row0_y = ind_y + ind_h - 26
    row1_y = row0_y - 42
    for idx, (lbl, key, val, info_fn) in enumerate(ind_params):
        if idx < 3:
            ix = right_x + 4 + idx * cell_w_i
            iy = row0_y
        else:
            offset = idx - 3
            ix = right_x + 4 + (right_w - 8) / 4 + offset * cell_w_i
            iy = row1_y
        status_txt, status_rgb, _, _ = info_fn(val)
        val_str = f'{val:.2f}' if val is not None else 'N/A'
        c.setFillColorRGB(*status_rgb)
        c.setFont('Helvetica-Bold', 10)
        c.drawCentredString(ix + cell_w_i/2, iy - 14, val_str)
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(ix + cell_w_i/2, iy - 2, lbl)
        c.setFillColorRGB(*status_rgb)
        c.setFont('Helvetica', 6.5)
        c.drawCentredString(ix + cell_w_i/2, iy - 24, status_txt)
    c.restoreState()

    # 3. Organic Carbon mini section
    oc_card_h = 56
    oc_card_y = ind_y - oc_card_h - 4
    oc_val = preds.get('organic_carbon')
    oc_pct = _param_score_100('organic_carbon', oc_val)
    oc_status, oc_color, _, _ = _oc_info(oc_val)
    c.saveState()
    c.setFillColorRGB(*_WHITE)
    _draw_rounded_card(c, right_x, oc_card_y, right_w, oc_card_h, radius=7)
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.7)
    c.roundRect(right_x, oc_card_y, right_w, oc_card_h, 7, fill=0, stroke=1)
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(right_x + right_w/2, oc_card_y + oc_card_h - 10, 'ORGANIC CARBON (OC)')
    mg_buf = _mini_gauge_img(oc_pct, w_in=1.4, h_in=0.9)
    mg_w, mg_h = 50, 34
    _embed_img(c, mg_buf, right_x + (right_w - mg_w)/2, oc_card_y + 14, mg_w, mg_h)
    oc_disp = f'{oc_val:.2f} %' if oc_val is not None else 'N/A'
    c.setFillColorRGB(*oc_color)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(right_x + right_w/2, oc_card_y + 6, f'{oc_disp}  ({oc_status})')
    c.restoreState()

    # ── pH / EC big text row ──────────────────────────────────────────────────
    ph_ec_y = 228
    ph_val = preds.get('ph')
    ec_val = preds.get('ec')
    ph_status, ph_color, _, _ = _ph_info(ph_val)
    ec_status, ec_color, _, _ = _ec_info(ec_val)
    ph_disp = f'{ph_val:.2f}' if ph_val is not None else 'N/A'
    ec_disp = f'{ec_val:.4f}' if ec_val is not None else 'N/A'

    c.saveState()
    c.setStrokeColorRGB(*_MED_GREEN)
    c.setLineWidth(0.8)
    c.line(14, ph_ec_y + 14, PAGE_W - 14, ph_ec_y + 14)
    c.line(14, ph_ec_y - 2, PAGE_W - 14, ph_ec_y - 2)
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(20, ph_ec_y + 5, f'pH (0-14) : {ph_disp}  ({ph_status})')
    # Divider
    c.setStrokeColorRGB(*_GRAY)
    c.setLineWidth(0.5)
    c.line(PAGE_W/2, ph_ec_y - 1, PAGE_W/2, ph_ec_y + 13)
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(PAGE_W/2 + 8, ph_ec_y + 5, f'EC (0.1-30 dS/m) : {ec_disp}  ({ec_status})')
    c.restoreState()

    # ── RECOMMENDATION box (left) ─────────────────────────────────────────────
    rec_x = 14
    rec_y = 42
    rec_w = (PAGE_W - 28) / 2 - 4
    rec_h = ph_ec_y - rec_y - 6
    oc  = preds.get('organic_carbon') or 0.0
    n   = preds.get('n') or 0.0
    p   = preds.get('p') or 0.0
    k   = preds.get('k') or 0.0

    bullets = []
    if oc < 0.5:
        bullets.append('Soil fertility is medium. Improve organic matter and address nutrient deficiencies.')
    if n < 280:
        bullets.append('Nitrogen is low - apply urea as recommended.')
    p_status, _, _, _ = _p_info(p)
    if 'Low' in p_status:
        bullets.append('Phosphorus is low - apply DAP at basal dose.')
    elif 'Medium' in p_status:
        bullets.append('Phosphorus is medium - apply basal P (DAP).')
    k_status, _, _, _ = _k_info(k)
    if 'Low' in k_status:
        bullets.append('Potassium is low - apply MOP at basal dose.')
    elif 'Sufficient' in k_status:
        bullets.append('Potassium is sufficient - no potash needed.')
    bullets.append('Use quality FYM/Compost and green manuring to improve soil health.')
    bullets.append('Balanced fertilisation will improve yield and soil health.')
    ai_crop = str(meta.get('ai_crop', '') or '')
    if ai_crop:
        bullets.append(f'AI Recommendation: {ai_crop} crop is best suited.')

    c.saveState()
    _set_rgb(c, _LGRAY)
    _draw_rounded_card(c, rec_x, rec_y, rec_w, rec_h, radius=6)
    _set_rgb(c, _DK_GREEN)
    c.roundRect(rec_x, rec_y + rec_h - 16, rec_w, 16, 4, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(rec_x + 6, rec_y + rec_h - 11, 'RECOMMENDATION')
    bullet_y = rec_y + rec_h - 28
    for bullet in bullets[:7]:
        if bullet_y < rec_y + 4: break
        _set_rgb(c, _MED_GREEN)
        c.circle(rec_x + 10, bullet_y + 3, 2.5, fill=1, stroke=0)
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica', 6.5)
        # wrap text
        max_chars = 52
        if len(bullet) > max_chars:
            line1 = bullet[:max_chars]
            line2 = bullet[max_chars:max_chars + max_chars]
            c.drawString(rec_x + 16, bullet_y, line1)
            bullet_y -= 9
            if bullet_y > rec_y + 4:
                c.drawString(rec_x + 16, bullet_y, line2)
                bullet_y -= 9
        else:
            c.drawString(rec_x + 16, bullet_y, bullet)
            bullet_y -= 13
    c.restoreState()

    # ── KEY NUTRIENT CONCERNS box (right of recommendation) ───────────────────
    knc_x = rec_x + rec_w + 8
    knc_y = rec_y
    knc_w = PAGE_W - knc_x - 14
    knc_h = rec_h
    low_n, med_n, high_n, suff_n, adeq_n = _categorize_nutrients(preds)

    c.saveState()
    _set_rgb(c, _LGRAY)
    _draw_rounded_card(c, knc_x, knc_y, knc_w, knc_h, radius=6)
    _set_rgb(c, _DK_GREEN)
    c.roundRect(knc_x, knc_y + knc_h - 16, knc_w, 16, 4, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(knc_x + 6, knc_y + knc_h - 11, 'KEY NUTRIENT CONCERNS')

    knc_rows = []
    if low_n:   knc_rows.append((_RED,      'Low',       ', '.join(low_n)))
    if med_n:   knc_rows.append((_ORANGE,   'Medium',    ', '.join(med_n)))
    if high_n:  knc_rows.append((_BLUE,     'High',      ', '.join(high_n)))
    if suff_n:  knc_rows.append((_MED_GREEN,'Sufficient',', '.join(suff_n)))
    if adeq_n:  knc_rows.append((_GRAY,     'Adequate',  ', '.join(adeq_n)))

    kr_y = knc_y + knc_h - 28
    for dot_color, label, nutrients in knc_rows:
        if kr_y < knc_y + 4: break
        c.setFillColorRGB(*dot_color)
        c.circle(knc_x + 10, kr_y + 3, 3, fill=1, stroke=0)
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(knc_x + 17, kr_y + 1, f'{label} :')
        c.setFont('Helvetica', 6.5)
        nut_str = nutrients[:48]
        c.drawString(knc_x + 17 + 34, kr_y + 1, nut_str)
        kr_y -= 14
    c.restoreState()

    # ── GREEN FOOTER ──────────────────────────────────────────────────────────
    c.saveState()
    _set_rgb(c, _DK_GREEN)
    c.rect(0, 0, PAGE_W, 30, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(PAGE_W/2, 10, 'Healthy Soil. Higher Yield. Sustainable Future.')
    c.restoreState()


# ─── Page 2: 14-parameter detailed table ─────────────────────────────────────

def _page2(c, preds, meta):
    _draw_page_header(c, 2)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'ARKASHINE SOILENZ RESULTS -')
    c.drawString(20, TOP - 18, 'DETAILED 14 PARAMETER TEST')
    c.setFont('Helvetica', 9)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP - 34, 'Powered by')
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(20, TOP - 48, 'SoiLENZ')
    c.setFont('Helvetica', 7.5)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP - 60, 'Advanced Soil Intelligence from Arkashine Labs')

    # Info box right
    bx, by, bw, bh = 330, TOP - 72, 240, 78
    c.setFillColorRGB(*_DK_GREEN)
    _draw_rounded_card(c, bx, by, bw, bh, radius=7)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(bx + 10, by + bh - 14, 'SOILENZ MEANS PRECISION')
    bullets = [
        'Scientific 14-parameter soil test',
        'Lab-grade accuracy in your field in 60 sec',
        'Smart recommendations for higher yield',
        'Enables data-driven decision farming',
    ]
    for i, b in enumerate(bullets):
        c.setFont('Helvetica', 7.5)
        c.drawString(bx + 14, by + bh - 28 - i * 13, f'*  {b}')

    analysis_date = str(meta.get('analysis_date', '') or date.today().strftime('%d %b %Y'))

    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(20, TOP - 86, 'DETAILED 14 PARAMETER RESULTS')
    c.setFont('Helvetica', 8)
    c.drawRightString(PAGE_W - 20, TOP - 86, f'Analysis Date: {analysis_date}')

    # Table columns
    lm = 20
    total_w = PAGE_W - 40
    widths = [18, 110, 50, 38, 70, 65, total_w - 18 - 110 - 50 - 38 - 70 - 65]
    xs = [lm]
    for ww in widths[:-1]:
        xs.append(xs[-1] + ww)

    row_h = 16
    hy    = TOP - 104
    headers = ['#', 'Parameter', 'Value', 'Unit', 'Status', 'Ideal Range', 'Interpretation']

    # Header row
    c.setFillColorRGB(*_DK_GREEN)
    c.rect(lm, hy, total_w, row_h, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    for hdr, x in zip(headers, xs):
        c.drawString(x + 3, hy + 5, hdr)

    row_y = hy - row_h
    for idx, (name, unit, key, info_fn) in enumerate(PARAMS_14):
        val = preds.get(key)
        status_txt, status_rgb, ideal, interp = info_fn(val)
        val_txt = f'{val:.3f}' if val is not None else 'N/A'

        fill = _LGRAY if idx % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(lm, row_y, total_w, row_h, fill=1, stroke=0)

        row_data = [str(idx + 1), name, val_txt, unit, '', ideal, interp]
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica', 7.5)
        for i, (cell, x) in enumerate(zip(row_data, xs)):
            if i == 2:
                c.setFillColorRGB(*status_rgb)
                c.setFont('Helvetica-Bold', 7.5)
                c.drawString(x + 3, row_y + 5, cell)
                c.setFont('Helvetica', 7.5)
                c.setFillColorRGB(*_DGRAY)
            elif i == 4:
                _draw_status_badge(c, status_txt, status_rgb, x + 2, row_y + 2, w=62, h=13)
            else:
                c.setFillColorRGB(*_DGRAY)
                c.setFont('Helvetica', 7)
                if i == 6:
                    txt = interp[:42] if len(interp) > 42 else interp
                    c.drawString(x + 2, row_y + 5, txt)
                else:
                    c.drawString(x + 3, row_y + 5, cell)

        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.4)
        c.line(lm, row_y, lm + total_w, row_y)
        row_y -= row_h

    # Extra static rows: Urea and DAP
    extra_rows = [
        (15, 'Urea (Recommended)',  '-', 'kg/ha', 'As per crop', 'Apply as per crop requirement'),
        (16, 'DAP (Recommended)',   '-', 'kg/ha', 'As per crop', 'Apply as per crop requirement'),
    ]
    for idx_e, (num, name_e, val_e, unit_e, status_e, interp_e) in enumerate(extra_rows):
        fill = _LGRAY if idx_e % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(lm, row_y, total_w, row_h, fill=1, stroke=0)
        row_data_e = [str(num), name_e, val_e, unit_e, status_e, '-', interp_e]
        c.setFont('Helvetica', 7)
        c.setFillColorRGB(*_DGRAY)
        for i, (cell, x) in enumerate(zip(row_data_e, xs)):
            c.drawString(x + 3, row_y + 5, cell[:18] if len(str(cell)) > 18 else str(cell))
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.4)
        c.line(lm, row_y, lm + total_w, row_y)
        row_y -= row_h

    # Footer note
    c.setFillColorRGB(*_GRAY)
    c.setFont('Helvetica-Oblique', 7)
    c.drawString(lm, row_y - 6, 'Note: Ideal ranges may vary slightly with soil type and crop.')
    c.drawRightString(PAGE_W - lm, row_y - 6, 'Analysis Method: Spectroscopy + AI Interpretation')


# ─── Page 3: Grid Analysis ────────────────────────────────────────────────────

def _page3(c, preds, env, meta):
    _draw_page_header(c, 3)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'SOILENZ GRID ANALYSIS - FIELD WISE VARIABILITY')

    analysis_date = str(meta.get('analysis_date', '') or date.today().strftime('%d %b %Y'))

    # Info strip
    info_strip = [
        ('Field Area',    meta.get('field_area') or '-'),
        ('Grid Size',     '30 m x 30 m'),
        ('Total Grids',   '16'),
        ('Analysis Date', analysis_date),
    ]
    sx = 20; sy = TOP - 22
    sw = (PAGE_W - 40) / len(info_strip)
    for label, val in info_strip:
        c.setFillColorRGB(0.94, 0.97, 0.94)
        _draw_rounded_card(c, sx, sy - 20, sw - 4, 36, radius=6)
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica', 7)
        c.drawCentredString(sx + (sw - 4)/2, sy + 8, label)
        c.setFont('Helvetica-Bold', 9)
        c.setFillColorRGB(*_DK_GREEN)
        c.drawCentredString(sx + (sw - 4)/2, sy - 8, str(val))
        sx += sw

    # Heatmap grid: 4 cols x 4 rows = 16 cells (14 filled)
    hm_params = [
        ('pH (0-14)',           'ph',             4.5, 9.0,  True,  _ph_info),
        ('EC (dS/m)',           'ec',             0.0, 4.0,  True,  _ec_info),
        ('Organic Carbon (%)',  'organic_carbon', 0.0, 1.0,  False, _oc_info),
        ('Nitrogen (kg/ha)',    'n',              0.0, 600,  False, _n_info),
        ('Phosphorus (kg/ha)',  'p',              0.0, 70,   False, _p_info),
        ('Potassium (kg/ha)',   'k',              0.0, 500,  False, _k_info),
        ('Calcium (meq/100g)', 'ca',             0.0, 5.0,  False, _ca_info),
        ('Magnesium (meq/100g)','mg',            0.0, 3.0,  False, _mg_info),
        ('Sulfur (ppm)',        's',              0.0, 60,   False, _s_info),
        ('Iron (ppm)',          'fe',             0.0, 100,  False, _fe_info),
        ('Zinc (ppm)',          'zn',             0.0, 10,   False, _zn_info),
        ('Manganese (ppm)',     'mn',             0.0, 50,   False, _mn_info),
        ('Copper (ppm)',        'cu',             0.0, 15,   False, _cu_info),
        ('Boron (ppm)',         'b',              0.0, 5,    False, _b_info),
    ]

    hm_x0, hm_y0 = 20, TOP - 70
    cols4  = 4
    cell_w = (PAGE_W - 40) / cols4
    cell_h = 72

    for i, (label, key, vmin, vmax, rev, info_fn) in enumerate(hm_params):
        if i >= 16: break
        row = i // cols4
        col = i % cols4
        cx  = hm_x0 + col * cell_w
        cy  = hm_y0 - row * (cell_h + 22)
        avg = preds.get(key) or ((vmin + vmax) / 2)
        buf = _heatmap_img(4, 4, vmin, vmax, avg, reverse=rev, w_in=1.5, h_in=1.5)
        hm_pw = cell_w - 10
        _embed_img(c, buf, cx + 4, cy - cell_h + 6, hm_pw, cell_h - 12)
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(cx + 4, cy + 4, label)
        c.setFont('Helvetica', 6.5)
        disp = f'{avg:.2f}' if avg else '-'
        c.setFillColorRGB(*_GRAY)
        c.drawString(cx + 4, cy - cell_h + 3, f'{vmin:.0f}-{vmax:.0f}  Avg:{disp}')
        # Status badge
        st_txt, st_col, _, _ = info_fn(preds.get(key))
        _draw_status_badge(c, st_txt, st_col, cx + 4, cy - cell_h - 10, w=hm_pw - 4, h=11)

    # Insights box  (below 4 rows)
    ins_y = hm_y0 - 4 * (cell_h + 22) + 12
    c.setFillColorRGB(0.96, 0.99, 0.96)
    _draw_rounded_card(c, PAGE_W - 175, ins_y - 75, 155, 90, radius=8)
    c.setStrokeColorRGB(*_DK_GREEN)
    c.setLineWidth(0.7)
    c.roundRect(PAGE_W - 175, ins_y - 75, 155, 90, 8, fill=0, stroke=1)
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(PAGE_W - 97, ins_y + 5, 'GRID ANALYSIS INSIGHTS')

    ph  = preds.get('ph') or 7.0
    oc  = preds.get('organic_carbon') or 0.0
    n   = preds.get('n') or 0.0
    p   = preds.get('p') or 0.0
    insights = []
    if ph > 7.5:   insights.append('pH is alkaline across the field')
    elif ph < 6.0: insights.append('pH is acidic; lime application needed')
    else:          insights.append('pH is in optimal range')
    if oc < 0.5:   insights.append('Organic carbon is uniformly low')
    if n < 280:    insights.append('N is deficient in most grids')
    if p < 20:     insights.append('P is low; apply basal DAP')
    elif p > 70:   insights.append('P & K are high in field')
    insights.append('Micronutrients vary across grids')
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica', 7.5)
    for j, ins in enumerate(insights[:5]):
        c.drawString(PAGE_W - 168, ins_y - 10 - j * 13, f'* {ins}')


# ─── Page 4: Crop Suitability ─────────────────────────────────────────────────

CROP_PROFILES = [
    # (name, symbol, ph_ideal, oc_min, n_min, k_min, notes)
    ('Wheat',              '[W]', (6.0, 8.0), 0.4, 160, 100, 'Suitable; balanced fertility required'),
    ('Paddy',              '[P]', (5.5, 7.0), 0.5, 150, 120, 'Best suited to alkaline pH'),
    ('Sorghum (Jowar)',    '[J]', (5.5, 8.5), 0.3, 120,  80, 'Tolerant to alkaline soil & low N'),
    ('Pearl Millet',       '[M]', (6.0, 8.5), 0.3, 100,  80, 'Drought tolerant; adapts well'),
    ('Cotton',             '[C]', (5.8, 8.0), 0.4, 150, 120, 'Performs well with high K & alkaline pH'),
    ('Pigeon Pea (Tur)',   '[T]', (5.5, 7.5), 0.4, 100,  80, 'Good for soil fertility & low N conditions'),
    ('Groundnut',          '[G]', (6.0, 7.5), 0.4, 100, 100, 'Needs better organic matter'),
    ('Green Gram (Moong)', '[Mo]',(6.0, 7.5), 0.5, 120,  80, 'Sensitive to low Mn & B'),
    ('Tomato',             '[To]',(6.0, 6.8), 0.7, 250, 150, 'Sensitive to high pH, low OC & Mn'),
    ('Brinjal',            '[B]', (5.5, 7.0), 0.5, 200, 120, 'Needs rich organic matter & balanced nutrients'),
    ('Cauliflower',        '[Ca]',(6.0, 7.0), 0.7, 280, 150, 'Requires low pH & high organic matter'),
]


def _crop_score(profile, preds, env):
    name, sym, ph_ideal, oc_min, n_min, k_min, _ = profile
    ph  = preds.get('ph') or 7.0
    oc  = preds.get('organic_carbon') or 0.0
    n   = preds.get('n') or 0.0
    k   = preds.get('k') or 0.0
    ndv = env.get('ndvi', 0.5) or 0.5

    s = 10.0
    if ph < ph_ideal[0]:   s -= (ph_ideal[0] - ph) * 1.5
    elif ph > ph_ideal[1]: s -= (ph - ph_ideal[1]) * 2.0
    if oc < oc_min:        s -= (oc_min - oc) * 3.0
    if n < n_min:          s -= (n_min - n) / n_min * 2.5
    if k < k_min:          s -= (k_min - k) / k_min * 1.0
    s += (ndv - 0.4) * 2.0
    return round(max(0.0, min(10.0, s)), 1)


def _page4(c, preds, env, meta):
    _draw_page_header(c, 4)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'CROP SUITABILITY ANALYSIS')
    c.setFont('Helvetica', 8.5)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP - 16, 'Crop suitability based on soil (pH, EC, N, P, K, OC, Ca, Mg, S, Micro) & local climate')

    analysis_date = str(meta.get('analysis_date', '') or date.today().strftime('%d %b %Y'))

    # Info strip (same as page 3)
    info_strip = [
        ('Field Area',    meta.get('field_area') or '-'),
        ('Grid Size',     '30 m x 30 m'),
        ('Total Grids',   '16'),
        ('Analysis Date', analysis_date),
    ]
    sx_i = 20; sy_i = TOP - 38
    sw_i = (PAGE_W - 40) / len(info_strip)
    for label_i, val_i in info_strip:
        c.setFillColorRGB(0.94, 0.97, 0.94)
        _draw_rounded_card(c, sx_i, sy_i - 18, sw_i - 4, 32, radius=5)
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica', 7)
        c.drawCentredString(sx_i + (sw_i - 4)/2, sy_i + 6, label_i)
        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColorRGB(*_DK_GREEN)
        c.drawCentredString(sx_i + (sw_i - 4)/2, sy_i - 8, str(val_i))
        sx_i += sw_i

    scored = sorted(
        [(p[0], _crop_score(p, preds, env), p[6]) for p in CROP_PROFILES],
        key=lambda x: -x[1]
    )

    # AI crop highlight box
    ai_crop = str(meta.get('ai_crop', '') or '')
    chart_top = TOP - 76
    if ai_crop:
        c.saveState()
        _set_rgb(c, _LT_GREEN)
        _draw_rounded_card(c, 20, chart_top - 22, PAGE_W - 40, 20, radius=5)
        c.setStrokeColorRGB(*_MED_GREEN)
        c.setLineWidth(0.7)
        c.roundRect(20, chart_top - 22, PAGE_W - 40, 20, 5, fill=0, stroke=1)
        _set_rgb(c, _DK_GREEN)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(30, chart_top - 14, f'AI Recommended: {ai_crop} crop is best suited for current soil conditions.')
        c.restoreState()
        chart_top -= 26

    # Bar chart (left)
    names  = [s[0] for s in scored]
    scores = [s[1] for s in scored]
    bar_buf = _bar_chart_img(names, scores, w_in=4.0, h_in=3.2)
    chart_h = 210
    _embed_img(c, bar_buf, 20, chart_top - chart_h - 10, 285, chart_h)

    # Right table
    rx, ry = 318, chart_top - 8
    rw = PAGE_W - rx - 14
    headers = ['Crop', 'Score', 'Status', 'Key Notes']
    col_ws  = [80, 30, 68, rw - 80 - 30 - 68]
    rxs = [rx]
    for ww in col_ws[:-1]:
        rxs.append(rxs[-1] + ww)

    c.setFillColorRGB(*_DK_GREEN)
    c.rect(rx, ry - 16, rw, 16, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    for hdr, x in zip(headers, rxs):
        c.drawString(x + 3, ry - 11, hdr)

    ry2 = ry - 16
    for i, (crop, score, notes) in enumerate(scored):
        row_h_t = 20
        fill = _LGRAY if i % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(rx, ry2 - row_h_t, rw, row_h_t, fill=1, stroke=0)

        if score >= 8:   st, sc = 'Highly Recommended', _MED_GREEN
        elif score >= 7: st, sc = 'Recommended',        _MED_GREEN
        elif score >= 5: st, sc = 'Mod. Suitable',      _ORANGE
        else:            st, sc = 'Not Recommended',    _RED

        row_vals = [crop, f'{score:.1f}', '', notes[:26] if len(notes) > 26 else notes]
        c.setFont('Helvetica', 7.5)
        c.setFillColorRGB(*_DGRAY)
        for j, (val, x) in enumerate(zip(row_vals, rxs)):
            if j == 2:
                _draw_status_badge(c, st, sc, x + 2, ry2 - row_h_t + 4, w=63, h=13)
            else:
                c.drawString(x + 3, ry2 - row_h_t + 8, str(val))
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.3)
        c.line(rx, ry2 - row_h_t, rx + rw, ry2 - row_h_t)
        ry2 -= row_h_t

    # Top recommended crops + nutrient concerns bottom box
    top_crops = [s[0] for s in scored if s[1] >= 6]
    low_n, med_n, high_n, suff_n, adeq_n = _categorize_nutrients(preds)
    box_y = chart_top - chart_h - 30
    box_h = 52

    c.saveState()
    _set_rgb(c, (0.96, 0.99, 0.96))
    _draw_rounded_card(c, 20, box_y - box_h, PAGE_W - 40, box_h, radius=7)
    c.setStrokeColorRGB(*_MED_GREEN)
    c.setLineWidth(0.7)
    c.roundRect(20, box_y - box_h, PAGE_W - 40, box_h, 7, fill=0, stroke=1)

    _set_rgb(c, _DK_GREEN)
    c.setFont('Helvetica-Bold', 8)
    top_str = ', '.join(top_crops[:4]) if top_crops else 'Review soil health'
    c.drawString(28, box_y - 10, f'Top Recommended Crops: {top_str}')
    c.setFont('Helvetica', 7.5)
    _set_rgb(c, _DGRAY)
    c.drawString(28, box_y - 24, 'Improve soil organic carbon, nitrogen & micronutrients for better yield.')

    # Right half: nutrient categories
    half_x = 20 + (PAGE_W - 40) / 2 + 10
    _set_rgb(c, _DK_GREEN)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(half_x, box_y - 10, 'KEY NUTRIENT STATUS:')
    c.setFont('Helvetica', 7)
    _set_rgb(c, _DGRAY)
    nut_lines = []
    if low_n:  nut_lines.append(f'Low: {", ".join(low_n)}')
    if med_n:  nut_lines.append(f'Medium: {", ".join(med_n)}')
    if suff_n: nut_lines.append(f'Sufficient: {", ".join(suff_n)}')
    for li, nl in enumerate(nut_lines[:3]):
        c.drawString(half_x, box_y - 22 - li * 11, nl[:48])
    c.restoreState()


# ─── Page 5: Soil Amendment & Action Plan ────────────────────────────────────

def _page5(c, preds, env):
    _draw_page_header(c, 5)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'SOIL AMENDMENT & ACTION PLAN')
    c.setFont('Helvetica', 8)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP - 16, 'Balanced soil nutrition is the key to sustainable high yield and health.')

    ph  = preds.get('ph') or 7.0
    oc  = preds.get('organic_carbon') or 0.0
    n   = preds.get('n') or 0.0
    p   = preds.get('p') or 0.0
    k   = preds.get('k') or 0.0
    zn  = preds.get('zn') or 0.0
    mn  = preds.get('mn') or 0.0
    b   = preds.get('b')  or 0.0

    amendments = []
    amendments.append(('FYM / Compost',      '1000 kg/acre', 'Improve organic matter',   'Pre sowing', 'HIGH'))
    amendments.append(('Vermicompost',       '500 kg/acre',  'Boost soil biology',        'Pre sowing', 'HIGH'))
    if ph > 7.5:
        amendments.append(('Lime / Gypsum',  '150 kg/acre',  'Reduce soil alkalinity',    'Pre sowing', 'HIGH'))
    elif ph < 6.0:
        amendments.append(('Agricultural Lime', '200 kg/acre', 'Correct soil acidity',    'Pre sowing', 'HIGH'))
    if n < 280:
        amendments.append(('Urea (46% N)',   '45 kg/acre',   'Nitrogen supply',           'Split dose', 'MEDIUM'))
    if p < 20:
        amendments.append(('DAP (18-46-0)',  '50 kg/acre',   'Phosphorus supply',         'Basal',      'MEDIUM'))
    elif p < 45:
        amendments.append(('DAP (18-46-0)',  '25 kg/acre',   'Phosphorus supplement',     'Basal',      'MEDIUM'))
    if k < 120:
        amendments.append(('MOP (0-0-60)',   '35 kg/acre',   'Potassium supply',          'Basal',      'MEDIUM'))
    else:
        amendments.append(('MOP (0-0-60)',   '25 kg/acre',   'Potassium maintenance',     'Basal',      'LOW'))
    if zn < 0.6:
        amendments.append(('Zinc Sulphate',  '10 kg/acre',   'Zinc & sulfur supply',      'Basal',      'LOW'))
    if mn < 2.0:
        amendments.append(('MnSO4',          '10 kg/acre',   'Improve Mn availability',   'Basal',      'LOW'))
    if b < 0.5:
        amendments.append(('Borax',          '1 kg/acre',    'Boron supply',              'Basal',      'LOW'))
    amendments.append(('Micronutrient Mix', 'As per label', 'Micronutrient balance',     'Foliar',     'LOW'))

    # Amendment table
    lm, rw = 20, PAGE_W - 40
    widths2 = [130, 80, 130, 80, 60]
    xs2 = [lm]
    for ww in widths2[:-1]:
        xs2.append(xs2[-1] + ww)
    headers2 = ['Input / Amendment', 'Dose (Per Acre)', 'Purpose', 'Timing', 'Priority']
    row_h2 = 18

    ty = TOP - 32
    c.setFillColorRGB(*_DK_GREEN)
    c.rect(lm, ty, rw, row_h2, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    for hdr, x in zip(headers2, xs2):
        c.drawString(x + 4, ty + 6, hdr)

    ry3 = ty - row_h2
    for i, (inp, dose, purpose, timing, prio) in enumerate(amendments[:10]):
        fill = _LGRAY if i % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(lm, ry3, rw, row_h2, fill=1, stroke=0)
        prio_color = _RED if prio == 'HIGH' else (_YELLOW if prio == 'MEDIUM' else _MED_GREEN)
        row_vals2 = [inp, dose, purpose, timing, '']
        c.setFont('Helvetica', 7.5)
        c.setFillColorRGB(*_DGRAY)
        for j, (val, x) in enumerate(zip(row_vals2, xs2)):
            if j == 4:
                _draw_status_badge(c, f'* {prio}', prio_color, x + 2, ry3 + 3, w=52, h=13)
            else:
                c.drawString(x + 4, ry3 + 6, str(val)[:22] if len(str(val)) > 22 else str(val))
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.3)
        c.line(lm, ry3, lm + rw, ry3)
        ry3 -= row_h2

    # Action Plan Timeline
    tl_y = ry3 - 24
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(lm, tl_y, 'ACTION PLAN TIMELINE')

    phases = [
        ('Pre sowing',        '(0-7 days)',      ['Apply FYM / Compost', 'Apply Lime (if needed)', 'Prepare fine tilth']),
        ('Basal Dose',        'At sowing',        ['Apply DAP, MOP', 'Apply Zinc Sulphate', 'Apply 1/3 Urea']),
        ('During Crop Growth','(20-45 DAS)',      ['Apply 2nd split Urea', 'Foliar micronutrients', 'Weed management']),
        ('Pre Harvest',       '(90-100 DAS)',     ['Balanced irrigation', 'Harvest at maturity']),
    ]
    ph_w = (rw - 30) / len(phases)
    ph_y = tl_y - 16
    for i, (ph_name, ph_sub, ph_items) in enumerate(phases):
        bx = lm + i * (ph_w + 10)
        c.setFillColorRGB(0.94, 0.97, 0.94)
        _draw_rounded_card(c, bx, ph_y - 80, ph_w, 82, radius=6)
        c.setFillColorRGB(*_DK_GREEN)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(bx + ph_w/2, ph_y - 4, ph_name)
        c.setFont('Helvetica', 7)
        c.setFillColorRGB(*_GRAY)
        c.drawCentredString(bx + ph_w/2, ph_y - 15, ph_sub)
        c.setFillColorRGB(*_DGRAY)
        for j, item in enumerate(ph_items):
            c.drawString(bx + 6, ph_y - 28 - j * 14, f'* {item}')
        if i < len(phases) - 1:
            ax2 = bx + ph_w + 2
            ay2 = ph_y - 42
            c.setFillColorRGB(*_DK_GREEN)
            c.setFont('Helvetica-Bold', 12)
            c.drawString(ax2, ay2, '->')

    # IMPORTANT CORRECTIONS box (left bottom)
    corr_y_top = ph_y - 100
    corr_x  = lm
    corr_w  = 270
    corr_h  = corr_y_top - 40
    if corr_h > 20:
        c.saveState()
        _set_rgb(c, _LGRAY)
        _draw_rounded_card(c, corr_x, 38, corr_w, max(corr_h, 20), radius=6)
        _set_rgb(c, _DK_GREEN)
        c.roundRect(corr_x, 38 + max(corr_h, 20) - 16, corr_w, 16, 4, fill=1, stroke=0)
        _set_rgb(c, _WHITE)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(corr_x + 6, 38 + max(corr_h, 20) - 11, 'IMPORTANT CORRECTIONS FROM SOIL TEST')
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica', 7)
        corrections = []
        if n < 280:
            corrections.append('Low N - apply urea in split doses.')
        p_stat, _, _, _ = _p_info(p)
        if 'Low' in p_stat:
            corrections.append('Low P - apply basal DAP at 50 kg/acre.')
        elif 'Medium' in p_stat:
            corrections.append('Medium P - apply basal DAP at 25 kg/acre.')
        if k >= 280:
            corrections.append('High K - no potash needed.')
        elif k < 120:
            corrections.append('Low K - apply MOP at 35 kg/acre.')
        if ph > 7.5:
            corrections.append('Alkaline pH - apply gypsum/lime to correct.')
        if oc < 0.5:
            corrections.append('Low OC - apply FYM 1000 kg/acre.')
        if zn < 0.6:
            corrections.append('Low Zn - apply zinc sulphate 10 kg/acre.')
        if mn < 2.0:
            corrections.append('Low Mn - apply MnSO4 10 kg/acre.')
        c_y = 38 + max(corr_h, 20) - 28
        for cor in corrections[:5]:
            if c_y < 42: break
            c.drawString(corr_x + 8, c_y, f'* {cor}')
            c_y -= 12
        c.restoreState()

    # KEY SOIL TEST SUMMARY (right bottom)
    sum_x = 305
    sum_w = 270
    low_n2, med_n2, high_n2, suff_n2, adeq_n2 = _categorize_nutrients(preds)
    if corr_h > 20:
        c.saveState()
        _set_rgb(c, _LGRAY)
        _draw_rounded_card(c, sum_x, 38, sum_w, max(corr_h, 20), radius=6)
        _set_rgb(c, _DK_GREEN)
        c.roundRect(sum_x, 38 + max(corr_h, 20) - 16, sum_w, 16, 4, fill=1, stroke=0)
        _set_rgb(c, _WHITE)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(sum_x + 6, 38 + max(corr_h, 20) - 11, 'KEY SOIL TEST SUMMARY')
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica', 7)
        summary_lines = []
        if low_n2:  summary_lines.append((_RED,       f'Low: {", ".join(low_n2)}'))
        if med_n2:  summary_lines.append((_ORANGE,    f'Medium: {", ".join(med_n2)}'))
        if high_n2: summary_lines.append((_BLUE,      f'High: {", ".join(high_n2)}'))
        if suff_n2: summary_lines.append((_MED_GREEN, f'Sufficient: {", ".join(suff_n2)}'))
        ph_s, ph_c, _, _ = _ph_info(preds.get('ph'))
        ec_s, ec_c, _, _ = _ec_info(preds.get('ec'))
        ph_disp2 = f'{preds.get("ph"):.2f}' if preds.get('ph') is not None else 'N/A'
        ec_disp2 = f'{preds.get("ec"):.4f}' if preds.get('ec') is not None else 'N/A'
        summary_lines.append((_DGRAY, f'pH: {ph_disp2} ({ph_s})'))
        summary_lines.append((_DGRAY, f'EC: {ec_disp2} ({ec_s})'))
        s_y = 38 + max(corr_h, 20) - 28
        for line_color, line_text in summary_lines[:6]:
            if s_y < 42: break
            c.setFillColorRGB(*line_color)
            c.circle(sum_x + 8, s_y + 3, 2.5, fill=1, stroke=0)
            c.setFillColorRGB(*_DGRAY)
            c.drawString(sum_x + 15, s_y, line_text[:46])
            s_y -= 12
        c.restoreState()


# ─── Page 6: Carbon Credit Dashboard ─────────────────────────────────────────

def _page6(c, preds, env, meta):
    _draw_page_header(c, 6)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'CARBON CREDIT IMPACT DASHBOARD')
    c.setFont('Helvetica', 8)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP - 16, 'Your soil health action leads to environment and income.')

    oc   = preds.get('organic_carbon') or 0.3
    ndvi = env.get('ndvi', 0.5) or 0.5
    n    = preds.get('n') or 0.0
    mn   = preds.get('mn') or 0.0
    ca   = preds.get('ca') or 0.0
    mg   = preds.get('mg') or 0.0
    k    = preds.get('k') or 0.0

    oc_after   = min(oc + 0.42, 1.5)
    bio_before = round(1.0 + ndvi * 3, 1)
    bio_after  = round(bio_before * 1.6, 1)
    oc_seq     = round((oc_after - oc) / 0.1 * 50, 0)
    bio_seq    = round(bio_after * 120, 0)
    total_seq  = int(oc_seq + bio_seq)

    # Flow diagram
    flow_items = [
        'Sustainable\nPractices', 'Improved Soil\nHealth', 'Higher Yield\n& Biomass',
        'CO2\nSequestration', 'Carbon Credit\nGeneration',
    ]
    fw = (PAGE_W - 40) / len(flow_items)
    fy = TOP - 52
    for i, fi in enumerate(flow_items):
        bx = 20 + i * fw
        c.setFillColorRGB(0.92, 0.97, 0.92)
        _draw_rounded_card(c, bx + 4, fy - 26, fw - 8, 36, radius=8)
        c.setFillColorRGB(*_DK_GREEN)
        c.setFont('Helvetica', 7)
        for li, line in enumerate(fi.split('\n')):
            c.drawCentredString(bx + fw/2, fy - 4 - li * 10, line)
        if i < len(flow_items) - 1:
            c.setFillColorRGB(*_DK_GREEN)
            c.setFont('Helvetica-Bold', 12)
            c.drawString(bx + fw - 2, fy - 14, '->')

    # Carbon sequestration table
    tbl_y = fy - 44
    lm = 20
    tbl_w = 260
    t_headers = ['Parameter', 'Current Value', 'After Improvement (1yr)', 'Annual Seq (kg CO2/acre)']
    t_rows = [
        ('Organic Carbon (%)', f'{oc:.2f}', f'{oc_after:.2f}', str(int(oc_seq))),
        ('Biomass (t/acre)',   f'{bio_before:.1f}', f'{bio_after:.1f}', str(int(bio_seq))),
        ('Total',             '-',           '-',                str(total_seq)),
    ]
    col_ws3 = [95, 55, 70, 40]
    xs3 = [lm]
    for ww in col_ws3:
        xs3.append(xs3[-1] + ww)

    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(lm, tbl_y + 4, 'ESTIMATED CARBON SEQUESTRATION (Per Acre)')

    h_y = tbl_y - 14
    c.setFillColorRGB(*_DK_GREEN)
    c.rect(lm, h_y, tbl_w, 16, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 7)
    for hdr, x in zip(t_headers, xs3):
        c.drawString(x + 3, h_y + 5, hdr.split('\n')[0])

    r_y3 = h_y - 18
    for i, row in enumerate(t_rows):
        fill = _LGRAY if i % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(lm, r_y3, tbl_w, 18, fill=1, stroke=0)
        c.setFont('Helvetica', 7.5)
        c.setFillColorRGB(*(_DK_GREEN if i == 2 else _DGRAY))
        for val, x in zip(row, xs3):
            c.drawString(x + 3, r_y3 + 5, str(val))
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.3)
        c.line(lm, r_y3, lm + tbl_w, r_y3)
        r_y3 -= 18

    # Carbon health score (right side)
    carbon_score = min(100, int(50 + ndvi * 30 + oc * 15))
    cg_x, cg_y = 310, tbl_y - 10
    cg_buf = _carbon_gauge_img(carbon_score, w_in=2.5, h_in=1.7)
    _embed_img(c, cg_buf, cg_x, cg_y - 90, 130, 90)

    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(cg_x + 65, cg_y + 4, 'CARBON HEALTH SCORE')
    cs_lbl = 'Excellent' if carbon_score >= 80 else ('Good' if carbon_score >= 60 else 'Moderate')
    c.setFillColorRGB(*((_MED_GREEN) if carbon_score >= 60 else (_ORANGE)))
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(cg_x + 65, cg_y - 96, cs_lbl)

    # CO2 saved box
    co2_y = tbl_y
    c.setFillColorRGB(*_DK_GREEN)
    _draw_rounded_card(c, 460, co2_y - 80, 110, 82, radius=8)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(515, co2_y - 10, 'CO2 SAVED (Per Year)')
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(515, co2_y - 34, f'{total_seq}')
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(515, co2_y - 48, 'kg CO2')
    c.setFont('Helvetica', 7.5)
    c.drawCentredString(515, co2_y - 60, '(Per Acre)')
    c.setFont('Helvetica', 7)
    c.drawCentredString(515, co2_y - 72, f'TOTAL: {total_seq} kg CO2/Acre/Year')

    # KEY BENEFITS & SOIL INSIGHTS (right side)
    ben_y = r_y3 - 16
    ben_x = 305
    ben_w = PAGE_W - ben_x - 14
    c.saveState()
    _set_rgb(c, _LGRAY)
    _draw_rounded_card(c, ben_x, ben_y - 90, ben_w, 88, radius=6)
    _set_rgb(c, _DK_GREEN)
    c.roundRect(ben_x, ben_y - 90 + 88 - 16, ben_w, 16, 4, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ben_x + 6, ben_y - 90 + 88 - 11, 'KEY BENEFITS & SOIL INSIGHTS')
    _set_rgb(c, _DGRAY)
    c.setFont('Helvetica', 7.5)
    dyn_benefits = [
        'Rs 700-1200 extra income possible from carbon credits',
        'Improves soil structure & water holding capacity',
    ]
    if k >= 280 or ca >= 1.5 or mg >= 1.0:
        dyn_benefits.append('High K / Mg / Ca indicators from test')
    if n < 280 or mn < 2.0:
        dyn_benefits.append('N & Mn are low - correction needed')
    dyn_benefits.append('Supports sustainable & climate-smart farming')

    ben_item_y = ben_y - 90 + 88 - 26
    for ben in dyn_benefits[:4]:
        if ben_item_y < ben_y - 90 + 4: break
        c.drawString(ben_x + 8, ben_item_y, f'* {ben}')
        ben_item_y -= 14
    c.restoreState()

    # SOIL INTERPRETATION (left, below table)
    interp_y_top = r_y3 - 16
    interp_x = lm
    interp_w = 275
    interp_h = 88
    c.saveState()
    _set_rgb(c, _LGRAY)
    _draw_rounded_card(c, interp_x, interp_y_top - interp_h, interp_w, interp_h, radius=6)
    _set_rgb(c, _DK_GREEN)
    c.roundRect(interp_x, interp_y_top - interp_h + interp_h - 16, interp_w, 16, 4, fill=1, stroke=0)
    _set_rgb(c, _WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(interp_x + 6, interp_y_top - interp_h + interp_h - 11, 'SOIL INTERPRETATION')
    _set_rgb(c, _DGRAY)
    c.setFont('Helvetica', 6.5)
    interp_params = [
        ('OC',  'organic_carbon', _oc_info),
        ('N',   'n',              _n_info),
        ('P',   'p',              _p_info),
        ('K',   'k',              _k_info),
        ('Ca',  'ca',             _ca_info),
        ('Mg',  'mg',             _mg_info),
        ('pH',  'ph',             _ph_info),
        ('EC',  'ec',             _ec_info),
    ]
    ip_y = interp_y_top - interp_h + interp_h - 26
    col_h_count = 0
    col_offset = 0
    for short_name, key, info_fn in interp_params:
        val_ip = preds.get(key)
        st_ip, col_ip, _, _ = info_fn(val_ip)
        val_str_ip = f'{val_ip:.2f}' if val_ip is not None else 'N/A'
        disp_ip = f'{short_name}: {val_str_ip} ({st_ip})'
        c.setFillColorRGB(*col_ip)
        c.drawString(interp_x + 8 + col_offset, ip_y, disp_ip)
        ip_y -= 11
        col_h_count += 1
        if col_h_count == 4:
            col_h_count = 0
            col_offset = 130
            ip_y = interp_y_top - interp_h + interp_h - 26
    c.restoreState()

    # IMPORTANT CORRECTIONS (bottom-left)
    corr2_y = interp_y_top - interp_h - 6
    corr2_x = lm
    corr2_w = interp_w
    corr2_h = corr2_y - 36
    if corr2_h > 20:
        c.saveState()
        _set_rgb(c, _LGRAY)
        _draw_rounded_card(c, corr2_x, 34, corr2_w, max(corr2_h, 20), radius=6)
        _set_rgb(c, _DK_GREEN)
        c.roundRect(corr2_x, 34 + max(corr2_h, 20) - 16, corr2_w, 16, 4, fill=1, stroke=0)
        _set_rgb(c, _WHITE)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(corr2_x + 6, 34 + max(corr2_h, 20) - 11, 'IMPORTANT CORRECTIONS FROM SOIL TEST')
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica', 7)
        corrections2 = []
        if preds.get('n') and preds.get('n') < 280:
            corrections2.append('Low N - apply urea in split doses.')
        p_v = preds.get('p') or 0
        if p_v < 20:
            corrections2.append('Low P - apply basal DAP at 50 kg/acre.')
        if preds.get('k') and preds.get('k') >= 280:
            corrections2.append('High K - no potash needed.')
        if preds.get('ph') and preds.get('ph') > 7.5:
            corrections2.append('Alkaline pH - apply gypsum to correct.')
        if oc < 0.5:
            corrections2.append('Low OC - apply FYM 1000 kg/acre.')
        c2y = 34 + max(corr2_h, 20) - 28
        for cor2 in corrections2[:4]:
            if c2y < 38: break
            c.drawString(corr2_x + 8, c2y, f'* {cor2}')
            c2y -= 12
        c.restoreState()

    # KEY SOIL TEST SUMMARY (bottom-right)
    sum2_x = ben_x
    sum2_w = ben_w
    if corr2_h > 20:
        low_n3, med_n3, high_n3, suff_n3, adeq_n3 = _categorize_nutrients(preds)
        c.saveState()
        _set_rgb(c, _LGRAY)
        _draw_rounded_card(c, sum2_x, 34, sum2_w, max(corr2_h, 20), radius=6)
        _set_rgb(c, _DK_GREEN)
        c.roundRect(sum2_x, 34 + max(corr2_h, 20) - 16, sum2_w, 16, 4, fill=1, stroke=0)
        _set_rgb(c, _WHITE)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(sum2_x + 6, 34 + max(corr2_h, 20) - 11, 'KEY SOIL TEST SUMMARY')
        _set_rgb(c, _DGRAY)
        c.setFont('Helvetica', 7)
        sum2_lines = []
        if low_n3:  sum2_lines.append((_RED,       f'Low: {", ".join(low_n3)}'))
        if med_n3:  sum2_lines.append((_ORANGE,    f'Medium: {", ".join(med_n3)}'))
        if high_n3: sum2_lines.append((_BLUE,      f'High: {", ".join(high_n3)}'))
        if suff_n3: sum2_lines.append((_MED_GREEN, f'Sufficient: {", ".join(suff_n3)}'))
        if adeq_n3: sum2_lines.append((_GRAY,      f'Adequate: {", ".join(adeq_n3)}'))
        s2y = 34 + max(corr2_h, 20) - 28
        for s2_color, s2_text in sum2_lines[:5]:
            if s2y < 38: break
            c.setFillColorRGB(*s2_color)
            c.circle(sum2_x + 8, s2y + 3, 2.5, fill=1, stroke=0)
            c.setFillColorRGB(*_DGRAY)
            c.drawString(sum2_x + 15, s2y, s2_text[:44])
            s2y -= 12
        c.restoreState()

    # Footer note
    c.saveState()
    _set_rgb(c, _LGRAY)
    c.rect(0, 20, PAGE_W, 22, fill=1, stroke=0)
    _set_rgb(c, _GRAY)
    c.setFont('Helvetica-Oblique', 6.5)
    c.drawCentredString(PAGE_W/2, 28,
        'Note: Carbon sequestration potential varies with management, climate, soil type & crop. '
        'This report is generated by SoiLENZ AI.')
    c.restoreState()


# ─── Public API ──────────────────────────────────────────────────────────────

def generate_pdf(preds, env_features, fertility, metadata):
    """
    Build and return the 6-page SoiLENZ PDF as bytes.

    preds        : dict from predict_for_point / dummy_predictions (14 params including ca, mg)
    env_features : dict from same functions
    fertility    : str ('Low' / 'Medium' / 'High')
    metadata     : dict with keys:
                   location, analysis_date, field_area, crop,
                   agro_zone, farmer_name, farmer_mobile, farmer_image_path,
                   report_time, lab_name, ai_crop
    """
    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)

    _page1(c, preds, env_features, fertility, metadata)
    c.showPage()

    _page2(c, preds, metadata)
    c.showPage()

    _page3(c, preds, env_features, metadata)
    c.showPage()

    _page4(c, preds, env_features, metadata)
    c.showPage()

    _page5(c, preds, env_features)
    c.showPage()

    _page6(c, preds, env_features, metadata)
    c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()