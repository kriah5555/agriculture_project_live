from . import api


class LanguageMiddleware:
    """Sets request.current_language (a cached language object) from ?lang=
    — URL-driven only, otherwise the default language. Also clears the
    legacy `report_lang` cookie that used to pin a language per browser."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = api.language_from_request(request)
        request.current_language = api.get_language(code) or api.default_language()
        response = self.get_response(request)
        if api.LEGACY_LANG_COOKIE in request.COOKIES:
            response.delete_cookie(api.LEGACY_LANG_COOKIE)
        return response
