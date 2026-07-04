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
    DeviseApis, DeviseApisFields, APICountThreshold, Farmer, UserRequest,
)
from devise_apis.mobile_serializers import (
    FieldsReadingSerializer,
    FieldsReadingCreateSerializer,
)


# ── Threshold check ───────────────────────────────────────────────────────────

def _raise_usage_alert(device, category, current_count, threshold_value):
    """
    Creates a pending UserRequest alert (usage_warning / usage_limit_reached) for
    the admin Notifications page, unless one of the same category is already
    pending for this device (avoids duplicate alerts on every subsequent call
    once a tier has been crossed).
    """
    already_pending = UserRequest.objects.filter(
        request_type=category, device=device, status=UserRequest.STATUS_PENDING,
    ).exists()
    if already_pending:
        return

    device_label = device.name or f'Device #{device.pk}'
    email = (device.user.email if device.user_id and device.user.email else device.email) or ''
    stage = 'is nearing its API call limit' if category == UserRequest.USAGE_WARNING else 'has reached its API call limit'
    UserRequest.objects.create(
        user         = device.user,
        device       = device,
        username     = device_label,
        email        = email,
        phone        = device.phone or '',
        request_type = category,
        message      = (
            f"Device '{device_label}' (ID {device.pk}) {stage}: "
            f"{current_count}/{threshold_value} API calls used. "
            f"Please review and update the device's usage limit."
        ),
    )


def check_threshold(device):
    """
    Returns a 403 Response if the device has exceeded its API call red-limit,
    or None if the write is allowed. Also raises an admin notification
    ('usage_warning' at the orange tier, 'usage_limit_reached' at/past the red
    tier) the first time each tier is crossed, so an admin can review and raise
    the device's limit.

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
        _raise_usage_alert(device, UserRequest.USAGE_LIMIT_REACHED, current, threshold.red)
        return Response(
            {
                'detail'   : 'API call limit reached for this device. Please contact the admin.',
                'limit'    : threshold.red,
                'current'  : current,
                'device_id': device.id,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # This call is allowed and will push the count to `current + 1` — raise an
    # alert now if that lands in the orange (warning) or red (limit reached) tier.
    new_count = current + 1
    if new_count >= threshold.red:
        _raise_usage_alert(device, UserRequest.USAGE_LIMIT_REACHED, new_count, threshold.red)
    elif new_count >= threshold.orange:
        _raise_usage_alert(device, UserRequest.USAGE_WARNING, new_count, threshold.orange)

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

def resolve_farmer(request, farmer_id):
    """
    Returns a Farmer instance if farmer_id is provided and belongs to the user,
    None if farmer_id is absent, or a 400/403 Response on error.
    Only soil partners and superusers may link readings to a farmer.
    """
    if not farmer_id:
        return None
    user = request.user
    if not user.is_superuser:
        try:
            is_partner = user.profile.user_type == 'soil_partner'
        except Exception:
            is_partner = False
        if not is_partner:
            return Response(
                {'detail': 'Only soil partners can link readings to a farmer.'},
                status=status.HTTP_403_FORBIDDEN,
            )
    try:
        farmer = Farmer.objects.get(pk=farmer_id)
    except Farmer.DoesNotExist:
        return Response({'detail': 'Farmer not found.'}, status=status.HTTP_400_BAD_REQUEST)
    if farmer.soil_partner_id != user.id and not user.is_superuser:
        return Response({'detail': 'You do not have access to this farmer.'}, status=status.HTTP_403_FORBIDDEN)
    return farmer


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
    ctx = {'request': request}
    return paginator.get_paginated_response(FieldsReadingSerializer(page, many=True, context=ctx).data)


def fields_create_view(request, device_id):
    """Create a DeviseApisFields record after checking the threshold."""
    device = get_user_device(request, device_id)
    blocked = check_threshold(device)
    if blocked:
        return blocked

    farmer = resolve_farmer(request, request.data.get('farmer_id'))
    if isinstance(farmer, Response):
        return farmer

    serializer = FieldsReadingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    reading = serializer.save(device=device, farmer=farmer)
    return Response(FieldsReadingSerializer(reading, context={'request': request}).data, status=status.HTTP_201_CREATED)


def fields_detail_view(request, device_id, call_id):
    """Return one DeviseApisFields record."""
    device  = get_user_device(request, device_id)
    reading = get_object_or_404(DeviseApisFields, pk=call_id, device=device)
    return Response(FieldsReadingSerializer(reading, context={'request': request}).data)