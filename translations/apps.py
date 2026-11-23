from django.apps import AppConfig


class TranslationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'translations'
    verbose_name = 'Translations'

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from . import api
        from .models import Language, Translation, TranslationString

        def _invalidate(**kwargs):
            api.invalidate()

        for model in (Language, Translation, TranslationString):
            post_save.connect(_invalidate, sender=model, dispatch_uid=f'tr_inv_save_{model.__name__}')
            post_delete.connect(_invalidate, sender=model, dispatch_uid=f'tr_inv_del_{model.__name__}')
