from django.urls import path
from .views import create_payment, webhook, status, payment_list

urlpatterns = [
    
    path("create/", create_payment),

    path("webhook/", webhook),

    path("status/<str:txn_id>/", status),

    path("payments/", payment_list, name="payment-list"),
]
