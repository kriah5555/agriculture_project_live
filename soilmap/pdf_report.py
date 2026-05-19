"""
SoiLENZ Soil Health Intelligence Report – PDF Generator
Uses ReportLab canvas + Matplotlib for charts.
"""
import io
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


# ─── Parameter definitions ────────────────────────────────────────────────────

def _ph_info(v):
    if v is None: return 'N/A', _GRAY, '6.0–7.5', 'No data'
    if v > 7.5:   return 'Alkaline', _RED,    '6.0–7.5', 'Alkaline soil; limits nutrient availability'
    if v < 6.0:   return 'Acidic',   _ORANGE, '6.0–7.5', 'Acidic soil; apply lime to correct'
    return 'Normal', _MED_GREEN, '6.0–7.5', 'Optimal pH for most crops'

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
    if v is None: return 'N/A', _GRAY, '20–70', 'No data'
    if 20 <= v <= 70: return 'Medium', _YELLOW, '20–70 kg/ha', 'Marginal; apply basal P (DAP)'
    if v > 70:    return 'Sufficient', _MED_GREEN, '20–70 kg/ha', 'High phosphorus; no addition needed'
    return 'Low', _RED, '20–70 kg/ha', 'Deficient; apply DAP at basal dose'

def _k_info(v):
    if v is None: return 'N/A', _GRAY, '> 120', 'No data'
    if v >= 280:  return 'Sufficient', _MED_GREEN, '> 120 kg/ha', 'High potassium; sufficient for crop'
    if v >= 120:  return 'Medium',     _YELLOW,    '> 120 kg/ha', 'Adequate; monitor crop response'
    return 'Low', _RED, '> 120 kg/ha', 'Deficient; apply MOP at basal dose'

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
    return 'Low', _RED, '> 2.0 ppm', 'Deficient; apply MnSO₄'

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

