
from .models import ContactDetails, Devise, DeviseApis, APICountThreshold, ColumnName, DeviseLocation, DeviseApisFields, SOIL_LIFE_FIELDS, ATMO_SENSE_FIELDS, SOIL_SAATHI_FIELDS

from . import UserFunctions
from django.views.generic import UpdateView, TemplateView, CreateView, View
from django.urls import reverse
from django.contrib import messages
from datetime import datetime
from .views import get_marker_color
from django.contrib.auth.models import User, Group
from .devise_details import *
from .import FertilizerCalculation

from django.shortcuts import get_object_or_404
from django.conf import settings

from django.http import JsonResponse

from django.urls import reverse_lazy
from django import forms
from django.utils.timezone import localtime
import json
from django.core.serializers.json import DjangoJSONEncoder

# for pdf download
from django.http import FileResponse
import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import tempfile
import numpy as np
from reportlab.platypus import Table, TableStyle, Frame
import pytz


def draw_gauge(value, label):
    fig, ax = plt.subplots(figsize=(2.5, 1.5))
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-0.3, 1.2)
    ax.axis('off')

    theta = np.linspace(0, np.pi, 100)
    ax.plot(np.cos(theta), np.sin(theta), color='black', linewidth=1.2)

    for i in range(0, 15):
        angle_deg = (i / 14) * 180
        angle_rad = np.radians(180 - angle_deg)
        x = 0.9 * np.cos(angle_rad)
        y = 0.9 * np.sin(angle_rad)
        ax.plot([0.8 * np.cos(angle_rad), x], [0.8 * np.sin(angle_rad), y], color='gray', linewidth=0.5)
        lx = 1.05 * np.cos(angle_rad)
        ly = 1.05 * np.sin(angle_rad)
        ax.text(lx, ly, str(i), fontsize=6, ha='center', va='center')

    needle_angle = (value / 14) * 180
    rad = np.radians(180 - needle_angle)
    x = 0.8 * np.cos(rad)
    y = 0.8 * np.sin(rad)
    ax.plot([0, x], [0, y], color='red', linewidth=2)
    ax.text(0, -0.2, label, fontsize=9, ha='center')

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    fig.savefig(temp_file.name, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    return temp_file.name


def draw_nutrient_grid(api):
    """
    Generate a 3-row × 5-col pie chart grid.
    figsize=(15, 9) → each cell is exactly 3×3 inches → perfectly circular pies.
    PDF aspect ratio: 15/9 = 5/3 → draw at width=500, height=300 in the PDF.
    """
    nutrients = [
        ('Nitrogen\n(N)',    api.nitrogen,    560),
        ('Phosphorus\n(P)',  api.phosphorous,  56),
        ('Potassium\n(K)',   api.potassium,   336),
        ('Calcium\n(Ca)',    api.calcium,       4),
        ('Magnesium\n(Mg)', api.magnesium,      3),
        ('Sulfur\n(S)',      api.sulphur,       20),
        ('Iron\n(Fe)',       api.iron,         10.5),
        ('Manganese\n(Mn)', api.manganese,      9),
        ('Zinc\n(Zn)',       api.zinc,          0.6),
        ('Copper\n(Cu)',     api.copper,        1.0),
        ('Boron\n(B)',       api.boron,         0.5),
    ]

    # 2 rows × 6 cols = 12 slots; 11 nutrients + 1 empty
    # figsize=(18, 6) → each cell 3×3 inches → perfectly circular pies
    # PDF aspect ratio 18:6 = 3:1 → draw at width=500, height=167
    fig, axes = plt.subplots(2, 6, figsize=(18, 6))
    fig.patch.set_facecolor('white')
    axes_flat = axes.flatten()

    for idx, (label, value, max_val) in enumerate(nutrients):
        ax = axes_flat[idx]
        available = min(float(value), float(max_val))
        deficit   = max(float(max_val) - float(value), 0)
        total     = available + deficit
        if total == 0:
            available, deficit, total = 0, 1, 1

        pct_avail = (available / total) * 100

        ax.pie(
            [available, deficit],
            colors=['#3498db', '#FFC300'],
            startangle=90,
            wedgeprops={'edgecolor': 'white', 'linewidth': 1},
        )
        ax.set_aspect('equal')
        ax.set_title(f'{label}\n{value:.1f}', fontsize=9, pad=4, fontweight='bold')
        ax.text(0, -1.45, f'{pct_avail:.1f}%', ha='center', fontsize=8, color='#3498db')

    # Remove the 1 unused slot completely
    fig.delaxes(axes_flat[11])

    plt.tight_layout(pad=0.8, h_pad=1.5, w_pad=0.8)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    fig.savefig(temp_file.name, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return temp_file.name


def _draw_header(c):
    """Draw the ArkaShine logo in the top-right corner."""
    new_logo = os.path.join(os.getcwd(), 'static/arkashine_logo.png')
    old_logo = os.path.join(os.getcwd(), 'static/logo.PNG')
    logo_path = new_logo if os.path.exists(new_logo) else old_logo
    # A4 right edge = 595pt; logo 80×80 right-aligned with 15pt margin
    c.drawImage(logo_path, 500, 755, width=80, height=80, preserveAspectRatio=True, mask='auto')


def download_api_response_pdf(request, **kwargs):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    _draw_header(c)

    if 'pk' in kwargs:
        api      = DeviseApis.objects.get(pk=kwargs['pk'])
        location = DeviseLocation.objects.filter(devise=api.device).first()

        # ── Format time in IST ────────────────────────────────────────────────
        ist      = pytz.timezone('Asia/Kolkata')
        ist_time = api.created_at.astimezone(ist)
        formatted_time = ist_time.strftime('%d-%b-%Y %H:%M:%S IST')

        # ── General Info Box ──────────────────────────────────────────────────
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.rect(45, 715, 500, 60, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, 758, f"Area name       : {api.area_name}")
        c.drawString(50, 743, f"API call time   : {formatted_time}")
        c.drawString(50, 728, f"Crop            : {api.crop_type}")
        c.drawString(310, 758, f"Latitude  : {location.latitude if location else 'N/A'}")
        c.drawString(310, 743, f"Longitude : {location.longitude if location else 'N/A'}")
        c.drawString(310, 728, f"Phone     : +91 9611297893")

        # ── Gauges (pH & EC) ──────────────────────────────────────────────────
        c.rect(45, 600, 500, 110, stroke=1, fill=0)
        ph_gauge = draw_gauge(api.ph, "pH")
        ec_gauge = draw_gauge(api.ec, "EC")
        c.drawImage(ph_gauge, 100, 615, width=150, height=90)
        c.drawImage(ec_gauge, 300, 615, width=150, height=90)
        c.setFont("Helvetica", 10)
        c.drawCentredString(175, 607, f"pH Value: {api.ph}")
        c.drawCentredString(375, 607, f"EC Value: {api.ec}")

        # ── Soil Parameters Table ─────────────────────────────────────────────
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, 576, "Soil Parameter Details")

        table_data = [
            ("Nitrogen (N)",     "kg/ha",    round(api.nitrogen,    2)),
            ("Phosphorus (P)",   "kg/ha",    round(api.phosphorous, 2)),
            ("Potassium (K)",    "kg/ha",    round(api.potassium,   2)),
            ("Calcium (Ca)",     "meq/100g", round(api.calcium,     2)),
            ("Magnesium (Mg)",   "meq/100g", round(api.magnesium,   2)),
            ("Sulfur (S)",       "ppm",      round(api.sulphur,     2)),
            ("Iron (Fe)",        "ppm",      round(api.iron,        2)),
            ("Manganese (Mn)",   "ppm",      round(api.manganese,   2)),
            ("Zinc (Zn)",        "ppm",      round(api.zinc,        2)),
            ("Copper (Cu)",      "ppm",      round(api.copper,      2)),
            ("Boron (B)",        "ppm",      round(api.boron,       2)),
        ]

        full_table_data = [["Parameter", "Unit", "Value"]] + list(table_data)
        table = Table(full_table_data, colWidths=[260, 110, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0),  colors.HexColor('#1a2f6b')),
            ('TEXTCOLOR',   (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, -1), 9),
            ('GRID',        (0, 0), (-1, -1), 0.5, colors.black),
            ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4ff')]),
        ]))

        frame = Frame(45, 150, 500, 415, showBoundary=0)
        frame.addFromList([table], c)

    else:
        c.drawString(50, 700, "No data available")

    # ── Page 2: Soil Nutrient Grid ────────────────────────────────────────────
    if 'pk' in kwargs:
        c.showPage()
        _draw_header(c)

        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, 758, "Soil Nutrient Grid")

        # Legend (blue = available, yellow = deficit)
        c.setFillColor(colors.HexColor('#3498db'))
        c.rect(52, 738, 10, 10, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 8)
        c.drawString(65, 739, "Available")
        c.setFillColor(colors.HexColor('#FFC300'))
        c.rect(122, 738, 10, 10, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(135, 739, "Deficit")

        # 2×6 grid, figsize=(18,6) → aspect ratio 3:1
        # PDF: width=500, height=500*(6/18)=167
        grid_img = draw_nutrient_grid(api)
        c.drawImage(grid_img, 45, 520, width=500, height=167)

    c.showPage()
    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="soil_report.pdf")