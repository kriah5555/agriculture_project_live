"""
JSON endpoint for the public website's forms (templates/website/*: "Book a demo",
enquiry / quote / partner forms). The page posts here with Django's CSRF token,
and every enquiry lands in the same place as the old homepage "Contact Us" form:

  * Soil Partner enquiries -> UserRequest(type=soil_partner_interest)
  * everything else (contact, quote, school, demo booking) -> ContactDetails

Both appear in the admin Notifications page.
"""
import json
import re

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ContactDetails, UserRequest

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _clean(value, max_len=200):
    return str(value or "").strip()[:max_len]


def _compose(kind_label, extra, message):
    """One readable message: '[Type] key: value · key: value — message'."""
    parts = [f"{k}: {v}" for k, v in extra if v]
    head = f"[{kind_label}]" + (" " + " · ".join(parts) if parts else "")
    return f"{head} — {message}" if message else head


def _enquiry_type(kind, audience):
    """Label for the design's enquiry forms (kind = partner | proposal | message)."""
    if audience == "soil-partner":
        return "Soil Partner pack request" if kind == "partner" else "Soil Partner message"
    if audience == "general":
        return "Product enquiry / quote request" if kind == "partner" else "Website message"
    return {"partner": "School partnership request", "proposal": "School proposal request"}.get(kind, "Website message")


@require_POST
def website_enquiry(request):
    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid request"}, status=400)

    name  = _clean(body.get("name"), 120)
    phone = _clean(body.get("phone"), 20)
    email = _clean(body.get("email"), 160)
    if not name or not phone or not email:
        return JsonResponse({"ok": False, "error": "Please add your name, phone number and email."}, status=400)
    if not _EMAIL_RE.match(email):
        return JsonResponse({"ok": False, "error": "Please enter a valid email."}, status=400)

    kind_label = _clean(body.get("type"), 60) or _enquiry_type(_clean(body.get("kind"), 20), _clean(body.get("audience"), 20))
    message    = _clean(body.get("message"), 2000)
    extra = [
        ("Role",         _clean(body.get("role"), 80)),
        ("Organisation", _clean(body.get("organisation"), 160)),
        ("Org type",     _clean(body.get("orgType"), 80)),
        ("City",         _clean(body.get("city"), 120)),
        ("Location",     _clean(body.get("location"), 160)),
        ("Students",     _clean(body.get("students"), 20)),
        ("Start",        _clean(body.get("start"), 40)),
        ("Demo date",    _clean(body.get("date"), 20)),
        ("Page",         _clean(body.get("page"), 120)),
    ]
    full_message = _compose(kind_label, extra, message)

    # Soil Partner interest -> same table as /soil-partner-enquiry/
    if _clean(body.get("audience"), 20) == "soil-partner":
        UserRequest.objects.create(
            user=None,
            username=name,
            email=email,
            phone=phone,
            request_type=UserRequest.SOIL_PARTNER_INTEREST,
            message=full_message[:500],
        )
        return JsonResponse({"ok": True})

    # Contact / quote / school / demo -> ContactDetails (mail & phone are unique,
    # so a repeat visitor updates their existing row and it becomes unread again).
    msg = full_message[:255]
    existing = ContactDetails.objects.filter(Q(mail__iexact=email) | Q(phone=phone)).order_by("-created_at").first()
    try:
        with transaction.atomic():
            if existing:
                existing.name, existing.message, existing.status = name, msg, True
                existing.mail, existing.phone = email, phone
                existing.save()
                ContactDetails.objects.filter(pk=existing.pk).update(created_at=timezone.now())
            else:
                ContactDetails.objects.create(name=name, mail=email, phone=phone, message=msg)
    except IntegrityError:
        # email matches one row and phone another: keep the row's phone, note the new one
        if existing is None:
            return JsonResponse({"ok": False, "error": "Could not save right now"}, status=409)
        msg = f"(phone {phone}) {full_message}"[:255]
        ContactDetails.objects.filter(pk=existing.pk).update(
            name=name, message=msg, status=True, created_at=timezone.now()
        )
    return JsonResponse({"ok": True})
