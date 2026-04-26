from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Devise, APICountThreshold


@receiver(post_save, sender=Devise)
def create_threshold_for_new_device(sender, instance, created, **kwargs):
    """Auto-create an APICountThreshold with sensible defaults when a new Devise is saved."""
    if created:
        APICountThreshold.objects.get_or_create(
            devise=instance,
            defaults={'red': 100, 'orange': 80, 'blue': 50, 'green': 20},
        )