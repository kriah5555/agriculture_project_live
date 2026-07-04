"""
Real (non-mock) data aggregation for the experimental Admin Overview
dashboard (agriapp/admin_overview_dashboard.html). Kept out of views.py so
the whole feature is easy to isolate or remove if it isn't kept after review.

Every number here comes from an existing model (Farmer, Devise, DeviseApis,
DeviseApisFields, DeviseLocation, APICountThreshold, UserRequest,
ContactDetails, PartnerPayment) — nothing is hardcoded/sample data.
"""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import (
    Farmer, Devise, DeviseApis, DeviseApisFields, DeviseLocation,
    APICountThreshold, UserRequest, ContactDetails, PartnerPayment,
    DEVICE_NAMES,
)
from .dashboard_utils import (
    month_buckets as _month_buckets,
    month_labels as _labels_for,
    fill_monthly as _fill_monthly,
    trend_fields as _trend_fields,
    format_inr_short as _format_inr_short,
    format_count_short as _format_count_short,
)

# Device types that actually record readings (matches the match/case logic
# already used in views.userPage for per-device api_used counts).
MODULE_TYPES = ['soilsaathi', 'atmo_sense', 'soil_life', 'ph_bottle', 'leaflenz']

# All device types the platform sells (agriapp.models.DEVICE_CHOICES). Every
# one of these EXCEPT carbon_credits has real, queryable usage rows — carbon
# credit calculations are computed on demand and never written to the DB
# (see devise_apis/devices/carbon_credits.py), so it's called out as
# "not tracked yet" rather than shown as a fabricated zero.
ALL_DEVICE_TYPES = ['soilsaathi', 'atmo_sense', 'soil_life', 'ph_bottle', 'soil_map', 'leaflenz', 'carbon_credits']
UNTRACKED_DEVICE_TYPES = {'carbon_credits'}

ALERT_SEVERITY_BY_REQUEST_TYPE = {
    UserRequest.USAGE_LIMIT_REACHED  : ('danger',  'fa-circle-exclamation'),
    UserRequest.USAGE_WARNING        : ('warning', 'fa-triangle-exclamation'),
    UserRequest.SOIL_PARTNER_INTEREST: ('info',    'fa-inbox'),
    UserRequest.FORGOT_PASSWORD      : ('info',    'fa-key'),
    UserRequest.CHANGE_PASSWORD      : ('info',    'fa-key'),
}


def _module_reading_qs(devise_type, since=None):
    qs = (
        DeviseApis.objects.filter(device__devise_type=devise_type)
        if devise_type == 'soilsaathi'
        else DeviseApisFields.objects.filter(device__devise_type=devise_type)
    )
    return qs.filter(created_at__gte=since) if since else qs


