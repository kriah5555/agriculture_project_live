from django.core.management.base import BaseCommand

from translations import api
from translations.models import Language, Translation, TranslationString
from translations.seeding import seed_languages, seed_strings


class Command(BaseCommand):
    help = ('Insert missing languages, strings and translations from every app\'s '
            'translation_seed/ (and live catalogues). Never modifies existing rows.')

    def handle(self, *args, **opts):
        langs = seed_languages(Language)
        strings, translations = seed_strings(Language, TranslationString, Translation, include_live=True)
        api.invalidate()
        self.stdout.write(self.style.SUCCESS(
            f'Created {langs} languages, {strings} strings, {translations} translations '
            f'({TranslationString.objects.count()} strings total).'))