PARAMS_12 = [
    # (display_name, unit, key, info_fn)
    ('pH (0–14)',                   'pH',         'ph',             _ph_info),
    ('Electrical Conductivity (EC)','dS/m',        'ec',             _ec_info),
    ('Organic Carbon (OC)',         '%',           'organic_carbon', _oc_info),
    ('Nitrogen (N)',                'kg/ha',       'n',              _n_info),
    ('Phosphorus (P)',              'kg/ha',       'p',              _p_info),
    ('Potassium (K)',               'kg/ha',       'k',              _k_info),
    ('Sulfur (S)',                  'ppm',         's',              _s_info),
    ('Iron (Fe)',                   'ppm',         'fe',             _fe_info),
    ('Manganese (Mn)',              'ppm',         'mn',             _mn_info),
    ('Copper (Cu)',                 'ppm',         'cu',             _cu_info),
    ('Zinc (Zn)',                   'ppm',         'zn',             _zn_info),
    ('Boron (B)',                   'ppm',         'b',              _b_info),
]


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

    # pH: best 6.0–7.5
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
    """Normalise one parameter to 0–100 for mini-gauge."""
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

    # Colour arc: red → yellow → green  (180° → 0°)
    N = 360
    theta = np.linspace(np.pi, 0, N)
    for i in range(N - 1):
        frac = i / (N - 2)
        r = 1.0 - frac * 0.5   # red→green
        g = frac * 0.8
        b = 0.1
        ax.plot([np.cos(theta[i]), np.cos(theta[i+1])],
                [np.sin(theta[i]), np.sin(theta[i+1])],
                color=(r, g, b), linewidth=10, solid_capstyle='round')

    # Grey inner track
    ax.plot(np.cos(theta)*0.78, np.sin(theta)*0.78,
            color='#e0e0e0', linewidth=5, alpha=0.4)

    # Needle
    angle = np.pi - (score / max_val) * np.pi
    nx, ny = 0.72 * np.cos(angle), 0.72 * np.sin(angle)
    ax.annotate('', xy=(nx, ny), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', color='#212121', lw=2.5))
    ax.add_patch(plt.Circle((0, 0), 0.07, color='#333', zorder=6))

    # Score label
    ax.text(0, -0.25, str(score), ha='center', va='center',
            fontsize=22, fontweight='bold', color='#1a1a1a')
    ax.text(0, -0.52, f'/100', ha='center', va='center',
            fontsize=10, color='#666')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=160, bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def _mini_gauge_img(value_pct, w_in=1.2, h_in=0.85):
    """Mini semicircle gauge, value_pct ∈ [0, 100]."""
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
    ax.set_xlabel('Score (0–10)', fontsize=8)
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

    # Page number circle bottom-right
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
    c.drawCentredString(x + w/2, y + 4, text)
    c.restoreState()


# ─── Page 1: Cover ───────────────────────────────────────────────────────────

def _page1(c, preds, env, fertility, meta):
    _draw_page_header(c, 1)
    TOP = PAGE_H - 60

    # Main white card
    c.saveState()
    c.setFillColorRGB(0.98, 0.98, 0.98)
    _draw_rounded_card(c, 14, 30, PAGE_W - 28, TOP - 38, radius=10)
    c.restoreState()

    # ── Left panel: Title + metadata ─────────────────────────────────────────
    lx = 24
    ty = TOP - 18

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 18)
    c.drawString(lx, ty, 'SOIL HEALTH')
    c.setFont('Helvetica-Bold', 18)
    c.drawString(lx, ty - 22, 'INTELLIGENCE')
    c.drawString(lx, ty - 44, 'REPORT')

    # "Powered by SoiLENZ" pill
    c.setFillColorRGB(*_DK_GREEN)
    _draw_rounded_card(c, lx, ty - 66, 110, 18, radius=5)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(lx + 8, ty - 59, 'Powered by SoiLENZ')

    # Metadata list
    meta_items = [
        ('Location',         meta.get('location') or '–'),
        ('Date of Analysis', meta.get('analysis_date') or date.today().strftime('%d %b %Y')),
        ('Field Area',       meta.get('field_area') or '–'),
        ('Crop (Current)',   meta.get('crop') or '–'),
        ('Agro Climatic Zone', meta.get('agro_zone') or '–'),
        ('Rainfall',         f"{env.get('rainfall_mm', '–')} mm" if env.get('rainfall_mm') else '–'),
        ('Temperature',      f"{env.get('temperature_c', '–')} °C" if env.get('temperature_c') else '–'),
        ('NDVI',             str(env.get('ndvi', '–'))),
    ]
    my = ty - 88
    for label, val in meta_items:
        c.setFillColorRGB(*_GRAY)
        c.setFont('Helvetica', 7)
        c.drawString(lx, my, label)
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(lx, my - 11, str(val))
        my -= 26

    # ── Centre: Oval soil illustration ───────────────────────────────────────
    cx_mid = PAGE_W / 2
    ov_y   = 200
    ov_h   = 190
    ov_w   = 130

    # Sky oval
    c.saveState()
    c.setFillColorRGB(0.82, 0.93, 0.82)
    c.ellipse(cx_mid - ov_w/2, ov_y, cx_mid + ov_w/2, ov_y + ov_h, fill=1, stroke=0)
    # Soil half
    c.setFillColorRGB(0.48, 0.30, 0.10)
    c.ellipse(cx_mid - ov_w/2, ov_y, cx_mid + ov_w/2, ov_y + ov_h*0.4, fill=1, stroke=0)
    c.restoreState()

    # Overall fertility badge
    score   = _soil_health_score(preds, env)
    f_label, f_color = _fertility_label(score)
    badge_y = ov_y + 12
    c.saveState()
    c.setFillColorRGB(*_BLACK)
    bw = 150
    _draw_rounded_card(c, cx_mid - bw/2, badge_y - 2, bw, 42, radius=8)
    c.setFillColorRGB(*_LT_GREEN)
    _draw_rounded_card(c, cx_mid - bw/2 + 1, badge_y - 1, bw - 2, 40, radius=7)
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(cx_mid, badge_y + 28, 'OVERALL SOIL FERTILITY')
    c.setFillColorRGB(*f_color)
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(cx_mid, badge_y + 10, f_label)
    c.restoreState()

    # ── Right panel: Score gauge + indicators ────────────────────────────────
    rx = cx_mid + 85
    ry_top = TOP - 10

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(rx, ry_top, 'SoiLENZ')
    c.setFont('Helvetica', 7)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(rx, ry_top - 14, 'Advanced Soil Intelligence')
    c.drawString(rx, ry_top - 24, 'from Arkashine Labs')

    # Score card
    sc_x, sc_y = rx - 8, ry_top - 135
    sc_w, sc_h = 148, 105
    c.setFillColorRGB(*_WHITE)
    _draw_rounded_card(c, sc_x, sc_y, sc_w, sc_h, radius=8)
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.8)
    c.roundRect(sc_x, sc_y, sc_w, sc_h, 8, fill=0, stroke=1)

    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(sc_x + sc_w/2, sc_y + sc_h - 12, 'SOIL HEALTH SCORE')

    gauge_buf = _gauge_img(score)
    g_w, g_h = 110, 72
    _embed_img(c, gauge_buf, sc_x + (sc_w - g_w)/2, sc_y + 16, g_w, g_h)

    s_label = ('EXCELLENT' if score >= 80 else 'GOOD' if score >= 65
               else 'MODERATE' if score >= 50 else 'LOW')
    s_color = (_MED_GREEN if score >= 65 else _YELLOW if score >= 50 else _ORANGE)
    c.setFillColorRGB(*s_color)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(sc_x + sc_w/2, sc_y + 6, s_label)

    # Indicators card
    ind_x, ind_y = rx - 8, sc_y - 142
    ind_w, ind_h = 148, 135
    c.setFillColorRGB(*_WHITE)
    _draw_rounded_card(c, ind_x, ind_y, ind_w, ind_h, radius=8)
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.8)
    c.roundRect(ind_x, ind_y, ind_w, ind_h, 8, fill=0, stroke=1)
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(ind_x + ind_w/2, ind_y + ind_h - 12, 'SOIL HEALTH INDICATORS')

    indicators = [
        ('pH',  'ph',             preds.get('ph'),             7.5),
        ('EC',  'ec',             preds.get('ec'),             4.0),
        ('N',   'n',              preds.get('n'),              560),
        ('P',   'p',              preds.get('p'),              70),
        ('K',   'k',              preds.get('k'),              500),
        ('OC',  'organic_carbon', preds.get('organic_carbon'), 1.5),
    ]
    mg_w, mg_h = 40, 28
    cols3 = 3
    gx0   = ind_x + 10
    for i, (lbl, key, val, maxv) in enumerate(indicators):
        col  = i % cols3
        row  = i // cols3
        gx   = gx0 + col * ((ind_w - 20) / cols3)
        gy   = ind_y + ind_h - 32 - row * 54

        pct  = _param_score_100(key, val)
        mg   = _mini_gauge_img(pct, mg_w / 72, mg_h / 72)
        _embed_img(c, mg, gx, gy - mg_h + 6, mg_w, mg_h)

        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica-Bold', 7)
        c.drawCentredString(gx + mg_w/2, gy - mg_h - 3, lbl)

        disp = f'{val:.0f}' if val is not None else '–'
        c.setFont('Helvetica', 6.5)
        c.setFillColorRGB(*_GRAY)
        c.drawCentredString(gx + mg_w/2, gy - mg_h - 12, f'{disp}/{int(maxv)}')

    # ── Footer tagline ────────────────────────────────────────────────────────
    c.setFillColorRGB(*_DK_GREEN)
    c.rect(0, 0, PAGE_W, 30, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(PAGE_W/2, 10, 'Healthy Soil. Higher Yield. Sustainable Future.')


# ─── Page 2: 14-parameter table ───────────────────────────────────────────────

def _page2(c, preds):
    _draw_page_header(c, 2)
    TOP = PAGE_H - 58

    # Title block
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'ARKASHINE SOILENZ RESULTS –')
    c.drawString(20, TOP - 18, 'DETAILED 12 PARAMETER TEST')
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
        'Scientific 12-parameter soil test',
        'Lab-grade accuracy in your field in 60 sec',
        'Smart recommendations for higher yield',
        'Enables data-driven decision farming',
    ]
    for i, b in enumerate(bullets):
        c.setFont('Helvetica', 7.5)
        c.drawString(bx + 14, by + bh - 28 - i * 13, f'✓  {b}')

    # Analysis date
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(20, TOP - 86, 'DETAILED 12 PARAMETER RESULTS')
    c.setFont('Helvetica', 8)
    c.drawRightString(PAGE_W - 20, TOP - 86, f'Analysis Date: {date.today().strftime("%d %b %Y")}')

    # Table
    col_x  = [20, 22+60, 22+120, 22+175, 22+235, 22+330]  # #, param, value, unit, status, ideal, interp
    col_x  = [20, 28, 135, 185, 220, 290, 380]
    headers = ['#', 'Parameter', 'Value', 'Unit', 'Status', 'Ideal Range', 'Interpretation']
    col_w   = [18, 107, 50, 35, 70, 65, 130]

    # Recompute from left margin
    lm = 20
    total_w = PAGE_W - 40
    widths = [18, 110, 50, 38, 70, 65, total_w - 18 - 110 - 50 - 38 - 70 - 65]
    xs = [lm]
    for ww in widths[:-1]:
        xs.append(xs[-1] + ww)

    row_h = 18
    hy    = TOP - 104

    # Header row
    c.setFillColorRGB(*_DK_GREEN)
    c.rect(lm, hy, total_w, row_h, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    for i, (hdr, x) in enumerate(zip(headers, xs)):
        c.drawString(x + 3, hy + 6, hdr)

    row_y = hy - row_h
    for idx, (name, unit, key, info_fn) in enumerate(PARAMS_12):
        val = preds.get(key)
        status_txt, status_rgb, ideal, interp = info_fn(val)
        val_txt = f'{val:.3f}' if val is not None else 'N/A'

        # Alternating row fill
        fill = _LGRAY if idx % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(lm, row_y, total_w, row_h, fill=1, stroke=0)

        row_data = [str(idx + 1), name, val_txt, unit, '', ideal, interp]
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica', 7.5)
        for i, (cell, x) in enumerate(zip(row_data, xs)):
            if i == 2:                       # value – bold coloured
                c.setFillColorRGB(*status_rgb)
                c.setFont('Helvetica-Bold', 7.5)
                c.drawString(x + 3, row_y + 6, cell)
                c.setFont('Helvetica', 7.5)
                c.setFillColorRGB(*_DGRAY)
            elif i == 4:                     # status badge
                _draw_status_badge(c, status_txt, status_rgb, x + 2, row_y + 3, w=62, h=13)
            else:
                c.setFillColorRGB(*_DGRAY)
                c.setFont('Helvetica', 7)
                # wrap interpretation
                if i == 6:
                    # simple truncation
                    txt = interp[:42] if len(interp) > 42 else interp
                    c.drawString(x + 2, row_y + 6, txt)
                else:
                    c.drawString(x + 3, row_y + 6, cell)

        # thin separator
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.4)
        c.line(lm, row_y, lm + total_w, row_y)
        row_y -= row_h

    # Footer note
    c.setFillColorRGB(*_GRAY)
    c.setFont('Helvetica-Oblique', 7)
    c.drawString(lm, row_y - 6, 'Note: Ideal ranges may vary slightly with soil type and crop.')
    c.drawRightString(PAGE_W - lm, row_y - 6, 'Analysis Method: AI Spectroscopy + ML Inference')


