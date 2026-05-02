"""
Shared utilities for all per-device mobile API files.

Every device API that WRITES data must call `check_threshold(device)` before saving.
If the threshold is exceeded it returns a ready-made 403 Response — the caller
should return it immediately.  If None is returned the write is allowed.
"""
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status

from agriapp.models import (
    DeviseApis, DeviseApisFields, APICountThreshold,
)
from devise_apis.mobile_serializers import (
    FieldsReadingSerializer,
    FieldsReadingCreateSerializer,
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
    """Returns the Devise for request.user, raises Http404 otherwise."""
    from agriapp.models import Devise
    return get_object_or_404(Devise, pk=device_id, user=request.user)


# ── Generic FieldsReading view logic (used by atmo_sense, soil_life, ph_bottle) ──

def fields_list_view(request, device_id):
    """Paginated list of DeviseApisFields for a device."""
    device    = get_user_device(request, device_id)
    qs        = DeviseApisFields.objects.filter(device=device).order_by('-created_at')
    paginator = DevicePagination()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(FieldsReadingSerializer(page, many=True).data)


def fields_create_view(request, device_id):
    """Create a DeviseApisFields record after checking the threshold."""
    device = get_user_device(request, device_id)
    blocked = check_threshold(device)
    if blocked:
        return blocked
    serializer = FieldsReadingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    reading = serializer.save(device=device)
    return Response(FieldsReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


def fields_detail_view(request, device_id, call_id):
    """Return one DeviseApisFields record."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(FieldsReadingSerializer(reading).data)