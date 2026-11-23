"""
Lookup API for app-wide translations.

    from translations import get_text, get_strings
    get_text('report.title', 'kn')                      -> str
    get_text('report.kg_total_ha', 'hi', kg=12, area=2) -> str with {placeholders} filled
    get_strings('report', 'kn')                         -> {key: text} for one module

Fallback order: the requested language, then the default language, then the
key itself. Results are cached per process and per (module, language). The
cache is dropped immediately on save/delete in this process (signals) and,
for other worker processes, whenever the database version stamp changes —
checked at most every VERSION_CHECK_SECS — so edits reach every worker.

The language is URL-driven only (?lang=); there is no session/cookie
fallback, so a page without ?lang= always renders in the default language.
"""
import string
import threading
import time

VERSION_CHECK_SECS = 5
LEGACY_LANG_COOKIE = 'report_lang'   # old per-browser preference; now cleared

_lock = threading.Lock()
_state = {'version': None, 'checked': 0.0, 'strings': {}, 'languages': None}


# ── cache bookkeeping ─────────────────────────────────────────────────────────

def _db_version():
    from django.db.models import Count, Max
    from .models import Language, Translation, TranslationString
    s = TranslationString.objects.aggregate(m=Max('updated_at'), n=Count('id'))
    l = Language.objects.aggregate(m=Max('updated_at'), n=Count('id'))
    return (str(s['m']), s['n'], str(l['m']), l['n'], Translation.objects.count())


def _ensure_fresh():
    now = time.monotonic()
    if now - _state['checked'] < VERSION_CHECK_SECS and _state['version'] is not None:
        return
    try:
        version = _db_version()
    except Exception:          # tables not migrated yet
        version = ('unmigrated',)
    with _lock:
        if version != _state['version']:
            _state['strings'] = {}
            _state['languages'] = None
            _state['version'] = version
        _state['checked'] = now


def invalidate():
    with _lock:
        _state['strings'] = {}
        _state['languages'] = None
        _state['version'] = None
        _state['checked'] = 0.0


def version_stamp():
    """Changes whenever any string or language changes (e.g. for PDF cache keys)."""
    _ensure_fresh()
    return '|'.join(map(str, _state['version'] or ()))


# ── languages ─────────────────────────────────────────────────────────────────

class _Lang:
    """Plain, cache-safe copy of a Language row."""
    __slots__ = ('code', 'name', 'native_name', 'font_family', 'is_active', 'is_default', 'sort_order')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def __str__(self):
        return self.code

    def __repr__(self):
        return f'<Lang {self.code}>'


_FALLBACK_LANGS = [_Lang(code='en', name='English', native_name='English', font_family='',
                         is_active=True, is_default=True, sort_order=0)]


def _all_languages():
    _ensure_fresh()
    if _state['languages'] is None:
        try:
            from .models import Language
            rows = [_Lang(**{k: getattr(l, k) for k in _Lang.__slots__}) for l in Language.objects.all()]
        except Exception:
            rows = []
        _state['languages'] = rows or list(_FALLBACK_LANGS)
    return _state['languages']


def active_languages():
    return [l for l in _all_languages() if l.is_active]


def default_language():
    langs = _all_languages()
    for l in langs:
        if l.is_default:
            return l
    for l in langs:
        if l.code == 'en':
            return l
    return langs[0]


def default_language_code():
    return default_language().code


def get_language(code):
    """Active language for `code`, or None."""
    code = (code or '').strip().lower()
    for l in active_languages():
        if l.code == code:
            return l
    return None


def normalize_lang(code):
    """`code` if it is an active language, else the default language's code."""
    lang = get_language(code)
    return lang.code if lang else default_language_code()


def language_from_request(request):
    """URL-driven: ?lang= when valid and active, otherwise the default."""
    return normalize_lang(request.GET.get('lang'))


# ── strings ───────────────────────────────────────────────────────────────────

def _load_module(module):
    """{lang_code: {key: text}} for one module, straight from the database."""
    from .models import Translation
    out = {}
    rows = (Translation.objects.filter(string__module=module)
            .values_list('string__key', 'language__code', 'text'))
    for key, code, text in rows:
        if (text or '').strip():
            out.setdefault(code, {})[key] = text
    return out


def get_strings(module, lang=None):
    """{key: text} for every string of `module` in `lang`, with blanks
    filled from the default language."""
    _ensure_fresh()
    lang = normalize_lang(lang)
    ck = (module, lang)
    data = _state['strings'].get(ck)
    if data is not None:
        return data
    try:
        by_lang = _load_module(module)
    except Exception:
        by_lang = {}
    data = dict(by_lang.get(default_language_code(), {}))
    if lang != default_language_code():
        data.update(by_lang.get(lang, {}))
    with _lock:
        _state['strings'][ck] = data
    return data


class _Keep(dict):
    def __missing__(self, k):
        return '{' + k + '}'


def fmt(text, **values):
    """str.format that leaves unknown {placeholders} untouched."""
    if not values:
        return text
    try:
        return string.Formatter().vformat(text, (), _Keep(values))
    except (ValueError, IndexError):
        return text


def module_of(key):
    return (key or '').split('.', 1)[0]


def get_text(key, lang=None, **values):
    text = get_strings(module_of(key), lang).get(key, key)
    return fmt(text, **values)
