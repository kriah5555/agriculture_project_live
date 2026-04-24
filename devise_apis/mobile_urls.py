"""
Mobile API URL configuration.
All routes are prefixed with /api/mobile/ from the root urls.py.

Endpoint summary
────────────────
Auth                                               (auth_api.py)
  POST  /api/mobile/auth/login/                Login → access + refresh tokens
  POST  /api/mobile/auth/refresh/              Get new access token
  POST  /api/mobile/auth/logout/               Blacklist refresh token
  POST  /api/mobile/auth/forgot-password/      Forgot password → notifies admin (no auth)

Device types  (requires auth)                      (mobile_api.py)
  GET   /api/mobile/device-types/         All types + lock status per user

Devices       (requires auth)                      (mobile_api.py)
  GET   /api/mobile/devices/              List user devices (?type=soilsaathi)
  GET   /api/mobile/devices/<id>/         Device details
  GET   /api/mobile/devices/<id>/location/ Device GPS location

API calls     (requires auth)                      (mobile_api.py — routes internally by device type)
  GET   /api/mobile/devices/<id>/api-calls/          Paginated readings list
  POST  /api/mobile/devices/<id>/api-calls/create/   Create a new reading
  GET   /api/mobile/devices/<id>/api-calls/<cid>/    Single reading detail

Thresholds    (requires auth)                      (mobile_api.py)
  GET   /api/mobile/devices/<id>/threshold/          Get threshold
  POST  /api/mobile/devices/<id>/threshold/set/      Set/update threshold

Recommendations (requires auth, SoiLENZ only)      (mobile_api.py)
  GET   /api/mobile/devices/<id>/recommendations/    Fertilizer recommendations

Account       (requires auth)                      (mobile_api.py / auth_api.py)
  GET   /api/mobile/account/profile/               Get profile
  PATCH /api/mobile/account/profile/update/        Update profile
  POST  /api/mobile/account/change-password-request/  Notify admin of password change
"""
from django.urls import path
from . import mobile_api as m
from . import auth_api   as a

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('auth/login/',   a.MobileLoginView.as_view(),   name='mobile_login'),
    path('auth/refresh/', a.MobileRefreshView.as_view(), name='mobile_refresh'),
    path('auth/logout/',  a.mobile_logout,               name='mobile_logout'),

    # ── Device types ──────────────────────────────────────────────────────────
    path('device-types/', m.device_types, name='mobile_device_types'),

    # ── Devices ───────────────────────────────────────────────────────────────
    path('devices/',                             m.device_list,     name='mobile_device_list'),
    path('devices/<int:device_id>/',             m.device_detail,   name='mobile_device_detail'),
    path('devices/<int:device_id>/location/',    m.device_location, name='mobile_device_location'),

    # ── API calls (readings) ──────────────────────────────────────────────────
    path('devices/<int:device_id>/api-calls/', m.api_call_list,   name='mobile_api_call_list'),
    path('devices/<int:device_id>/api-calls/create/', m.api_call_create, name='mobile_api_call_create'),
    path('devices/<int:device_id>/api-calls/<int:call_id>/', m.api_call_detail, name='mobile_api_call_detail'),

    # ── Thresholds ────────────────────────────────────────────────────────────
    path('devices/<int:device_id>/threshold/', m.device_threshold,     name='mobile_threshold_get'),
    path('devices/<int:device_id>/threshold/set/', m.device_threshold_set, name='mobile_threshold_set'),

    # ── Recommendations ───────────────────────────────────────────────────────
    path('devices/<int:device_id>/recommendations/', m.device_recommendations, name='mobile_recommendations'),

    # ── Account ───────────────────────────────────────────────────────────────
    path('account/profile/',         m.account_profile,         name='mobile_profile'),
    path('account/profile/update/',  m.account_profile_update,  name='mobile_profile_update'),

    # ── Password requests (notify admin) ──────────────────────────────────────
    path('auth/forgot-password/',            a.forgot_password_request, name='mobile_forgot_password'),
    path('account/change-password-request/', a.change_password_request, name='mobile_change_password_request'),
]