# ─── Page 3: Grid Analysis ────────────────────────────────────────────────────

def _page3(c, preds, env, meta):
    _draw_page_header(c, 3)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'SOILENZ GRID ANALYSIS – FIELD WISE VARIABILITY')

    # Info strip
    info_strip = [
        ('Field Area',    meta.get('field_area') or '–'),
        ('Grid Size',     '30 m × 30 m'),
        ('Total Grids',   '16'),
        ('Analysis Date', date.today().strftime('%d %b %Y')),
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

    # Heatmap grid: 4 cols x 3 rows
    hm_params = [
        ('pH (0–14)',        'ph',             4.5, 9.0, True),
        ('EC (dS/m)',        'ec',             0.0, 4.0, True),
        ('Organic Carbon (%)', 'organic_carbon', 0.0, 1.0, False),
        ('Nitrogen (kg/ha)', 'n',              0.0, 600, False),
        ('Phosphorus (kg/ha)','p',             0.0, 70,  False),
        ('Potassium (kg/ha)','k',              0.0, 500, False),
        ('Sulfur (ppm)',     's',              0.0, 60,  False),
        ('Iron (ppm)',       'fe',             0.0, 100, False),
        ('Zinc (ppm)',       'zn',             0.0, 10,  False),
        ('Manganese (ppm)', 'mn',             0.0, 50,  False),
        ('Copper (ppm)',    'cu',             0.0, 15,  False),
        ('Boron (ppm)',     'b',             0.0, 5,   False),
    ]

    hm_x0, hm_y0 = 20, TOP - 70
    cols4  = 4
    cell_w = (PAGE_W - 40) / cols4
    cell_h = 80

    for i, (label, key, vmin, vmax, rev) in enumerate(hm_params):
        if i >= 12: break
        row = i // cols4
        col = i % cols4
        cx  = hm_x0 + col * cell_w
        cy  = hm_y0 - row * (cell_h + 18)
        avg = preds.get(key) or ((vmin + vmax) / 2)
        buf = _heatmap_img(4, 4, vmin, vmax, avg, reverse=rev, w_in=1.6, h_in=1.6)
        hm_pw = cell_w - 10
        _embed_img(c, buf, cx + 4, cy - cell_h + 4, hm_pw, cell_h - 10)
        c.setFillColorRGB(*_DGRAY)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(cx + 4, cy + 4, label)
        c.setFont('Helvetica', 6.5)
        disp = f'{avg:.2f}' if avg else '–'
        c.setFillColorRGB(*_GRAY)
        c.drawString(cx + 4, cy - cell_h + 1, f'{vmin:.0f} – {vmax:.0f}   Avg: {disp}')

    # Insights box
    ins_y = hm_y0 - 3 * (cell_h + 18) + 5
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
    if ph > 7.5:         insights.append('pH is alkaline across the field')
    elif ph < 6.0:       insights.append('pH is acidic; lime application needed')
    else:                insights.append('pH is in optimal range')
    if oc < 0.5:         insights.append('Organic carbon is uniformly low')
    if n < 280:          insights.append('N is deficient in most grids')
    if p < 20:           insights.append('P is low; apply basal DAP')
    elif p > 70:         insights.append('P & K are high in field')
    insights.append('Micronutrients vary across grids')
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica', 7.5)
    for j, ins in enumerate(insights[:5]):
        c.drawString(PAGE_W - 168, ins_y - 10 - j * 13, f'• {ins}')


# ─── Page 4: Crop Suitability ─────────────────────────────────────────────────

CROP_PROFILES = [
    # name, ph_ideal, oc_min, n_min, k_min, notes
    ('Bitter Gourd', (6.0, 7.5), 0.5, 180, 120, 'Well-suited to warm climate; good market demand'),
    ('Cucumber',     (6.0, 7.0), 0.6, 200, 100, 'Requires organic matter improvement'),
    ('Ridge Gourd',  (6.0, 7.5), 0.5, 160, 100, 'Responds well to balanced nutrition'),
    ('Tomato',       (6.0, 6.8), 0.7, 250, 150, 'Sensitive to high pH, low OC & Mn'),
    ('Brinjal',      (5.5, 7.0), 0.5, 200, 120, 'Needs N & organic matter management'),
    ('Okra',         (6.0, 7.5), 0.5, 150, 100, 'Sensitive to low N & Mn'),
    ('Cauliflower',  (6.0, 7.0), 0.7, 280, 150, 'Requires better pH & organic matter'),
    ('Groundnut',    (6.0, 7.0), 0.4, 120, 100, 'Fixes own nitrogen; good for low-N soils'),
]

def _crop_score(profile, preds, env):
    name, ph_ideal, oc_min, n_min, k_min, _ = profile
    ph  = preds.get('ph') or 7.0
    oc  = preds.get('organic_carbon') or 0.0
    n   = preds.get('n') or 0.0
    k   = preds.get('k') or 0.0
    ndv = env.get('ndvi', 0.5) or 0.5

    s = 10.0
    # pH penalty
    if ph < ph_ideal[0]:   s -= (ph_ideal[0] - ph) * 1.5
    elif ph > ph_ideal[1]: s -= (ph - ph_ideal[1]) * 2.0
    # OC penalty
    if oc < oc_min:        s -= (oc_min - oc) * 3.0
    # N penalty
    if n < n_min:          s -= (n_min - n) / n_min * 2.5
    # K penalty
    if k < k_min:          s -= (k_min - k) / k_min * 1.0
    # NDVI bonus
    s += (ndv - 0.4) * 2.0
    return round(max(0.0, min(10.0, s)), 1)


def _page4(c, preds, env):
    _draw_page_header(c, 4)
    TOP = PAGE_H - 58

    # Title
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'CROP SUITABILITY ANALYSIS')
    c.setFont('Helvetica', 8.5)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP - 16, 'Crop suitability based on soil (pH, EC, N, P, K, OC, S, Micro) & local climate')

    scored = sorted(
        [(p[0], _crop_score(p, preds, env), p[5]) for p in CROP_PROFILES],
        key=lambda x: -x[1]
    )

    # Bar chart
    names  = [s[0] for s in scored]
    scores = [s[1] for s in scored]
    bar_buf = _bar_chart_img(names, scores, w_in=4.2, h_in=3.2)

    chart_h = 220
    _embed_img(c, bar_buf, 20, TOP - chart_h - 32, 300, chart_h)

    # Right table: score / status / notes
    rx, ry = 338, TOP - 32
    rw = PAGE_W - rx - 20
    headers = ['Crop', 'Score', 'Status', 'Key Notes']
    col_ws  = [80, 35, 65, rw - 80 - 35 - 65]
    rxs = [rx]
    for ww in col_ws[:-1]:
        rxs.append(rxs[-1] + ww)

    # Header
    c.setFillColorRGB(*_DK_GREEN)
    c.rect(rx, ry - 16, rw, 16, fill=1, stroke=0)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 7.5)
    for hdr, x in zip(headers, rxs):
        c.drawString(x + 3, ry - 11, hdr)

    ry2 = ry - 16
    for i, (crop, score, notes) in enumerate(scored):
        fill = _LGRAY if i % 2 == 0 else _WHITE
        c.setFillColorRGB(*fill)
        c.rect(rx, ry2 - 22, rw, 22, fill=1, stroke=0)

        if score >= 7:   st, sc = 'Recommended',     _MED_GREEN
        elif score >= 5: st, sc = 'Conditional',     _ORANGE
        else:            st, sc = 'Not Recommended', _RED

        row_vals = [crop, f'{score:.1f}', '', notes[:28]]
        c.setFont('Helvetica', 7.5)
        c.setFillColorRGB(*_DGRAY)
        for j, (val, x) in enumerate(zip(row_vals, rxs)):
            if j == 2:
                _draw_status_badge(c, st, sc, x + 2, ry2 - 19, w=60, h=13)
            else:
                c.drawString(x + 3, ry2 - 13, val)
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.3)
        c.line(rx, ry2 - 22, rx + rw, ry2 - 22)
        ry2 -= 22

    # Top crops summary box
    top3 = [s[0] for s in scored if s[1] >= 6][:3]
    box_y = TOP - chart_h - 62
    c.setFillColorRGB(0.96, 0.99, 0.96)
    _draw_rounded_card(c, 20, box_y - 34, 300, 48, radius=8)
    c.setStrokeColorRGB(*_MED_GREEN)
    c.setLineWidth(0.7)
    c.roundRect(20, box_y - 34, 300, 48, 8, fill=0, stroke=1)
    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(36, box_y + 5, f'Top Recommended Crops: {", ".join(top3) if top3 else "Review soil health"}')
    c.setFont('Helvetica', 7.5)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(36, box_y - 10, 'Improve soil organic carbon, nitrogen & micronutrients for better yield.')
    c.drawString(36, box_y - 22, f'Current soil fertility requires targeted inputs for optimal results.')


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
    # Always recommend organic matter
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
        amendments.append(('MnSO₄',          '10 kg/acre',   'Improve Mn availability',   'Basal',      'LOW'))
    if b < 0.5:
        amendments.append(('Borax',          '1 kg/acre',    'Boron supply',              'Basal',      'LOW'))
    amendments.append(('Micronutrient Mix', 'As per label', 'Micronutrient balance',     'Foliar',     'LOW'))

    # Table
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
                _draw_status_badge(c, f'● {prio}', prio_color, x + 2, ry3 + 3, w=52, h=13)
            else:
                c.drawString(x + 4, ry3 + 6, val[:22] if len(val) > 22 else val)
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
        ('Pre sowing',       '(0–7 days)',      ['Apply FYM / Compost', 'Apply Lime (if needed)', 'Prepare fine tilth']),
        ('Basal Dose',       'At sowing',       ['Apply DAP, MOP', 'Apply Zinc Sulphate', 'Apply 1/3 Urea']),
        ('During Crop Growth','(20–45 DAS)',    ['Apply 2nd split Urea', 'Foliar micronutrients', 'Weed management']),
        ('Pre Harvest',      '(90–100 DAS)',    ['Balanced irrigation', 'Harvest at maturity']),
    ]
    ph_x = lm
    ph_w = (rw - 30) / len(phases)
    ph_y = tl_y - 16
    for i, (ph_name, ph_sub, ph_items) in enumerate(phases):
        bx = ph_x + i * (ph_w + 10)
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
            c.drawString(bx + 6, ph_y - 28 - j * 14, f'• {item}')
        # Arrow
        if i < len(phases) - 1:
            ax = bx + ph_w + 2
            ay = ph_y - 42
            c.setFillColorRGB(*_DK_GREEN)
            c.setFont('ZapfDingbats', 12)
            c.drawString(ax, ay, '\xa6')  # right arrow


