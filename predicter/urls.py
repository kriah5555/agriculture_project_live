from django.urls import path
from . import views

urlpatterns = [
    #path('api/predict/<int:api_id>/', views.get_recommendation, name='get_recommendation'),
    path('crop-recommendation-dashboard/', views.get_recommendation, name='dashboard'),
]
