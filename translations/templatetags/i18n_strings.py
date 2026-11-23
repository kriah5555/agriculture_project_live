"""
{% load i18n_strings %}

  {% t "report.title" %}
  {% t "report.kg_total_ha" kg=x area=y %}       placeholders, values escaped
  {% t "report.crop_summary_top" crops=c bold="crops" %}   wrap values in <strong>
  {% lang_url "kn" %}       current URL with ?lang=kn (drops partial/full flags)
  {% language_font_stack %} CSS font list of the active languages

The language comes from the template context: `lang`, else
`current_language` (context processor), else the default language.
"""
import re

from django import template
from django.http import QueryDict
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

from translations import api

register = template.Library()


def _lang(context):
    lang = context.get('lang') or context.get('lang_code') or context.get('current_language')
    return api.normalize_lang(str(lang) if lang else None)


@register.simple_tag(takes_context=True)
def t(context, key, bold='', **values):
    text = api.get_strings(api.module_of(key), _lang(context)).get(key, key)
    if not values:
        return text   # auto-escaped by the template engine
    bold_names = {b.strip() for b in str(bold).split(',') if b.strip()}
    safe = {}
    for name, value in values.items():
        v = conditional_escape('' if value is None else value)
        safe[name] = str(format_html('<strong>{}</strong>', v) if name in bold_names else v)
    return mark_safe(api.fmt(str(conditional_escape(text)), **safe))


@register.simple_tag(takes_context=True)
def lang_url(context, code):
    request = context.get('request')
    params = request.GET.copy() if request is not None else QueryDict(mutable=True)
    for flag in ('partial', 'full'):
        params.pop(flag, None)
    params['lang'] = code
    path = request.path if request is not None else ''
    return f'{path}?{params.urlencode()}'


def _css_font(name):
    """One family name from the DB, made safe for a CSS font-family list."""
    name = re.sub(r"[^\w \-]", '', name or '').strip()
    return f"'{name}'" if name else ''


@register.simple_tag
def language_font_stack():
    """e.g. 'Noto Sans Kannada', 'Noto Sans Devanagari' — or sans-serif."""
    fonts = []
    for lang in api.active_languages():
        for part in (lang.font_family or '').split(','):
            f = _css_font(part)
            if f and f not in fonts:
                fonts.append(f)
    return mark_safe(', '.join(fonts) or 'sans-serif')