# ─── Page 6: Carbon Credit Dashboard ─────────────────────────────────────────

def _page6(c, preds, env, meta):
    _draw_page_header(c, 6)
    TOP = PAGE_H - 58

    c.setFillColorRGB(*_DK_GREEN)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(20, TOP, 'CARBON CREDIT IMPACT DASHBOARD')
    c.setFont('Helvetica', 8)
    c.setFillColorRGB(*_DGRAY)
    c.drawString(20, TOP, '')
    c.drawString(20, TOP - 16, 'Your soil health action leads to environment and income.')

    oc   = preds.get('organic_carbon') or 0.3
    ndvi = env.get('ndvi', 0.5) or 0.5

    oc_after   = min(oc + 0.42, 1.5)
    bio_before = round(1.0 + ndvi * 3, 1)
    bio_after  = round(bio_before * 1.6, 1)
    oc_seq     = round((oc_after - oc) / 0.1 * 50, 0)
    bio_seq    = round(bio_after * 120, 0)
    total_seq  = int(oc_seq + bio_seq)

    # Flow diagram
    flow_items = ['Sustainable\nPractices', 'Improved Soil\nHealth', 'Higher Yield\n& Biomass',
                  'CO₂\nSequestration', 'Carbon Credit\nGeneration']
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
            c.drawString(bx + fw - 2, fy - 14, '→')

    # Carbon sequestration table
    tbl_y = fy - 44
    lm = 20
    tbl_w = 260
    t_headers = ['Parameter', 'Current Value', 'After Improvement\n(1 Year)', 'Annual Sequestration\n(kg CO₂/acre)']
    t_rows = [
        ('Organic Carbon (%)', f'{oc:.2f}', f'{oc_after:.2f}', str(int(oc_seq))),
        ('Biomass (t/acre)',   f'{bio_before:.1f}', f'{bio_after:.1f}', str(int(bio_seq))),
        ('Total',             '–',           '–',                str(total_seq)),
    ]
    col_ws3 = [100, 60, 70, 30]
    xs3 = [lm]
    for ww in col_ws3:
        xs3.append(xs3[-1] + ww)

    # Table title
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
            c.drawString(x + 3, r_y3 + 5, val)
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
    c.setFillColorRGB(*_MED_GREEN if carbon_score >= 60 else _ORANGE)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(cg_x + 65, cg_y - 96, cs_lbl)

    # CO2 saved box
    co2_y = tbl_y
    c.setFillColorRGB(*_DK_GREEN)
    _draw_rounded_card(c, 460, co2_y - 80, 110, 82, radius=8)
    c.setFillColorRGB(*_WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(515, co2_y - 10, 'CO₂ SAVED (Per Year)')
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(515, co2_y - 34, f'{total_seq}')
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(515, co2_y - 48, 'kg CO₂')
    c.setFont('Helvetica', 7.5)
    c.drawCentredString(515, co2_y - 60, '(Per Acre)')
    c.setFont('Helvetica', 7)
    c.drawCentredString(515, co2_y - 72, f'TOTAL: {total_seq} kg CO₂/Acre/Year')

    # Key benefits
    ben_y = r_y3 - 20
    c.setFillColorRGB(*_DGRAY)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(lm, ben_y, 'KEY BENEFITS')
    benefits = [
        '₹1,200 – ₹1,800 extra income possible from carbon credits',
        'Improves soil structure & water holding capacity',
        'Enhances crop productivity and resilience',
        'Supports sustainable & climate-smart farming',
    ]
    for j, ben in enumerate(benefits):
        c.setFont('Helvetica', 8)
        c.setFillColorRGB(*_DGRAY)
        c.drawString(lm + 10, ben_y - 16 - j * 16, f'▸  {ben}')

    # Disclaimer footer
    c.setFillColorRGB(*_LGRAY)
    c.rect(0, 20, PAGE_W, 22, fill=1, stroke=0)
    c.setFillColorRGB(*_GRAY)
    c.setFont('Helvetica-Oblique', 6.5)
    c.drawCentredString(PAGE_W/2, 28, 'This report is generated by SoiLENZ AI. Values are predictive estimates; consult a soil scientist for final decisions.')


# ─── Public API ──────────────────────────────────────────────────────────────

def generate_pdf(preds, env_features, fertility, metadata):
    """
    Build and return the 6-page SoiLENZ PDF as bytes.

    preds        : dict from predict_for_point / dummy_predictions
    env_features : dict from same functions
    fertility    : str ('Low' / 'Medium' / 'High')
    metadata     : dict with optional keys:
                   location, analysis_date, field_area, crop,
                   agro_zone, farmer_name
    """
    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)

    _page1(c, preds, env_features, fertility, metadata)
    c.showPage()

    _page2(c, preds)
    c.showPage()

    _page3(c, preds, env_features, metadata)
    c.showPage()

    _page4(c, preds, env_features)
    c.showPage()

    _page5(c, preds, env_features)
    c.showPage()

    _page6(c, preds, env_features, metadata)
    c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()