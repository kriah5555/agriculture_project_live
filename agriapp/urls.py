from django.urls import path
from django.views.generic import TemplateView
from . import views as v
from . import PDF as pdf
from .views import *
from .exportInfo import *
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('',  v.home, name = "home"),
    path('login/', TemplateView.as_view(template_name="authapp/login.html"), name = "login"),
    path('admin-login/', v.login, name = "admin-login"),
    path('user-login/', v.login, name = "user-login"),
    path('logout/', v.logout, name = "logout"),
    path('acess_denied/', TemplateView.as_view(template_name="authapp/acess_denied.html"), name = "acess_denied"),

    # ── Admin-only pages (views already carry @admin_required or AdminRequiredMixin) ──
    path('add_field/',                              v.add_field,                        name="add_field"),
    path('add-devise/<str:uid>/',                   v.add_devise,                       name="add-devise"),
    path('edit-devise/<int:pk>/',                   v.edit_devise,                      name="edit-devise"),
    path('device-list/',                            v.devise_list,                      name="device-list"),
    path('device-details/<int:pk>/',                v.devise_details,                   name="device-details"),
    path('api-overview/<int:pk>/',                  v.api_overview,                     name="api-overview"),
    path('api-edit/<int:pk>/',                      UpdateApi.as_view(),                name="api-edit"),
    path('add-api/',                                CreateApi.as_view(),                name="add-api"),
    path('api-list/<int:pk>/',                      v.api_list,                         name="api-list"),
    path('change-password/<str:uid>',               v.change_password,                  name="change-password"),
    path('welcome/',                                Dashboard.as_view(),                name="welcome"),
    path('dashboard/',                              v.dashboard,                        name="dashboard"),
    path('notifications/',                          v.notifications,                    name="notifications"),
    path('notifications/<int:pk>/',                 v.notifications,                    name="notifications"),
    path('download_api_response_pdf/<int:pk>/',     login_required(pdf.download_api_response_pdf), name="download-api-response-pdf"),
    path('download_api_response_csv/<int:pk>/',     v.download_api_response_csv,        name="download-api-response-csv"),
    path('dynamic-fields/',                         v.dynamic_fields,                   name="dynamic-fields"),
    path('delete_field/<int:id>/',                  v.delete_field,                     name="delete_field"),
    path('update-location/<int:pk>/',               UpdateDeviceLocation.as_view(),     name="update-location"),
    path('add-location/<int:pk>/',                  AddDeviceLocation.as_view(),        name="add-location"),
    path('users/',                                  Users.as_view(),                    name="users"),
    path('create-user/',                            v.create_user,                      name="create-user"),
    path('delete-user/<str:uid>/',                  v.delete_user,                      name="delete-user"),
    path('delete-devise/<int:pk>/',                 v.delete_devise,                    name="delete-devise"),
    path('user-details/<str:uid>/',                 v.user_details,                     name="user-details"),
    path('admin-panne/',                            v.dashboard,                        name="dashboard"),
    path('resolve-user-request/<int:pk>/',          v.resolve_user_request,             name='resolve-user-request'),
    path('delete-api-call/<int:pk>/',               v.delete_api_call,                  name='delete-api-call'),
    path('get-all-npk-values/',                     v.get_all_NPK_values,               name='get-all-npk-values'),
    path('api-threshold/<int:pk>/',                 v.create_or_update_threshold,       name='api-threshold'),
    path('docs/',                                   v.docs,                             name='docs'),

    # ── Device dashboards ────────────────────────────────────────────────────────
    path('soil-saathi-dashboard/',                  SoiLENZDashboard.as_view(),         name="soil-saathi-dashboard"),
    path('atmos-sense-dashboard/',                  AtmoSSenseDashboard.as_view(),      name="atmos-sense-dashboard"),
    path('atmos-sense-api-overview/<int:pk>/',      v.api_overview,                     name="atmos-sense-api-overview"),
    path('soil-life-dashboard/',                    SoilLifeDashboard.as_view(),        name="soil-life-dashboard"),
    path('soil-life-api-overview/<int:pk>/',        v.api_overview,                     name="soil-life-api-overview"),
    path('ph-bottle-dashboard/',                    PHBottleDashboard.as_view(),        name="ph-bottle-dashboard"),
    path('ph-bottle-api-overview/<int:pk>/',        v.api_overview,                     name="ph-bottle-api-overview"),

    # ── AJAX / JSON endpoints ────────────────────────────────────────────────────
    path('devise-api-calls/<int:id>/',              GetDeviseApiCallsJsonData.as_view(),        name="devise-api-calls"),
    path('devise-api-calls-chart/<int:id>/',        GetDeviseApiCallsJsonDataForChart.as_view(),name="devise-api-calls-chart"),
    path('get-api-fields/<str:devise_type>',        GetApiFieldsJsonData.as_view(),             name="get-api-fields"),
    path('save-api-data/<int:devise_id>',           SaveApiFieldsJsonData.as_view(),            name="save-api-data"),
    path('update-api-data/<int:devise_id>/<int:api_id>', SaveApiFieldsJsonData.as_view(),       name="update-api-data"),
    path('get-api-data/<int:devise_id>/<int:api_id>',    GetApiDataJsonData.as_view(),          name="api-data"),

    # ── User-only pages ──────────────────────────────────────────────────────────
    path('user-page/',                              v.userPage,                                 name="user-page"),
    path('change-password-request/',               v.change_password_request,                  name='change-password-request'),

    # ── Public / shared ──────────────────────────────────────────────────────────
    path('forgot_password/',                        v.forgot_password_request,                  name='forgot_password'),
    path('soil-partner-enquiry/',                   v.soil_partner_enquiry,                     name='soil-partner-enquiry'),
    path('devise_user_details/',                    login_required(TemplateView.as_view(template_name="agriapp/devise_user_details.html")), name="devise_user_details"),

    # ── Exports ──────────────────────────────────────────────────────────────────
    path('users/export/',                           ExportUsersView.as_view(),                  name='export-users'),
    path('users-devices/export/',                   ExportUsersAndDevicesView.as_view(),        name='export-users-devices'),
    path('user-devices/export/<str:username>/',     ExportUsersAndDevicesView.as_view(),        name='export-user-devices'),
    path('export/device-apis/<int:device_id>/',     ExportDeviceApisView.as_view(),             name='export-device-apis'),

    # ── Farmer ───────────────────────────────────────────────────────────────────
    path('farmers/',                                v.farmer_list,                              name='farmer-list'),
    path('farmers/create/',                         v.create_farmer,                            name='create-farmer'),
    path('farmer/<int:pk>/',                        v.farmer_detail,                            name='farmer-detail'),
    path('farmer/<int:pk>/update/',                 v.update_farmer,                            name='farmer-update'),
    path('farmer/<int:pk>/status/',                 v.update_farmer_status,                     name='update-farmer-status'),
    path('farmer/<int:pk>/delete/',                 v.delete_farmer,                            name='delete-farmer'),
    path('farmer/<int:pk>/image/update/',           v.farmer_update_image,                      name='farmer-image-update'),
    path('farmer/<int:pk>/image/delete/',           v.farmer_delete_image,                      name='farmer-image-delete'),
    path('farmer/check-aadhaar/',                   v.check_aadhaar,                            name='check-aadhaar'),
    path('update-user-profile/<str:uid>/',          v.update_user_profile,                      name='update-user-profile'),
    path('payment-history/',                        v.payment_history,                          name='payment-history'),
    path('add-payment/<str:uid>/',                  v.add_payment,                              name='add-payment'),
    path('delete-payment/<int:pk>/',                v.delete_payment,                           name='delete-payment'),
    path('toggle-payment-status/<int:pk>/',         v.toggle_payment_status,                    name='toggle-payment-status'),
    path('my-payment-history/',                     v.my_payment_history,                       name='my-payment-history'),

    # ── Location AJAX ────────────────────────────────────────────────────────────
    path('location/states/',                        v.location_states,                          name='location-states'),
    path('location/districts/',                     v.location_districts,                       name='location-districts'),
]