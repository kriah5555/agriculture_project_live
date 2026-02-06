from django.db import models

class PaymentTransaction(models.Model):
    txn_id = models.CharField( max_length=100, unique=True, null=True, blank=True)
    amount = models.IntegerField( null=True, blank=True)
    status = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )
    payment_id = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )
    raw_event = models.JSONField(
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True
    )

