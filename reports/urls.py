from django.urls import path
from . import views

urlpatterns = [
    path('crop-recommendation-pdf/',       views.download_recommendation_pdf, name='crop-recommendation-pdf'),
    path('soil-report/',                   views.soil_report_html,            name='soil-report-html'),
    path('soil-report-pdf/',               views.soil_report_pdf,             name='soil-report-pdf'),
]