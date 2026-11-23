"""Seed the default languages (en, kn, hi) and every app's translation_seed/
strings. Insert-only, so re-running never overwrites admin edits; new strings
added later are picked up by `manage.py seed_translations`."""
from django.db import migrations


def seed(apps, schema_editor):
    from translations.seeding import seed_languages, seed_strings
    Language = apps.get_model('translations', 'Language')
    TranslationString = apps.get_model('translations', 'TranslationString')
    Translation = apps.get_model('translations', 'Translation')
    seed_languages(Language)
    seed_strings(Language, TranslationString, Translation, include_live=False)


class Migration(migrations.Migration):
    dependencies = [('translations', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
