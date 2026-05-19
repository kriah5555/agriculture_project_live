from django.urls import path
from . import views

urlpatterns = [
    path('crop-recommendation-dashboard/', views.get_recommendation,         name='crop-recommendation-dashboard/'),
    path('crop-recommendation-pdf/',       views.download_recommendation_pdf, name='crop-recommendation-pdf'),
]
