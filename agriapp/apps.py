from django.apps import AppConfig


class AgriappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agriapp'

    def ready(self):
        import agriapp.signals  # noqa: F401  — registers post_save signal
