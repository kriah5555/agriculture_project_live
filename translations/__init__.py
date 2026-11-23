"""App-wide translatable strings (see translations/api.py).

    from translations import get_text, get_strings
"""


def get_text(key, lang=None, **values):
    from .api import get_text as _get_text
    return _get_text(key, lang, **values)


def get_strings(module, lang=None):
    from .api import get_strings as _get_strings
    return _get_strings(module, lang)
