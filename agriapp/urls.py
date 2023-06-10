# from django.urls import path, include
# from .views import index
from django.urls import path
from django.views.generic import TemplateView
from . import views as v
from .views import APIThresholdForm, APIThresholdFormUpdate, Dashboard, UpdateDeviceLocation, AddDeviceLocation
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('',  v.home, name = "home"),
    path('login/', TemplateView.as_view(template_name="login.html"), name = "login"),
    path('login1/', v.login, name = "login1"),
    path('login2/', v.login, name = "login2"),
    path('logout/', v.logout, name = "logout"),
    path('acess_denied/', TemplateView.as_view(template_name="acess_denied.html"), name = "acess_denied"),
    path('add_field/', login_required(v.add_field), name = "add_field"),
    path('add-devise/', login_required(v.add_devise), name = "add-devise"),
    path('edit-devise/<int:pk>/', login_required(v.edit_devise), name = "edit-devise"),
    path('device-list/', login_required(v.devise_list), name = "device-list"),
    path('device-details/<int:pk>/', login_required(v.devise_details), name = "device-details"),
    path('api-overview/<int:pk>/', login_required(v.api_overview), name = "api-overview"),
    path('api-edit/<int:pk>/', login_required(v.UpdateApi.as_view()), name = "api-edit"),
    path('api-list/<int:pk>/', login_required(v.api_list), name = "api-list"),
    path('users/',v.users, name = "users"),
    path('forgot_password/', TemplateView.as_view(template_name="forgot_password.html"), name = "forgot_password"),
    path('change_password/<int:pk>', login_required(v.change_password), name = "change-password"),
    path('welcome/', login_required(Dashboard.as_view(  )), name = "welcome"),
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
]

