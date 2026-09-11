from django.conf import settings

from .models import ContactDetails, UserRequest


def app_version(request):
    """Exposes APP_VERSION (settings.py) to every template, for the small
    version label shown next to the app name in the sidebar."""
    return {'app_version': getattr(settings, 'APP_VERSION', '')}


def notifications_badge(request):
    """
    Exposes `pending_notifications_count` to every template (via navbar.html)
    so the admin sidebar can show a badge for unread contact messages and
    pending user requests / usage alerts.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_superuser:
        return {}

    count = (
        ContactDetails.objects.filter(status=True).count()
        + UserRequest.objects.filter(status=UserRequest.STATUS_PENDING).count()
    )
    return {'pending_notifications_count': count}