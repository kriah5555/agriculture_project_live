import json
import hmac
import hashlib
import razorpay

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .models import PaymentTransaction

client = razorpay.Client(
    auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_SECRET_KEY)
)

@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return HttpResponse("Only POST allowed", status=405)

    payload   = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        return HttpResponse("Missing signature", status=400)

    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        return HttpResponse("Invalid signature", status=400)

    event = json.loads(payload.decode("utf-8"))
    event_type = event.get("event")

    print("[EVENT]", event_type)

    # ================= SUCCESS =================
    if event_type == "payment.captured":
        payment = event["payload"]["payment"]["entity"]
        pay_id  = payment["id"]

        try:
            full_payment = client.payment.fetch(pay_id)
        except Exception as e:
            print("[ERROR] Razorpay fetch failed:", e)
            return HttpResponse("OK")

        txn_id = full_payment.get("notes", {}).get("txn_id")
        if not txn_id:
            print("[FATAL] txn_id missing")
            return HttpResponse("OK")

        obj, created = PaymentTransaction.objects.get_or_create(
            txn_id=txn_id,
            defaults={"raw_event": event}
        )

        # do not overwrite final state
        if obj.status in ("success", "failed"):
            return HttpResponse("OK")

        obj.payment_id = pay_id
        obj.amount = payment.get("amount")
        obj.status = "success"
        obj.raw_event = event
        obj.save()

    # ================= FAILED =================
    elif event_type == "payment.failed":
        payment = event["payload"]["payment"]["entity"]
        pay_id = payment["id"]

        try:
            full_payment = client.payment.fetch(pay_id)
        except Exception as e:
            print("[ERROR] Razorpay fetch failed:", e)
            return HttpResponse("OK")

        txn_id = full_payment.get("notes", {}).get("txn_id")
        if not txn_id:
            return HttpResponse("OK")

        obj, created = PaymentTransaction.objects.get_or_create(
            txn_id=txn_id,
            defaults={"raw_event": event}
        )

        if obj.status == "success":
            return HttpResponse("OK")

        obj.payment_id = pay_id
        obj.status = "failed"
        obj.failure_reason = payment.get("error_description")
        obj.raw_event = event
        obj.save()

    return HttpResponse("OK")
