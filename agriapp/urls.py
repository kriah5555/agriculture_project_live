# from django.urls import path, include
# from .views import index
from django.urls import path
from django.views.generic import TemplateView
from . import views as v
from .views import *
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('',  v.home, name = "home"),
    path('login/', TemplateView.as_view(template_name="login.html"), name = "login"),
    path('login1/', v.login, name = "login1"),
    path('login2/', v.login, name = "login2"),
    path('logout/', v.logout, name = "logout"),
    path('acess_denied/', TemplateView.as_view(template_name="acess_denied.html"), name = "acess_denied"),
    path('add_field/', login_required(v.add_field), name = "add_field"),
    path('add-devise/<str:uid>/', login_required(v.add_devise), name = "add-devise"),
    path('edit-devise/<int:pk>/', login_required(v.edit_devise), name = "edit-devise"),
    path('device-list/', login_required(v.devise_list), name = "device-list"),
    path('device-details/<int:pk>/', login_required(v.devise_details), name = "device-details"),
    path('api-overview/<int:pk>/', login_required(v.api_overview), name = "api-overview"),
    path('api-edit/<int:pk>/', login_required(v.UpdateApi.as_view()), name = "api-edit"),
    path('add-api/', login_required(v.CreateApi.as_view()), name = "add-api"),
    path('api-list/<int:pk>/', login_required(v.api_list), name = "api-list"),
    path('forgot_password/', TemplateView.as_view(template_name="forgot_password.html"), name = "forgot_password"),
    path('change-password/<str:uid>', login_required(v.change_password), name = "change-password"),
    path('welcome/', login_required(Dashboard.as_view()), name = "welcome"),
    path('dashboard/', login_required(v.dashboard), name = "dashboard"),
    path('devise_user_details/', login_required(TemplateView.as_view(template_name="devise_user_details.html")), name = "devise_user_details"),
    path('notifications/', login_required(v.notifications), name = "notifications"),
    path('notifications/<int:pk>/', login_required(v.notifications), name = "notifications"),
    path('add-api-threshold/<int:pk>/', APIThresholdForm.as_view(), name = "add-api-threshold"),
    path('update-api-threshold/<int:pk>/<int:devise_pk>/', APIThresholdFormUpdate.as_view(), name = "update-api-threshold"),
    path('download_api_response_pdf/<int:pk>/', login_required(v.download_api_response_pdf), name = "download-api-response-pdf"),
    path('download_api_response_csv/<int:pk>/', login_required(v.download_api_response_csv), name = "download-api-response-csv"),
    path('dynamic_fields/', login_required(v.dynamic_fields), name = "dynamic_fields"),
    path('delete_field/<int:id>/', login_required(v.delete_field), name = "delete_field"),
    path('update-location/<int:pk>/', login_required(UpdateDeviceLocation.as_view()), name = "update-location"),
    path('add-location/<int:pk>/', login_required(AddDeviceLocation.as_view()), name = "add-location"),

    # New development
    path('users/', login_required(Users.as_view()), name = "users"),
    path('admin-panne/', login_required(v.dashboard), name = "dashboard"),
    path('create-user/', login_required(v.create_user), name = "create-user"),
    path('user-details/<str:uid>/', login_required(v.user_details), name = "user-details"),
    path('soil-saathi-dashboard/', login_required(SoilSaathiDashboard.as_view()), name = "soil-saathi-dashboard"),

    path('atmos-sense-dashboard/', login_required(AtmoSSenseDashboard.as_view()), name = "atmos-sense-dashboard"),
    path('atmos-sense-devise-overview/', login_required(AtmoSSenseDeviseOverviewDetails.as_view()), name = "atmos-sense-devise-overview"),
    path('atmos-sense-devise-overview-data/', getAtmoSenseJsonData.as_view(), name = "atmos-sense-devise-overview-data"), # api data for page
    path('atmos-sense-api-overview/<int:pk>/', login_required(v.api_overview), name = "atmos-sense-api-overview"),

    path('devise-api-calls/<int:id>/', getDeviseApiCallsJsonData.as_view(), name = "devise-api-calls"), # api data for page
    path('soil-life-dashboard/', login_required(SoilLifeDashboard.as_view()), name = "soil-life-dashboard"),
    path('soil-life-api-overview/<int:pk>/', login_required(v.api_overview), name = "soil-life-api-overview"),

]

user_details