from django.db import models

class PaymentTransaction(models.Model):
    txn_id = models.CharField(max_length=100, unique=True)
    payment_id = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("created", "Created"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="created"
    )

    amount = models.IntegerField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)

    raw_event = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

