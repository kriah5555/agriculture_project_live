from . import api


def languages(request):
    """current_language, languages (active, ordered) and lang_code for templates."""
    current = getattr(request, 'current_language', None) or api.get_language(
        api.language_from_request(request)) or api.default_language()
    return {
        'current_language': current,
        'lang_code': current.code,
        'languages': api.active_languages(),
    }
