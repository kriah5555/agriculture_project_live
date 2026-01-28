from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import os

def version_upload_path(instance, filename):
    # media/updaet_versions/versions/app_v1.0.0.zip
    return f"updaet_versions/versions/{filename}"

class AppVersion(models.Model):
    version     = models.CharField(max_length=50,unique=True)
    zip_file    = models.FileField(upload_to=version_upload_path)
    description = models.TextField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.version

@receiver(post_delete, sender=AppVersion)
def delete_zip_file_on_delete(sender, instance, **kwargs):
    if instance.zip_file:
        if os.path.isfile(instance.zip_file.path):
            os.remove(instance.zip_file.path)