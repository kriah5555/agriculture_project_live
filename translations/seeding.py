"""
Insert-only seeding of languages and strings. Never modifies existing rows,
so anything an admin edited is kept.

Any installed app can ship seed data in <app>/translation_seed/:
    catalog.json   {key: context-note}
    <code>.json    {key: text} per language (en.json, kn.json, hi.json …)
and may declare a live catalogue on its AppConfig:
    translation_catalog = 'reports.i18n.live_catalog'   # -> {key: (english, context)}
(used by the seed_translations command to pick up strings added in code).
"""
import json
import os

DEFAULT_LANGUAGES = [
    # code, name, native_name, font_family, is_default, sort_order
    ('en', 'English', 'English', '', True, 0),
    ('kn', 'Kannada', 'ಕನ್ನಡ', 'Noto Sans Kannada', False, 1),
    ('hi', 'Hindi', 'हिंदी', 'Noto Sans Devanagari', False, 2),
]


def seed_languages(Language):
    created = 0
    for code, name, native, font, is_default, order in DEFAULT_LANGUAGES:
        _obj, made = Language.objects.get_or_create(code=code, defaults=dict(
            name=name, native_name=native, font_family=font, is_active=True,
            is_default=is_default, sort_order=order))
        created += made
    return created


def _read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def seed_sources(include_live=False):
    """(catalog {key: context}, texts {lang: {key: text}}) from every app."""
    from django.apps import apps
    from django.utils.module_loading import import_string

    catalog, texts = {}, {}
    for cfg in apps.get_app_configs():
        folder = os.path.join(cfg.path, 'translation_seed')
        if os.path.isdir(folder):
            catalog.update(_read(os.path.join(folder, 'catalog.json')))
            for fn in sorted(os.listdir(folder)):
                if fn.endswith('.json') and fn != 'catalog.json':
                    texts.setdefault(fn[:-5], {}).update(_read(os.path.join(folder, fn)))
        hook = getattr(cfg, 'translation_catalog', None)
        if include_live and hook:
            for key, (en, ctx) in import_string(hook)().items():
                catalog.setdefault(key, ctx)
                texts.setdefault('en', {}).setdefault(key, en)
    return catalog, texts


def seed_strings(Language, TranslationString, Translation, include_live=False):
    """Create missing strings and missing (string, language) translations.
    Returns (strings_created, translations_created)."""
    catalog, texts = seed_sources(include_live)
    keys = set(catalog) | {k for per in texts.values() for k in per}
    existing = {s.key: s for s in TranslationString.objects.all()}
    new_strings = []
    for key in sorted(keys - set(existing)):
        s = TranslationString(key=key, module=key.split('.', 1)[0][:50], context=(catalog.get(key) or '')[:255])
        new_strings.append(s)
    TranslationString.objects.bulk_create(new_strings, batch_size=300)
    if new_strings:
        existing = {s.key: s for s in TranslationString.objects.all()}

    langs = {l.code: l for l in Language.objects.all()}
    default = next((l.code for l in langs.values() if l.is_default), 'en')
    have = set(Translation.objects.values_list('string_id', 'language_id'))
    new_tr = []
    for code, per in texts.items():
        lang = langs.get(code)
        if lang is None:
            continue
        for key, text in per.items():
            s = existing.get(key)
            if s is None or (s.pk, lang.pk) in have or not (text or '').strip():
                continue
            new_tr.append(Translation(string=s, language=lang, text=text, reviewed=(code == default)))
    Translation.objects.bulk_create(new_tr, batch_size=500)
    return len(new_strings), len(new_tr)


def seed_default(key, code):
    """The seeded text of `key` in language `code` (None if there is none)."""
    _catalog, texts = seed_sources(include_live=True)
    return texts.get(code, {}).get(key)