def build_overview_context():
    now               = timezone.now()
    last_30           = now - timedelta(days=30)
    prev_30_start     = now - timedelta(days=60)
    twelve_months_ago = now - timedelta(days=365)
    six_months_ago    = now - timedelta(days=182)

    # ---------------- KPIs ----------------
    total_farmers = Farmer.objects.count()
    total_devices = Devise.objects.count()

    farmers_last_30 = Farmer.objects.filter(created_at__gte=last_30).count()
    farmers_prev_30 = Farmer.objects.filter(created_at__gte=prev_30_start, created_at__lt=last_30).count()

    devices_last_30 = Devise.objects.filter(created_at__gte=last_30).count()
    devices_prev_30 = Devise.objects.filter(created_at__gte=prev_30_start, created_at__lt=last_30).count()

    active_device_ids = set(
        DeviseApis.objects.filter(created_at__gte=last_30).values_list('device_id', flat=True)
    ) | set(
        DeviseApisFields.objects.filter(created_at__gte=last_30).values_list('device_id', flat=True)
    )
    active_devices  = len(active_device_ids)
    offline_devices = max(total_devices - active_devices, 0)

    api_calls_last_30 = (
        DeviseApis.objects.filter(created_at__gte=last_30).count()
        + DeviseApisFields.objects.filter(created_at__gte=last_30).count()
    )
    api_calls_prev_30 = (
        DeviseApis.objects.filter(created_at__gte=prev_30_start, created_at__lt=last_30).count()
        + DeviseApisFields.objects.filter(created_at__gte=prev_30_start, created_at__lt=last_30).count()
    )

    revenue_last_30 = float(PartnerPayment.objects.filter(status='paid', created_at__gte=last_30).aggregate(total=Sum('amount'))['total'] or 0)
    revenue_prev_30 = float(PartnerPayment.objects.filter(status='paid', created_at__gte=prev_30_start, created_at__lt=last_30).aggregate(total=Sum('amount'))['total'] or 0)

    needs_attention = UserRequest.objects.filter(status=UserRequest.STATUS_PENDING).count()

    kpis = {
        'total_farmers'       : total_farmers,
        'total_devices'       : total_devices,
        'active_devices'      : active_devices,
        'active_pct'          : round(active_devices / total_devices * 100) if total_devices else 0,
        'api_calls_30d'       : api_calls_last_30,
        'api_calls_30d_display': _format_count_short(api_calls_last_30),
        'revenue_30d_display' : _format_inr_short(revenue_last_30),
        'needs_attention'     : needs_attention,
        'offline_devices'     : offline_devices,
    }
    kpis.update(_trend_fields('farmers', farmers_last_30, farmers_prev_30))
    kpis.update(_trend_fields('devices', devices_last_30, devices_prev_30))
    kpis.update(_trend_fields('api_calls', api_calls_last_30, api_calls_prev_30))
    kpis.update(_trend_fields('revenue', revenue_last_30, revenue_prev_30))

    # ---------------- Platform growth (12 months) ----------------
    buckets_12 = _month_buckets(12)
    farmers_by_month = (
        Farmer.objects.filter(created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(count=Count('id')).order_by('month')
    )
    devices_by_month = (
        Devise.objects.filter(created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(count=Count('id')).order_by('month')
    )
    growth = {
        'labels' : _labels_for(buckets_12),
        'farmers': _fill_monthly(farmers_by_month, buckets_12),
        'devices': _fill_monthly(devices_by_month, buckets_12),
    }

    # 12-month API-calls series, used only for the KPI sparkline (rise/fall at a glance)
    api_calls_by_month = (
        DeviseApis.objects.filter(created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(count=Count('id')).order_by('month')
    )
    api_calls_fields_by_month = (
        DeviseApisFields.objects.filter(created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(count=Count('id')).order_by('month')
    )
    api_calls_series = [
        a + b for a, b in zip(
            _fill_monthly(api_calls_by_month, buckets_12),
            _fill_monthly(api_calls_fields_by_month, buckets_12),
        )
    ]

    # 12-month distinct-active-device-per-month series, for the "Active
    # Devices" KPI sparkline. Two bulk queries (not one per month/device).
    from collections import defaultdict
    active_sets = defaultdict(set)
    for row in DeviseApis.objects.filter(created_at__gte=twelve_months_ago).annotate(month=TruncMonth('created_at')).values('month', 'device_id'):
        active_sets[(row['month'].year, row['month'].month)].add(row['device_id'])
    for row in DeviseApisFields.objects.filter(created_at__gte=twelve_months_ago).annotate(month=TruncMonth('created_at')).values('month', 'device_id'):
        active_sets[(row['month'].year, row['month'].month)].add(row['device_id'])
    active_devices_series = [len(active_sets.get(b, set())) for b in buckets_12]

    sparklines = {
        'farmers'       : growth['farmers'],
        'devices'       : growth['devices'],
        'api_calls'     : api_calls_series,
        'active_devices': active_devices_series,
    }

    # ---------------- Users & soil partners ----------------
    total_users        = User.objects.filter(is_superuser=False).count()
    soil_partners_count = User.objects.filter(profile__user_type='soil_partner').count()
    regular_users_count = User.objects.filter(is_superuser=False).exclude(profile__user_type='soil_partner').count()
    total_api_calls_all_time = DeviseApis.objects.count() + DeviseApisFields.objects.count()
    users_summary = {
        'total_users'        : total_users,
        'soil_partners_count': soil_partners_count,
        'regular_users_count': regular_users_count,
        'total_api_calls_all_time_display': _format_count_short(total_api_calls_all_time),
    }

    # ---------------- Usage by user type (soil-partner-managed farmer
    # readings vs a device owner using it directly), per module type ----
    # DeviseApis/DeviseApisFields.farmer is set when a reading was recorded
    # against a Farmer (who always belongs to a soil partner) — null means
    # the reading was recorded directly against the device's own owner.
    usage_by_user_type_series = {'partner': [], 'direct': []}
    usage_by_user_type_labels = []
    for devise_type in MODULE_TYPES:
        base_qs = _module_reading_qs(devise_type)
        partner_count = base_qs.filter(farmer__isnull=False).count()
        direct_count  = base_qs.filter(farmer__isnull=True).count()
        if partner_count or direct_count:
            usage_by_user_type_labels.append(DEVICE_NAMES.get(devise_type, devise_type))
            usage_by_user_type_series['partner'].append(partner_count)
            usage_by_user_type_series['direct'].append(direct_count)
    usage_by_user_type = {
        'labels' : usage_by_user_type_labels,
        'partner': usage_by_user_type_series['partner'],
        'direct' : usage_by_user_type_series['direct'],
    }

    # ---------------- Device distribution ----------------
    dist_rows = list(Devise.objects.values('devise_type').annotate(count=Count('id')).order_by('-count'))
    device_distribution = {
        'labels': [DEVICE_NAMES.get(r['devise_type'], r['devise_type']) for r in dist_rows],
        'data'  : [r['count'] for r in dist_rows],
    }
    device_counts = [
        {'type': DEVICE_NAMES.get(r['devise_type'], r['devise_type']), 'count': r['count']}
        for r in dist_rows
    ]

    # ---------------- API calls by module (6 months) ----------------
    buckets_6 = _month_buckets(6)
    module_series = []
    for devise_type in MODULE_TYPES:
        rows = (
            _module_reading_qs(devise_type, since=six_months_ago)
            .annotate(month=TruncMonth('created_at')).values('month')
            .annotate(count=Count('id')).order_by('month')
        )
        counts = _fill_monthly(rows, buckets_6)
        if any(counts) or Devise.objects.filter(devise_type=devise_type).exists():
            module_series.append({'label': DEVICE_NAMES.get(devise_type, devise_type), 'data': counts})
    module_calls = {'labels': _labels_for(buckets_6), 'series': module_series}

    # ---------------- Fleet-wide API quota usage ----------------
    # A DB signal auto-creates an APICountThreshold for every device, so this
    # set is effectively "all devices" — computing per-device usage with a
    # query-per-device loop here would be an N+1 that scales with fleet size
    # and can make the whole app unresponsive on a real (non-trivial) device
    # count. Use two bulk aggregates instead: O(1) queries regardless of N.
    total_quota = APICountThreshold.objects.aggregate(total=Sum('red'))['total'] or 0
    soilsaathi_ids = APICountThreshold.objects.filter(devise__devise_type='soilsaathi').values_list('devise_id', flat=True)
    other_ids = APICountThreshold.objects.filter(
        devise__devise_type__in=['atmo_sense', 'soil_life', 'ph_bottle', 'leaflenz']
    ).values_list('devise_id', flat=True)
    total_used = (
        DeviseApis.objects.filter(device_id__in=soilsaathi_ids).count()
        + DeviseApisFields.objects.filter(device_id__in=other_ids).count()
    )
    quota_pct = round(total_used / total_quota * 100) if total_quota else 0

    # ---------------- Revenue trend (12 months, paid vs pending) ----------------
    paid_by_month = (
        PartnerPayment.objects.filter(status='paid', created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(total=Sum('amount')).order_by('month')
    )
    pending_by_month = (
        PartnerPayment.objects.filter(status='pending', created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(total=Sum('amount')).order_by('month')
    )
    revenue_trend = {
        'labels' : _labels_for(buckets_12),
        'paid'   : [float(v) for v in _fill_monthly(paid_by_month, buckets_12, value_key='total')],
        'pending': [float(v) for v in _fill_monthly(pending_by_month, buckets_12, value_key='total')],
    }
    sparklines['revenue'] = revenue_trend['paid']

    # ---------------- Top soil partners by paid revenue ----------------
    partner_rows = list(
        PartnerPayment.objects.filter(status='paid')
        .values('user__username', 'user__first_name', 'user__last_name')
        .annotate(total=Sum('amount')).order_by('-total')[:5]
    )
    max_partner_total = max((float(r['total']) for r in partner_rows), default=0)
    top_partners = [
        {
            'name' : (f"{r['user__first_name']} {r['user__last_name']}".strip() or r['user__username']),
            'total': float(r['total']),
            'pct'  : round(float(r['total']) / max_partner_total * 100) if max_partner_total else 0,
        }
        for r in partner_rows
    ]

    # ---------------- Pending payment aging ----------------
    pending_payments_qs   = PartnerPayment.objects.filter(status='pending')
    pending_over_30_count = pending_payments_qs.filter(created_at__lt=last_30).count()
    oldest_pending        = pending_payments_qs.order_by('created_at').first()
    oldest_pending_days   = (now - oldest_pending.created_at).days if oldest_pending else 0

    # ---------------- Device type usage — lifetime, all types ----------------
    # Answers "which device type is used more / less, and which isn't used
    # at all". carbon_credits is flagged as untracked rather than shown as a
    # fabricated 0 — it's computed on demand and never persisted anywhere.
    device_usage_rows = []
    for devise_type in ALL_DEVICE_TYPES:
        count = 0 if devise_type in UNTRACKED_DEVICE_TYPES else _module_reading_qs(devise_type).count()
        device_usage_rows.append({
            'type'   : DEVICE_NAMES.get(devise_type, devise_type),
            'count'  : count,
            'tracked': devise_type not in UNTRACKED_DEVICE_TYPES,
        })
    device_usage_rows.sort(key=lambda d: d['count'], reverse=True)
    max_usage = max((d['count'] for d in device_usage_rows), default=0)
    for d in device_usage_rows:
        d['pct'] = round(d['count'] / max_usage * 100) if max_usage else 0
    device_usage = device_usage_rows
    device_usage_chart = {
        'labels'  : [d['type'] for d in device_usage_rows],
        'data'    : [d['count'] for d in device_usage_rows],
        'tracked' : [d['tracked'] for d in device_usage_rows],
    }

    # ---------------- Device activation status ----------------
    linked_devices          = Devise.objects.filter(user__isnull=False).count()
    unlinked_devices        = total_devices - linked_devices
    thresholded_devices     = APICountThreshold.objects.values('devise').distinct().count()
    not_thresholded_devices = max(total_devices - thresholded_devices, 0)
    activation_status = {
        'linked_devices'         : linked_devices,
        'unlinked_devices'       : unlinked_devices,
        'thresholded_devices'    : thresholded_devices,
        'not_thresholded_devices': not_thresholded_devices,
    }

    # ---------------- AI recommendations (LeafLenz disease scans) ----------------
    # Fertilizer-dose and carbon-credit recommendations are computed live and
    # never saved (see agriapp/FertilizerCalculation.py, devise_apis/devices/
    # carbon_credits.py) — there is no historical count to show for those.
    # LeafLenz IS persisted (DeviseApisFields.tag = predicted label,
    # field1 = confidence), so that's the one real "AI recommendations made"
    # number we can report.
    leaflenz_scans_qs = DeviseApisFields.objects.filter(device__devise_type='leaflenz')
    leaflenz_scan_count = leaflenz_scans_qs.count()
    diagnosis_rows = list(
        leaflenz_scans_qs.exclude(tag__isnull=True).exclude(tag='')
        .values('tag').annotate(count=Count('id')).order_by('-count')[:5]
    )
    max_diagnosis = max((r['count'] for r in diagnosis_rows), default=0)
    top_diagnoses = [
        {
            'label': r['tag'],
            'count': r['count'],
            'pct'  : round(r['count'] / max_diagnosis * 100) if max_diagnosis else 0,
        }
        for r in diagnosis_rows
    ]
    ai_recommendations = {
        'leaflenz_scan_count': leaflenz_scan_count,
        'top_diagnoses'      : top_diagnoses,
    }

    # ---------------- Payments summary (lifetime, prominent KPIs) ----------------
    payments_agg = PartnerPayment.objects.aggregate(
        total_paid       = Sum('amount', filter=Q(status='paid')),
        total_pending    = Sum('amount', filter=Q(status='pending')),
        distinct_partners= Count('user', distinct=True),
        total_count      = Count('id'),
        paid_count       = Count('id', filter=Q(status='paid')),
        pending_count    = Count('id', filter=Q(status='pending')),
    )
    total_paid_amt = float(payments_agg['total_paid'] or 0)
    payments_summary = {
        'total_paid_display'   : _format_inr_short(total_paid_amt),
        'total_pending_display': _format_inr_short(float(payments_agg['total_pending'] or 0)),
        'paid_count'           : payments_agg['paid_count'],
        'pending_count'        : payments_agg['pending_count'],
        'distinct_partners'    : payments_agg['distinct_partners'],
        'avg_payment_display'  : _format_inr_short(total_paid_amt / payments_agg['total_count']) if payments_agg['total_count'] else '₹0',
    }

    # ---------------- Top states (by registered farmers) ----------------
    state_rows = list(
        Farmer.objects.exclude(state='').values('state')
        .annotate(count=Count('id')).order_by('-count')[:5]
    )
    max_state_count = max((r['count'] for r in state_rows), default=0)
    top_states = [
        {
            'state': r['state'],
            'count': r['count'],
            'pct'  : round(r['count'] / max_state_count * 100) if max_state_count else 0,
        }
        for r in state_rows
    ]

    # ---------------- Device locations (map) ----------------
    devices_qs = list(Devise.objects.values('id', 'name', 'devise_type'))
    locations  = {loc.devise_id: (loc.latitude, loc.longitude) for loc in DeviseLocation.objects.all()}
    device_locations = []
    for d in devices_qs:
        latlng = locations.get(d['id'])
        if latlng:
            module_label = DEVICE_NAMES.get(d['devise_type'], d['devise_type'])
            device_locations.append({
                'name'        : d['name'] or module_label,
                'module_label': module_label,
                'latitude'    : latlng[0],
                'longitude'   : latlng[1],
            })

    # ---------------- Alerts (real pending items only) ----------------
    alerts = []
    for req in UserRequest.objects.filter(status=UserRequest.STATUS_PENDING).order_by('-created_at')[:6]:
        severity, icon = ALERT_SEVERITY_BY_REQUEST_TYPE.get(req.request_type, ('info', 'fa-circle-info'))
        alerts.append({
            'severity'  : severity,
            'icon'      : icon,
            'title'     : req.get_request_type_display(),
            'subtitle'  : req.message or req.username,
            'created_at': req.created_at,
        })
    pending_contacts = ContactDetails.objects.filter(status=True).count()
    if pending_contacts:
        alerts.append({
            'severity'  : 'info',
            'icon'      : 'fa-envelope',
            'title'     : f'{pending_contacts} unread contact message{"s" if pending_contacts != 1 else ""}',
            'subtitle'  : 'Awaiting review',
            'created_at': now,
        })
    if pending_over_30_count:
        alerts.append({
            'severity'  : 'warning',
            'icon'      : 'fa-hourglass-half',
            'title'     : f'{pending_over_30_count} pending payment{"s" if pending_over_30_count != 1 else ""} over 30 days old',
            'subtitle'  : f'Oldest pending payment: {oldest_pending_days}d',
            'created_at': now,
        })
    alerts.sort(key=lambda a: a['created_at'], reverse=True)

    # ---------------- Recent activity (merged feed) ----------------
    activity = []
    for f in Farmer.objects.order_by('-created_at')[:5]:
        activity.append({
            'date': f.created_at, 'actor': f.farmer_name, 'action': 'Farmer registered',
            'module': 'Farmer', 'status': f.get_status_display(),
            'status_class': 'success' if f.status == 'report_delivered' else 'info',
        })
    for p in PartnerPayment.objects.select_related('user').order_by('-created_at')[:5]:
        activity.append({
            'date': p.created_at, 'actor': p.user.username, 'action': f'Payment ₹{p.amount}',
            'module': 'Payments', 'status': p.get_status_display(),
            'status_class': 'success' if p.is_paid else 'warning',
        })
    for r in UserRequest.objects.order_by('-created_at')[:5]:
        activity.append({
            'date': r.created_at, 'actor': r.username or r.email, 'action': r.get_request_type_display(),
            'module': 'Requests', 'status': r.get_status_display(),
            'status_class': 'success' if r.status == UserRequest.STATUS_RESOLVED else 'danger',
        })
    for a in DeviseApis.objects.select_related('device').order_by('-created_at')[:5]:
        activity.append({
            'date': a.created_at, 'actor': a.device.name if a.device_id else a.devise_id,
            'action': 'Soil reading recorded', 'module': 'SoiLENZ',
            'status': 'Completed', 'status_class': 'success',
        })
    activity.sort(key=lambda x: x['date'], reverse=True)
    activity = activity[:10]

    return {
        'ov_kpis'                 : kpis,
        'ov_growth_json'          : json.dumps(growth, cls=DjangoJSONEncoder),
        'ov_device_dist_json'     : json.dumps(device_distribution, cls=DjangoJSONEncoder),
        'ov_module_calls_json'    : json.dumps(module_calls, cls=DjangoJSONEncoder),
        'ov_quota_pct'            : quota_pct,
        'ov_revenue_json'         : json.dumps(revenue_trend, cls=DjangoJSONEncoder),
        'ov_sparklines_json'      : json.dumps(sparklines, cls=DjangoJSONEncoder),
        'ov_device_counts'        : device_counts,
        'ov_device_usage_chart_json': json.dumps(device_usage_chart, cls=DjangoJSONEncoder),
        'ov_top_states'           : top_states,
        'ov_top_partners'         : top_partners,
        'ov_device_locations_json': json.dumps(device_locations, cls=DjangoJSONEncoder),
        'ov_alerts'               : alerts,
        'ov_activity'             : activity,
        'ov_device_usage'         : device_usage,
        'ov_activation'           : activation_status,
        'ov_ai'                   : ai_recommendations,
        'ov_payments'             : payments_summary,
        'ov_users'                : users_summary,
        'ov_usage_by_user_type_json': json.dumps(usage_by_user_type, cls=DjangoJSONEncoder),
    }