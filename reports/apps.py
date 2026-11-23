from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'
    # Builder phrases for `manage.py seed_translations` (translations app).
    translation_catalog = 'reports.i18n.live_catalog'
