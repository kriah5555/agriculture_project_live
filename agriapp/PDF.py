
from .models import ContactDetails, Devise, DeviseApis, APICountThreshold, ColumnName, DeviseLocation, DeviseApisFields, SOIL_LIFE_FIELDS, ATMO_SENSE_FIELDS, SOIL_SAATHI_FIELDS

from . import UserFunctions
from django.views.generic import UpdateView, TemplateView, CreateView, View
from django.urls import reverse
from django.contrib import messages #import messages
from datetime import datetime
from map.views import get_marker_color
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

def draw_gauge(value, label):
    fig, ax = plt.subplots(figsize=(2.5, 1.5))
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-0.3, 1.2)
    ax.axis('off')

    # Semicircle border
    theta = np.linspace(0, np.pi, 100)
    ax.plot(np.cos(theta), np.sin(theta), color='black', linewidth=1.2)

    # Tick marks and numbers
    for i in range(0, 15):
        angle_deg = (i / 14) * 180
        angle_rad = np.radians(180 - angle_deg)
        x = 0.9 * np.cos(angle_rad)
        y = 0.9 * np.sin(angle_rad)
        ax.plot([0.8 * np.cos(angle_rad), x], [0.8 * np.sin(angle_rad), y], color='gray', linewidth=0.5)

        lx = 1.05 * np.cos(angle_rad)
        ly = 1.05 * np.sin(angle_rad)
        ax.text(lx, ly, str(i), fontsize=6, ha='center', va='center')

    # Needle
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

def download_api_response_pdf(request, **kwargs):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Logo
    logo_path = os.path.join(os.getcwd(), 'static/logo.PNG')
    c.drawImage(logo_path, 450, 780, width=100, height=40)

    # Header and Address
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "ArkaShine Innovations Pvt Ltd")

    c.setFont("Helvetica", 9)
    c.drawString(50, 785, "Address : H. NO.9.1 2-226, 11th Cross, Bhawani Rice Mill Road")
    c.drawString(50, 772, "Vidyanagar colony, Bidar, Karnataka, India, 585403")

    if 'pk' in kwargs:
        api = DeviseApis.objects.get(pk=kwargs['pk'])
        location = DeviseLocation.objects.filter(devise=api.device).first()

        # General Info Box
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.rect(45, 695, 500, 60, stroke=1, fill=0)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, 740, f"Area name : {api.area_name}")
        c.drawString(50, 725, f"API call time : {api.created_at}")
        c.drawString(50, 710, f"Crop : {api.crop_type}")
        c.drawString(320, 740, f"Latitude : {location.latitude if location else ''}")
        c.drawString(320, 725, f"Longitude : {location.longitude if location else ''}")
        c.drawString(320, 710, f"Phone : +91 9611297893")

        # Gauges
        c.rect(45, 580, 500, 120, stroke=1, fill=0)
        ph_gauge = draw_gauge(api.ph, "pH")
        ec_gauge = draw_gauge(api.ec, "EC")
        c.drawImage(ph_gauge, 100, 600, width=150, height=100)
        c.drawImage(ec_gauge, 300, 600, width=150, height=100)
        c.setFont("Helvetica", 10)
        c.drawCentredString(175, 590, f"pH Value: {api.ph}")
        c.drawCentredString(375, 590, f"EC Value: {api.ec}")

        # Soil Parameters Table
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, 550, "Soil Parameter Details")

        table_data = [
            ("Organic Carbon as OC (0.51–0.75)", "%", api.oc),
            ("Phosphorus as P (11–25)", "Kg/acre", api.phosphorous),
            ("Potassium K (60–120)", "Kg/acre", api.potassium),
            ("Calcium as Ca (>300)", "mg/kg", api.calcium),
            ("Magnesium as Mg (>120)", "mg/kg", api.magnesium),
            ("Sulphur as S >10", "mg/kg", api.sulphur),
            ("Boron", "mg/kg", api.boron),
            ("Zinc as Zn (1.00)", "mg/kg", api.zinc),
            ("Iron as Fe (24.50)", "mg/kg", api.iron),
            ("Copper as Cu (1.20)", "mg/kg", api.copper),
            ("Manganese as Mn", "mg/kg", api.manganese),
            ("Nitrogen", "", api.nitrogen),
            ("Phosphorous", "", api.phosphorous),
            ("Molybdenum", "", api.molybdenum),
            ("Chlorine", "", api.chlorine),
            ("Nickel", "", api.nickel),
        ]

        full_table_data = [["Parameters", "Unit", "Value"]] + table_data
        table = Table(full_table_data, colWidths=[240, 100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        frame = Frame(45, 180, 500, 350, showBoundary=1)
        frame.addFromList([table], c)

        # Fertilizer Recommendation Section
        from reportlab.platypus import Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        styles = getSampleStyleSheet()
        crops_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(
            api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type
        )

        elements = []
        title_text = f'<b>THE RECOMMENDED DOSES OF FERTILIZER FOR CROP "{api.crop_type.upper()}" ARE:</b>'
        elements.append(Spacer(-1, 0))
        elements.append(Paragraph(title_text, styles['Heading4']))

        crop_fertilizer = crops_data.get('crop_fertilizer', [])
        if crop_fertilizer:
            fert_table_data = [["Recommendation"]]
            for crop_fertilizer_data in crop_fertilizer:
                for crop_data in crop_fertilizer_data:
                    fert_table_data.append([crop_data])

            fert_table = Table(fert_table_data, colWidths=[500])
            fert_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(fert_table)
        else:
            elements.append(Paragraph('No fertilizer data available.', styles['Normal']))

        # Optional FYM section (can be activated when needed)
        # fym_data = crops_data.get('fym', [])
        # if fym_data:
        #     elements.append(Paragraph('<b>Remedy, Fertility, FYM and Target Yield</b>', styles['Heading4']))
        #     fym_table_data = [["Details"]] + [[fym] for crop_fym_data in fym_data for fym in crop_fym_data]
        #     fym_table = Table(fym_table_data, colWidths=[500])
        #     fym_table.setStyle(TableStyle([
        #         ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
        #         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        #         ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        #         ('FONTSIZE', (0, 0), (-1, -1), 9),
        #         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        #         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        #     ]))
        #     elements.append(fym_table)

        extra_frame = Frame(45, 20, 500, 200, showBoundary=0)
        extra_frame.addFromList(elements, c)
    else:
        c.drawString(50, 700, "No data available")

    c.showPage()
    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="recommended.pdf")
