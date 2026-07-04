"""
Mobile API URL configuration.
All routes are prefixed with /api/mobile/ from the root urls.py.


Endpoint summary
────────────────
Auth                                               (auth_api.py)
  POST  /api/mobile/auth/register/             Register new user → access + refresh tokens
  POST  /api/mobile/auth/login/                Login → access + refresh tokens
  POST  /api/mobile/auth/refresh/              Get new access token
  POST  /api/mobile/auth/logout/               Blacklist refresh token
  POST  /api/mobile/auth/forgot-password/      Forgot password → notifies admin (no auth)
  POST  /api/mobile/auth/soil-partner-enquiry/ Express interest in becoming a soil partner (no auth)

Device types  (requires auth)                      (mobile_api.py)
  GET   /api/mobile/device-types/                        All types + lock status per user
  GET   /api/mobile/device-types/<type_key>/field-schema/ Field label map for a device type

Devices       (requires auth)                      (mobile_api.py)
  GET   /api/mobile/devices/              List user devices (?type=soilsaathi|atmo_sense|soil_life|ph_bottle)
  GET   /api/mobile/devices/<id>/         Device details
  GET   /api/mobile/devices/<id>/location/ Device GPS location

  NOTE: <id> is the integer primary key of the device, NOT the string devise_id field.

Generic API calls (all device types)               (mobile_api.py — routes internally by device type)
  GET   /api/mobile/devices/<id>/api-calls/          Paginated readings list
  POST  /api/mobile/devices/<id>/api-calls/create/   Create a new reading
  GET   /api/mobile/devices/<id>/api-calls/<cid>/    Single reading detail

SoiLENZ readings (soilsaathi)                      (devices/soilsaathi.py)
  GET   /api/mobile/devices/<id>/soilsaathi/              List readings
  POST  /api/mobile/devices/<id>/soilsaathi/create/       Create reading
  GET   /api/mobile/devices/<id>/soilsaathi/<cid>/            Single reading
  GET   /api/mobile/devices/<id>/soilsaathi/recommendations/  Fertilizer recommendations
  GET   /api/mobile/devices/<id>/soilsaathi/ai-recommendation/ AI crop recommendation (ML)
  GET   /api/mobile/devices/<id>/soilsaathi/<cid>/pdf/             Soil parameters PDF (api-overview report)
  GET   /api/mobile/devices/<id>/soilsaathi/<cid>/recommendation-pdf/  Full 6-page SoiLENZ PDF report

SoilSparsh readings (atmo_sense)                   (devices/atmo_sense.py)
  GET   /api/mobile/devices/<id>/atmo-sense/              List readings
  POST  /api/mobile/devices/<id>/atmo-sense/create/       Create reading
  GET   /api/mobile/devices/<id>/atmo-sense/<cid>/        Single reading

SoilLIFE readings (soil_life)                      (devices/soil_life.py)
  GET   /api/mobile/devices/<id>/soil-life/               List readings
  POST  /api/mobile/devices/<id>/soil-life/create/        Create reading
  GET   /api/mobile/devices/<id>/soil-life/<cid>/         Single reading

PHBottle readings (ph_bottle)                      (devices/ph_bottle.py)
  GET   /api/mobile/devices/<id>/ph-bottle/               List readings
  POST  /api/mobile/devices/<id>/ph-bottle/create/        Create reading
  GET   /api/mobile/devices/<id>/ph-bottle/<cid>/         Single reading

LeafLenz readings (leaflenz)                       (devices/leaflenz.py)
  GET   /api/mobile/devices/<id>/leaflenz/                List scans
  POST  /api/mobile/devices/<id>/leaflenz/scan/           Upload a leaf photo → ONNX prediction + save
  GET   /api/mobile/devices/<id>/leaflenz/<cid>/          Single scan (with disease info)
  GET   /api/mobile/devices/<id>/leaflenz/stats/          Total scans + plant distribution for a device
  GET   /api/mobile/leaflenz/diseases/                    Static disease encyclopedia (description/symptoms/treatment)

Account       (requires auth)                      (mobile_api.py / auth_api.py)
  GET   /api/mobile/account/profile/               Get profile
  PATCH /api/mobile/account/profile/update/        Update profile
  POST  /api/mobile/account/change-password-request/  Notify admin of password change
  GET   /api/mobile/account/payment-history/       My payment records (soil partner only)

Soil Map      (requires auth)                      (soilmap/views.py + services/views.py)
  POST  /api/mobile/soil-map/predict/              AI soil prediction for a lat/lon point or drawn polygon
                                                   Body: { lat, lon }  OR  { polygon: [[lat,lon], ...] }
                                                   Returns: fertility, soil chemistry (pH EC N P K OC S Fe Zn Cu B Mn),
                                                            env factors (NDVI temp rainfall elevation), coordinates
  POST  /api/mobile/soil-map/climate-zone/         Agroclimatic zone for a location
                                                   Body: { lat, lon }  OR  { temp, rainfall, elevation }
                                                   Returns: zone name, zone id, color, description, soil_types,
                                                            ndvi_range, growing_tips, location, climate inputs
  GET   /api/mobile/soil-map/location-search/      Location autocomplete (Nominatim)
                                                   Query: ?q=<search text>
                                                   Returns: [{ name, lat, lon, type }]
  GET   /api/mobile/soil-map/devices/<id>/readings/         All sensor readings for a soil-map device
  GET   /api/mobile/soil-map/devices/<id>/readings/export/  Download readings as CSV

CarbonCredits (requires auth)                      (devices/carbon_credits.py — proxy to Carbon Credit FastAPI service)
  POST  /api/mobile/carbon-credits/calculate/       calculateCarbon  — compute & save carbon credit report
  POST  /api/mobile/carbon-credits/analyze/         analyzeFarm      — full farm sustainability analysis (no save)
  GET   /api/mobile/carbon-credits/pdf-report/      buildPdfReportUrl — stream PDF carbon credit report

"""
from django.urls import path
from . import mobile_api as m
from . import auth_api   as a
from .devices import soilsaathi as ss
from .devices import atmo_sense as atmo
from .devices import soil_life  as sl
from .devices import ph_bottle  as pb
from .devices import leaflenz   as ll
from agriapp import farmer_api as fa
from soilmap  import views     as sm
from agriapp  import views     as svc
from .devices import carbon_credits as cc

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('auth/register/', a.mobile_register,             name='mobile_register'),
    path('auth/login/',    a.MobileLoginView.as_view(),   name='mobile_login'),
    path('auth/refresh/',  a.MobileRefreshView.as_view(), name='mobile_refresh'),
    path('auth/logout/',   a.mobile_logout,               name='mobile_logout'),

    # ── Device types ──────────────────────────────────────────────────────────
    path('device-types/', m.device_types, name='mobile_device_types'),
    path('device-types/<str:type_key>/field-schema/', m.device_field_schema, name='mobile_device_field_schema'),

    # ── Devices ───────────────────────────────────────────────────────────────
    path('devices/',                             m.device_list,     name='mobile_device_list'),
    path('devices/<int:device_id>/',             m.device_detail,   name='mobile_device_detail'),
    path('devices/<int:device_id>/location/',    m.device_location, name='mobile_device_location'),

    # ── Generic API calls (routes by device type internally) ──────────────────
    path('devices/<int:device_id>/api-calls/',                       m.api_call_list,   name='mobile_api_call_list'),
    path('devices/<int:device_id>/api-calls/create/',                m.api_call_create, name='mobile_api_call_create'),
    path('devices/<int:device_id>/api-calls/<int:call_id>/',         m.api_call_detail, name='mobile_api_call_detail'),

    # ── SoiLENZ (soilsaathi) device-specific routes ───────────────────────────
    path('devices/<int:device_id>/soilsaathi/',                      ss.soilsaathi_list,            name='mobile_ss_list'),
    path('devices/<int:device_id>/soilsaathi/create/',               ss.soilsaathi_create,          name='mobile_ss_create'),
    path('devices/<int:device_id>/soilsaathi/<int:call_id>/',        ss.soilsaathi_detail,          name='mobile_ss_detail'),
    path('devices/<int:device_id>/soilsaathi/recommendations/',        ss.soilsaathi_recommendations,    name='mobile_ss_recommendations'),
    path('devices/<int:device_id>/soilsaathi/ai-recommendation/',     ss.soilsaathi_ai_recommendation,  name='mobile_ss_ai_recommendation'),
    path('devices/<int:device_id>/soilsaathi/<int:call_id>/pdf/',                ss.soilsaathi_pdf,               name='mobile_ss_pdf'),
    path('devices/<int:device_id>/soilsaathi/<int:call_id>/recommendation-pdf/', ss.soilsaathi_recommendation_pdf, name='mobile_ss_recommendation_pdf'),

    # ── SoilSparsh (atmo_sense) device-specific routes ────────────────────────
    path('devices/<int:device_id>/atmo-sense/',                      atmo.atmo_sense_list,   name='mobile_atmo_list'),
    path('devices/<int:device_id>/atmo-sense/create/',               atmo.atmo_sense_create, name='mobile_atmo_create'),
    path('devices/<int:device_id>/atmo-sense/<int:call_id>/',        atmo.atmo_sense_detail, name='mobile_atmo_detail'),

    # ── SoilLIFE (soil_life) device-specific routes ───────────────────────────
    path('devices/<int:device_id>/soil-life/',                       sl.soil_life_list,   name='mobile_sl_list'),
    path('devices/<int:device_id>/soil-life/create/',                sl.soil_life_create, name='mobile_sl_create'),
    path('devices/<int:device_id>/soil-life/<int:call_id>/',         sl.soil_life_detail, name='mobile_sl_detail'),

    # ── PHBottle (ph_bottle) device-specific routes ───────────────────────────
    path('devices/<int:device_id>/ph-bottle/',                       pb.ph_bottle_list,   name='mobile_pb_list'),
    path('devices/<int:device_id>/ph-bottle/create/',                pb.ph_bottle_create, name='mobile_pb_create'),
    path('devices/<int:device_id>/ph-bottle/<int:call_id>/',         pb.ph_bottle_detail, name='mobile_pb_detail'),

    # ── LeafLenz (leaflenz) device-specific routes ────────────────────────────
    path('devices/<int:device_id>/leaflenz/',                       ll.leaflenz_list,   name='mobile_ll_list'),
    path('devices/<int:device_id>/leaflenz/scan/',                  ll.leaflenz_scan,   name='mobile_ll_scan'),
    path('devices/<int:device_id>/leaflenz/stats/',                 ll.leaflenz_stats,  name='mobile_ll_stats'),
    path('devices/<int:device_id>/leaflenz/<int:call_id>/',         ll.leaflenz_detail, name='mobile_ll_detail'),
    path('leaflenz/diseases/',                                      ll.leaflenz_diseases, name='mobile_ll_diseases'),

    # ── Account ───────────────────────────────────────────────────────────────
    path('account/profile/',           m.account_profile,        name='mobile_profile'),
    path('account/profile/update/',    m.account_profile_update, name='mobile_profile_update'),
    path('account/payment-history/',   a.my_payment_history,     name='mobile_payment_history'),

    # ── Password requests (notify admin) ──────────────────────────────────────
    path('auth/forgot-password/',            a.forgot_password_request,  name='mobile_forgot_password'),
    path('account/change-password-request/', a.change_password_request,  name='mobile_change_password_request'),
    path('auth/soil-partner-enquiry/',       a.soil_partner_enquiry,     name='mobile_soil_partner_enquiry'),

    # ── Farmers ───────────────────────────────────────────────────────────────
    path('farmers/check-aadhaar/',            fa.farmer_check_aadhaar, name='mobile_farmer_check_aadhaar'),
    path('farmers/',                          fa.farmer_list,          name='mobile_farmer_list'),
    path('farmers/create/',                   fa.farmer_create,        name='mobile_farmer_create'),
    path('farmers/<int:pk>/',                 fa.farmer_detail,        name='mobile_farmer_detail'),
    path('farmers/<int:pk>/update/',          fa.farmer_update,        name='mobile_farmer_update'),
    path('farmers/<int:pk>/delete/',          fa.farmer_delete,        name='mobile_farmer_delete'),
    path('farmers/<int:pk>/status/',          fa.farmer_update_status, name='mobile_farmer_status'),
    path('farmers/<int:pk>/api-calls/',       fa.farmer_api_calls,          name='mobile_farmer_api_calls'),
    path('farmers/<int:pk>/device-readings/<int:device_id>/', fa.farmer_device_readings, name='mobile_farmer_device_readings'),
    path('farmers/<int:pk>/image/',           fa.farmer_update_image,  name='mobile_farmer_image'),
    path('farmers/<int:pk>/image/delete/',    fa.farmer_delete_image,  name='mobile_farmer_image_delete'),

    # ── Soil Map ──────────────────────────────────────────────────────────────
    path('soil-map/predict/',                                    sm.predict_soil,          name='mobile_sm_predict'),
    path('soil-map/climate-zone/',                               sm.classify_climate_zone, name='mobile_sm_climate_zone'),
    path('soil-map/location-search/',                            svc.location_search,      name='mobile_sm_location_search'),
    path('soil-map/devices/<int:device_id>/readings/',           sm.list_soil_data,        name='mobile_sm_readings'),
    path('soil-map/devices/<int:device_id>/readings/export/',    sm.export_soil_data_csv,  name='mobile_sm_readings_export'),

    # ── CarbonCredits ─────────────────────────────────────────────────────────
    path('carbon-credits/calculate/',  cc.calculate_carbon,      name='mobile_cc_calculate'),
    path('carbon-credits/analyze/',    cc.analyze_farm,          name='mobile_cc_analyze'),
    path('carbon-credits/pdf-report/', cc.build_pdf_report_url,  name='mobile_cc_pdf_report'),
]