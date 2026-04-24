"""
Shared utilities for all per-device mobile API files.

Every device API that WRITES data must call `check_threshold(device)` before saving.
If the threshold is exceeded it returns a ready-made 403 Response — the caller
should return it immediately.  If None is returned the write is allowed.
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status

from agriapp.models import (
    DeviseApis, DeviseApisFields, APICountThreshold,
)


# ── Threshold check ───────────────────────────────────────────────────────────

def check_threshold(device):
    """
    Returns a 403 Response if the device has exceeded its API call red-limit,
    or None if the write is allowed.

    Usage in any view that saves a reading:
        blocked = check_threshold(device)
        if blocked:
            return blocked
        # ... proceed with save
    """
    threshold = APICountThreshold.objects.filter(devise=device).first()
    if not threshold:
        return None  # no threshold configured → always allow

    if device.devise_type == 'soilsaathi':
        current = DeviseApis.objects.filter(device=device).count()
    else:
        current = DeviseApisFields.objects.filter(device=device).count()

    if current >= threshold.red:
        return Response(
            {
                'detail'   : 'API call limit reached for this device. Please contact the admin.',
                'limit'    : threshold.red,
                'current'  : current,
                'device_id': device.id,
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ── Shared paginator ──────────────────────────────────────────────────────────

class DevicePagination(PageNumberPagination):
    page_size             = 50
    page_size_query_param = 'per_page'
    max_page_size         = 200

    def get_paginated_response(self, data):
        return Response({
            'count'      : self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'page'       : self.page.number,
            'per_page'   : self.get_page_size(self.request),
            'next'       : self.get_next_link(),
            'previous'   : self.get_previous_link(),
            'results'    : data,
        })


# ── Auth helper ───────────────────────────────────────────────────────────────

def get_user_device(request, device_id):
    """
    Returns the Devise object only if it belongs to request.user.
    Raises Http404 otherwise.
    """
    from django.shortcuts import get_object_or_404
    from agriapp.models import Devise
    return get_object_or_404(Devise, pk=device_id, user=request.user)