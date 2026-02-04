from django.urls import path
from .views import razorpay_webhook, payment_list

urlpatterns = [
    path("razorpay/", razorpay_webhook, name="razorpay-webhook"),
    path("payments/", payment_list, name="payment-list"),
]
