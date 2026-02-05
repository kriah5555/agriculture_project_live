import json
import hmac
import base64
import hashlib
import razorpay

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import PaymentTransaction

client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_SECRET_KEY))

def is_admin(user):
    return user.is_staff or user.is_superuser

@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return JsonResponse({
            "ack": True,
            "status": "ignored",
            "message": "Only POST accepted"
        })

    payload   = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    # Parse event safely
    event = json.loads(payload.decode("utf-8"))
    event_type = event.get("event")

    payment = event.get("payload", {}).get("payment", {}).get("entity", {})
    pay_id  = payment.get("id")
    amount  = payment.get("amount")

    # ---- Signature check ----
    if not signature:
        return JsonResponse({
            "ack": True,
            "event": event_type,
            "pay_id": pay_id,
            "amount": amount,
            "status": "ignored",
            "message": "Missing signature"
        })

    expected_signature = base64.b64encode(
        hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).digest()
    ).decode()

    if not hmac.compare_digest(expected_signature, signature):
        return JsonResponse({
            "ack": True,
            "event": event_type,
            "pay_id": pay_id,
            "amount": amount,
            "status": "ignored",
            "message": "Invalid signature"
        })

    # ---- Fetch payment ----
    try:
        full_payment = client.payment.fetch(pay_id)
    except Exception:
        return JsonResponse({
            "ack": True,
            "event": event_type,
            "pay_id": pay_id,
            "amount": amount,
            "status": "ignored",
            "message": "Unable to fetch payment"
        })

    txn_id = full_payment.get("notes", {}).get("txn_id")

    if not txn_id:
        return JsonResponse({
            "ack": True,
            "event": event_type,
            "pay_id": pay_id,
            "amount": amount,
            "status": "ignored",
            "message": "txn_id missing"
        })

    obj, _ = PaymentTransaction.objects.get_or_create(
        txn_id=txn_id,
        defaults={"raw_event": event}
    )

    # ================= SUCCESS =================
    if event_type == "payment.captured":
        if obj.status in ("success", "failed"):
            return JsonResponse({
                "ack": True,
                "event": event_type,
                "txn_id": txn_id,
                "pay_id": pay_id,
                "amount": amount,
                "status": "ignored",
                "message": f"Already processed as {obj.status}"
            })

        obj.payment_id = pay_id
        obj.amount     = amount
        obj.status     = "success"
        obj.raw_event  = event
        obj.save()

        return JsonResponse({
            "ack": True,
            "event": event_type,
            "txn_id": txn_id,
            "pay_id": pay_id,
            "amount": amount,
            "status": "success",
            "message": "Payment captured and saved"
        })

    # ================= FAILED =================
    if event_type == "payment.failed":
        if obj.status == "success":
            return JsonResponse({
                "ack": True,
                "event": event_type,
                "txn_id": txn_id,
                "pay_id": pay_id,
                "amount": amount,
                "status": "ignored",
                "message": "Already marked success"
            })

        obj.payment_id     = pay_id
        obj.amount         = amount
        obj.status         = "failed"
        obj.failure_reason = payment.get("error_description")
        obj.raw_event      = event
        obj.save()

        return JsonResponse({
            "ack": True,
            "event": event_type,
            "txn_id": txn_id,
            "pay_id": pay_id,
            "amount": amount,
            "status": "failed",
            "message": "Payment failed"
        })

    # ================= UNKNOWN =================
    return JsonResponse({
        "ack": True,
        "event": event_type,
        "txn_id": txn_id,
        "pay_id": pay_id,
        "amount": amount,
        "status": "ignored",
        "message": "Event not handled"
    })

@login_required
@user_passes_test(is_admin)
def payment_list(request):
    payments = PaymentTransaction.objects.order_by("-created_at")
    return render(request, "razorpay/payment_list.html", {
        "payments": payments
    })
