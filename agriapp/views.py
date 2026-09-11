from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect # redirect to direct url redirect(to)
from django.contrib import auth
from django.contrib.auth.decorators import login_required, user_passes_test

from .forms import ContactForm, DeviseForm
from .models import (
    ContactDetails, UserRequest, Devise, DeviseApis, APICountThreshold,
    ColumnName, DeviseLocation, DeviseApisFields,
    SOIL_LIFE_FIELDS, ATMO_SENSE_FIELDS, SOIL_SAATHI_FIELDS,
    SOIL_SAATHI_FIELD_THRESHOLDS, DEVICE_NAMES, DEVICE_ICONS, PH_BOTTLE_FIELDS, SOIL_MAP_FIELDS,
    LEAFLENZ_FIELDS,
    UserProfile, USER_TYPE_CHOICES,
    Farmer, FarmerStatusHistory, FARMER_STATUS_CHOICES, SEASON_CHOICES,
    PartnerPayment, PaymentAttachment,
)
from agri_ai.leaf import parse_class_label, get_disease_details
from reports.views import build_recommendation, build_fertilizer_recommendation, build_crop_recommendation_v2
from agri_ai.fertilizer import get_states as get_fertilizer_states, get_crops_for_state as get_fertilizer_crops_for_state
from agri_ai.crop_recommendation import get_states as get_crop_rec_states
from agri_ai.yield_estimator import get_hierarchy as get_yield_hierarchy, estimate_yield

from . import UserFunctions
from django.views.generic import UpdateView, TemplateView, CreateView, View
from django.urls import reverse
from django.contrib import messages #import messages
from datetime import datetime
from django.contrib.auth.models import User, Group
from .devise_details import *
from .import FertilizerCalculation
from .overview_dashboard import build_overview_context

from django.shortcuts import get_object_or_404
from django.conf import settings

from django.http import JsonResponse, FileResponse, HttpResponseBadRequest

from django.urls import reverse_lazy
from django import forms
from django.utils.timezone import localtime
import json
from django.core.serializers.json import DjangoJSONEncoder

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import matplotlib.pyplot as plt
import numpy as np
import io
import os
from matplotlib.backends.backend_agg import FigureCanvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

from .serializers import APICountThresholdSerializer 
import pytz
from django.utils import timezone

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


def admin_required(function):
    """Decorator: superuser only. Redirects to /admin-login/ if not authenticated,
    or /acess_denied/ if authenticated but not a superuser."""
    def check(user):
        return user.is_superuser
    return login_required(login_url='/admin-login/')(
        user_passes_test(check, login_url='/acess_denied/')(function)
    )


def user_login_required(function):
    """Decorator: any logged-in user. Redirects to /user-login/ if not authenticated."""
    return login_required(login_url='/user-login/')(function)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin for class-based views: superuser only."""
    login_url = '/admin-login/'

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('/acess_denied/')
        return super().handle_no_permission()

from django.core.paginator import Paginator
        
def home(request):
    if request.method == 'GET':
        template_name = 'home1.html'
        return render(request, template_name)
    elif request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request,"Contact details added successfully")
        else:
            return render(request, 'home1.html', {'errors': form.errors})
        
        template_name = 'home1.html'
        return render(request, template_name, {'message' : 'Contact details has been added successfully'})

def dashboard(request):
    return redirect('/welcome/')

@admin_required
def docs(request):
    return render(request, 'agriapp/docs.html', {'active_page': 'docs'})

@user_login_required
def userPage(request):
    linked_devices = Devise.objects.filter(user__username=request.user.username)
    for devise in linked_devices:
        devise_location          = DeviseLocation.objects.filter(devise=devise).first()
        devise.latitude          = devise_location.latitude if devise_location else 0
        devise.longitude         = devise_location.longitude if devise_location else 0
        api_thresholds           = APICountThreshold.objects.filter(devise=devise).first()
        devise.api_limit         = api_thresholds.red if api_thresholds else None
        devise.type_display_name = DEVICE_NAMES[devise.devise_type]
        match devise.devise_type:
            case "soilsaathi":
                devise.api_used = DeviseApis.objects.filter(device=devise).count()
            case "atmo_sense" | "soil_life" | "ph_bottle" | "leaflenz":
                devise.api_used = DeviseApisFields.objects.filter(device=devise).count()
            case _:
                devise.api_used = 0

    profile    = getattr(request.user, 'profile', None)
    is_partner = profile and profile.user_type == 'soil_partner'
    farmers    = Farmer.objects.filter(soil_partner=request.user) if is_partner else []

    payments = PartnerPayment.objects.filter(user=request.user).select_related('farmer').prefetch_related('attachments') if is_partner else []

    payment_totals = {}
    if is_partner:
        from django.db.models import Sum, Count, Q
        payment_totals = PartnerPayment.objects.filter(user=request.user).aggregate(
            paid_amount    = Sum('amount', filter=Q(status='paid')),
            pending_amount = Sum('amount', filter=Q(status='pending')),
            paid_count     = Count('id', filter=Q(status='paid')),
            pending_count  = Count('id', filter=Q(status='pending')),
        )

    context = {
        "linked_devices" : linked_devices,
        "is_soil_partner": is_partner,
        "profile"        : profile,
        "farmers"        : farmers,
        "payments"       : payments,
        "payment_totals" : payment_totals,
        "season_choices" : SEASON_CHOICES,
        "status_choices" : FARMER_STATUS_CHOICES,
    }
    return render(request, 'agriapp/devise_user_details.html', context)

from django.shortcuts import render, redirect
from django.contrib import auth

def login(request):
    # Already logged in — skip the form and go straight to the right page
    if request.user.is_authenticated:
        return redirect('/dashboard/' if 'admin-login' in request.path else '/user-page/')

    template_mapping = {
        'user-login': 'authapp/login.html',
        'admin-login': 'authapp/login1.html'
    }

    template_name = 'home1.html'  # Default template for errors
    context = {}

    if request.method == 'GET':
        for key, template in template_mapping.items():
            if key in request.path:
                template_name = template
                break

    elif request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            context['error'] = 'Both username and password are required'
        else:
            user = auth.authenticate(username=username, password=password)
            if user:
                auth.login(request, user)
                return redirect('/user-page/' if 'user-login' in request.path else '/dashboard/')
            else:
                context['error'] = 'Invalid username or password'

        # Ensure the correct template is used for errors
        for key, template in template_mapping.items():
            if key in request.path:
                template_name = template
                break

    return render(request, template_name, context)

    
def logout(request):
    auth.logout(request)
    return redirect('/')

class Users(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/users.html'

    def get_context_data(self, **kwargs):
        context        = super().get_context_data(**kwargs)
        group          = Group.objects.get(name='deviseowner')
        users_in_group = User.objects.filter(groups=group).select_related('profile')

        device_types_by_user = {}
        for devise in Devise.objects.filter(user__in=users_in_group).values('user_id', 'devise_type'):
            device_types_by_user.setdefault(devise['user_id'], set()).add(devise['devise_type'])

        users_list = list(users_in_group)
        for u in users_list:
            u.device_types = device_types_by_user.get(u.id, set())
            try:
                u.user_type_display = u.profile.get_user_type_display()
                u.profile_status    = u.profile.status
            except UserProfile.DoesNotExist:
                u.user_type_display = '—'
                u.profile_status    = True

        context['active_page'] = "users"
        context['users']       = users_list
        context['device_info'] = [
            {'key': k, 'name': v, 'icon': DEVICE_ICONS.get(k, 'fa-microchip')}
            for k, v in DEVICE_NAMES.items()
        ]
        return context

class UserForm(forms.Form):
    first_name   = forms.CharField(max_length=30)
    last_name    = forms.CharField(max_length=30)
    username     = forms.CharField(max_length=150)
    email        = forms.EmailField()
    password     = forms.CharField(max_length=128)
    user_type    = forms.ChoiceField(choices=USER_TYPE_CHOICES)
    state        = forms.CharField(max_length=100, required=False)
    district     = forms.CharField(max_length=100, required=False)
    city_village = forms.CharField(max_length=100, required=False)
    amount_paid  = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    balance      = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    status       = forms.BooleanField(required=False, initial=True)

@admin_required
def create_user(request):
    if request.method == "POST":
        form = UserForm(request.POST)

        if form.is_valid():
            first_name   = form.cleaned_data['first_name']
            last_name    = form.cleaned_data['last_name']
            username     = form.cleaned_data['username']
            email        = form.cleaned_data['email']
            password     = form.cleaned_data['password']
            user_type    = form.cleaned_data['user_type']
            state        = form.cleaned_data.get('state', '')
            district     = form.cleaned_data.get('district', '')
            city_village = form.cleaned_data.get('city_village', '')
            amount_paid  = form.cleaned_data.get('amount_paid') or 0
            balance      = form.cleaned_data.get('balance') or 0
            status       = form.cleaned_data.get('status', True)

            if User.objects.filter(username=username).exists():
                form.add_error('username', 'Username already exists')
                return render(request, 'agriapp/create-user.html', {'form': form})

            if User.objects.filter(email=email).exists():
                form.add_error('email', 'Email already exists')
                return render(request, 'agriapp/create-user.html', {'form': form})

            user = UserFunctions.create_user(username, email, first_name, last_name, password)
            UserProfile.objects.create(
                user         = user,
                user_type    = user_type,
                state        = state        if user_type == 'soil_partner' else '',
                district     = district     if user_type == 'soil_partner' else '',
                city_village = city_village if user_type == 'soil_partner' else '',
                amount_paid  = amount_paid  if user_type == 'soil_partner' else 0,
                balance      = balance      if user_type == 'soil_partner' else 0,
                status       = status if status is not None else True,
                created_by   = request.user,
            )
            messages.success(request, "User created successfully")
            return redirect('/users/')
        else:
            return render(request, 'agriapp/create-user.html', {'form': form})
    else:
        form = UserForm()
        return render(request, 'agriapp/create-user.html', {'form': form})

@admin_required
def delete_user(request, uid):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    user = get_object_or_404(User, username=uid)
    Devise.objects.filter(user=user).update(user=None)
    user.delete()
    return JsonResponse({'success': True})


@admin_required
def delete_devise(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    device = get_object_or_404(Devise, pk=pk)
    api_count = (
        DeviseApis.objects.filter(device=device).count() +
        DeviseApisFields.objects.filter(device=device).count()
    )
    if api_count > 0:
        return JsonResponse({'error': f'Cannot delete — this device has {api_count} API call record(s) linked to it.'}, status=400)
    device.delete()
    return JsonResponse({'success': True})


@admin_required
def auto_link_devise(request, uid):
    """Auto-create and link a non-standard device type to a user (no form required)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)

    _STANDARD = {'soilsaathi', 'atmo_sense', 'soil_life', 'ph_bottle'}
    devise_type = request.POST.get('devise_type', '').strip()

    if not devise_type:
        return JsonResponse({'error': 'devise_type is required.'}, status=400)
    if devise_type in _STANDARD:
        return JsonResponse({'error': 'Standard device types must be added via the form.'}, status=400)
    if devise_type not in DEVICE_NAMES:
        return JsonResponse({'error': f'Unknown device type: {devise_type}'}, status=400)

    user = get_object_or_404(User, username=uid)

    if Devise.objects.filter(user=user, devise_type=devise_type).exists():
        return JsonResponse({'error': f'User already has a {DEVICE_NAMES[devise_type]} device linked.'}, status=400)

    from datetime import date
    next_year = date.today().replace(year=date.today().year + 1)
    devise = Devise.objects.create(
        name           = DEVICE_NAMES[devise_type],
        devise_type    = devise_type,
        user           = user,
        amount_paid    = 0,
        balance_amount = 0,
        land           = 0,
        warrenty       = next_year,
    )
    return JsonResponse({'success': True, 'pk': devise.pk, 'name': devise.name})


@admin_required
def add_devise(request, uid=None):
        
    context = {'message': '', 'device_names': DEVICE_NAMES, 'default_type': request.GET.get('type', ''), 'devise': {}}
    user    = UserFunctions.get_user_by_username(uid)

    if request.method == 'GET':
        template_name = 'agriapp/add_devise.html'
    elif request.method == 'POST':
        form = DeviseForm(request.POST)
        if form.is_valid():
            devise      = form.save(commit=False)
            devise.user = user
            devise.save()
            messages.success(request, "Device added successfully")
            return redirect(f"/user-details/{uid}")
        else:
            errors = form.errors
            field_errors = {error: errors[error] for error in errors}
            default_values = {
                'name'          : request.POST['name'],
                'devise_id'     : request.POST['devise_id'],
                'serial_no'     : request.POST['serial_no'],
                'chipset_no'    : request.POST['chipset_no'],
                'email'         : request.POST['email'],
                'address1'      : request.POST['address1'],
                'address2'      : request.POST['address2'],
                'purchase_date' : request.POST['purchase_date'],
                'time_of_sale'  : request.POST['time_of_sale'],
                'warrenty'      : request.POST['warrenty'],
                'amount_paid'   : request.POST['amount_paid'],
                'balance_amount': request.POST['balance_amount'],
                'phone'         : request.POST['phone'],
                'land'          : request.POST['land'],
                'devise_type'   : request.POST['devise_type'],
            }
            return render(request, 'agriapp/add_devise.html', {
                'devise'       : default_values,
                'field_errors' : field_errors,
                'device_names' : DEVICE_NAMES,
                'purchase_date': request.POST.get('purchase_date', ''),
                'time_of_sale' : request.POST.get('time_of_sale', ''),
                'warrenty'     : request.POST.get('warrenty', ''),
            })

    return render(request, template_name, context)

@admin_required
def edit_devise(request, **kwargs):
    context              = {'message' : ''}
    devise               = get_object_or_404(Devise, pk=kwargs['pk'])
    devise.purchase_date = datetime.strptime(str(devise.purchase_date), '%Y-%m-%d') if devise.purchase_date else None
    devise.warrenty      = datetime.strptime(str(devise.warrenty),      '%Y-%m-%d') if devise.warrenty      else None
    if request.method == 'GET':
        template_name = 'agriapp/add_devise.html'
        context       = {
            'devise'        : devise,
            'warrenty'      : str(devise.warrenty.date()),
            'purchase_date' : str(devise.purchase_date.date()) if devise.purchase_date else '',
            'time_of_sale'  : str(devise.time_of_sale) if devise.time_of_sale else '',
            'is_edit'       : True,
            'device_names'  : DEVICE_NAMES,
        }
    elif request.method == 'POST':
        form = DeviseForm(request.POST or None, instance=devise)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.devise_type = devise.devise_type  # device type is locked on edit
            updated.save()
            messages.success(request,"Device updated successfully")
            return redirect(f"/user-details/{devise.user.username}")
        else:
            errors  = form.errors
            field_errors = dict()
            for error in errors:
                field_errors[error] = errors[error]

            default_values = {
                'name'           : request.POST['name'],
                'devise_id'      : request.POST['devise_id'],
                'serial_no'      : request.POST['serial_no'],
                'chipset_no'     : request.POST['chipset_no'],
                'email'          : request.POST['email'],
                'address1'       : request.POST['address1'],
                'address2'       : request.POST['address2'],
                'purchase_date'  : request.POST['purchase_date'],
                'time_of_sale'   : request.POST['time_of_sale'],
                'warrenty'       : request.POST['warrenty'],
                'amount_paid'    : request.POST['amount_paid'],
                'balance_amount' : request.POST['balance_amount'],
                'phone'          : request.POST['phone'],
                'land'           : request.POST['land'],
                'devise_type'    : request.POST['devise_type'],
            }
            
            context1 = {
                'field_errors' : field_errors,
                'devise'       : default_values,
                'is_edit'      : True,
                'device_names' : DEVICE_NAMES,
                'warrenty'     : request.POST['warrenty'],
                'purchase_date': request.POST['purchase_date'],
                'time_of_sale' : request.POST['time_of_sale'],
            }

            return render(request, 'agriapp/add_devise.html', context1)
    return render(request, template_name = template_name, context=context)

@admin_required
def notifications(request, **kwargs):
    if kwargs.get('pk'):
        data = get_object_or_404(ContactDetails, pk=kwargs['pk'])
        data.status = False
        data.save()

    notifications_all  = ContactDetails.objects.all()
    user_requests_all  = UserRequest.objects.all()
    template_name      = 'agriapp/notifications.html'
    context            = {
        'notification_active'    : notifications_all.filter(status=True),
        'notification_inactive'  : notifications_all.filter(status=False),
        'user_requests_pending'  : user_requests_all.filter(status=UserRequest.STATUS_PENDING),
        'user_requests_resolved' : user_requests_all.filter(status=UserRequest.STATUS_RESOLVED),
        'active_page'            : 'notifications',
    }
    return render(request, template_name = template_name, context = context)

@admin_required
def devise_list(request, **kwargs):
    if request.method == 'POST':
        pk = request.POST['pk']
        if pk:
            devises = Devise.objects.filter(pk=request.POST['pk'], devise_type='soilsaathi')
        else :
            devises = Devise.objects.filter(devise_type='soilsaathi')
    else:
        devises = Devise.objects.filter(devise_type='soilsaathi')

    template_name     = 'agriapp/device_list.html'
    
    context = {
        'devise_count' :len(devises),
        'devises'      : devises,
    }
    return render(request, template_name = template_name, context = context)

@admin_required
def devise_details(request, **kwargs):
    devise  = get_object_or_404(Devise, pk=kwargs['pk'])

    if devise.devise_type == 'soilsaathi':
        apis = DeviseApis.objects.filter(device=devise)
    else:
        apis = DeviseApisFields.objects.filter(device=devise)
        
    template_name = 'agriapp/devise_details1.html'
    used          = len(apis)
    remaining     = 0
    if (len(apis)):
        api_thresholds = APICountThreshold.objects.filter(devise=devise).first()
        if api_thresholds:
            val       = api_thresholds.red - len(apis)
            remaining = 0 if (val < 0) else api_thresholds.red - len(apis)
    context       = {
        'devise'        : devise,
        'api_usage'     : len(apis),
        'api_threshold' : APICountThreshold.objects.filter(devise=devise).first(),
        'used'          : len(apis),
        'color'         : get_marker_color(devise),
        'remaining'     : remaining,
        'location'      : DeviseLocation.objects.filter(devise=devise).first()
    }
    return render(request, template_name = template_name, context=context)

@admin_required
def update_user_profile(request, uid):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    target_user = get_object_or_404(User, username=uid)
    data = request.POST

    target_user.first_name = data.get('first_name', target_user.first_name).strip()
    target_user.last_name  = data.get('last_name',  target_user.last_name).strip()
    target_user.email      = data.get('email',       target_user.email).strip()
    target_user.save()

    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    if 'user_type' in data:
        profile.user_type = data['user_type']
    if 'profile_status' in data:
        profile.status = data['profile_status'] == '1'
    if 'state' in data:
        profile.state = data['state'].strip()
    if 'district' in data:
        profile.district = data['district'].strip()
    if 'city_village' in data:
        profile.city_village = data['city_village'].strip()
    if 'amount_paid' in data and data['amount_paid']:
        profile.amount_paid = data['amount_paid']
    if 'balance' in data and data['balance']:
        profile.balance = data['balance']
    profile.save()

    return JsonResponse({'success': True, 'message': 'User profile updated successfully.'})


@admin_required
def user_details(request, **kwargs):
    username       = kwargs.get('uid')
    user           = get_object_or_404(User, username=username)
    linked_devices = Devise.objects.filter(user=user)  # Fetch all devices linked to the user

    for devise in linked_devices:
        devise_location          = DeviseLocation.objects.filter(devise=devise).first()
        devise.latitude          = devise_location.latitude if devise_location else 0
        devise.longitude         = devise_location.longitude if devise_location else 0
        api_thresholds           = APICountThreshold.objects.filter(devise=devise).first()
        devise.api_limit         = api_thresholds.red if api_thresholds else None
        devise.type_display_name = DEVICE_NAMES[devise.devise_type]
        match devise.devise_type:
            case "soilsaathi":
                devise.api_used = DeviseApis.objects.filter(device=devise).count()
            case "atmo_sense" | "soil_life" | "ph_bottle" | "leaflenz":
                devise.api_used = DeviseApisFields.objects.filter(device=devise).count()
            case _:
                devise.api_used = 0

    # Always ensure a profile exists so the Edit button is available for all user types
    profile, _ = UserProfile.objects.get_or_create(user=user)
    is_sp   = profile.user_type == 'soil_partner'
    farmers  = Farmer.objects.filter(soil_partner=user) if is_sp else []
    payments = PartnerPayment.objects.filter(user=user).select_related('farmer').prefetch_related('attachments') if is_sp else []

    payment_totals = {}
    if is_sp:
        from django.db.models import Sum, Count, Q
        payment_totals = PartnerPayment.objects.filter(user=user).aggregate(
            paid_amount    = Sum('amount', filter=Q(status='paid')),
            pending_amount = Sum('amount', filter=Q(status='pending')),
            paid_count     = Count('id', filter=Q(status='paid')),
            pending_count  = Count('id', filter=Q(status='pending')),
        )

    linked_types   = {d.devise_type for d in linked_devices}
    standard_types = {'soilsaathi', 'atmo_sense', 'soil_life', 'ph_bottle'}

    context = {
        "user"           : user,
        "linked_devices" : linked_devices,
        "linked_types"   : linked_types,
        "standard_types" : standard_types,
        "device_names"   : DEVICE_NAMES,
        "profile"        : profile,
        "farmers"        : farmers,
        "payments"       : payments,
        "payment_totals" : payment_totals,
    }

    template_name = 'agriapp/user_details.html'
    return render(request, template_name=template_name, context=context)

@admin_required
def api_overview(request, **kwargs):
    template_name = ''
    context       = dict()
    if "soil-life-api-overview" in request.path:
        template_name   = 'agriapp/soil_life_api_details.html'
        devise_data     = get_object_or_404(DeviseApisFields.objects.select_related('farmer'), pk=kwargs['pk'])
        fields          = {field.name: getattr(devise_data, field.name) for field in DeviseApisFields._meta.get_fields()}
        devise_location = DeviseLocation.objects.filter(devise=devise_data.device).first()
        fields.pop('device', None)
        fields.pop('created_at', None)
        fields.pop('farmer', None)
        context         = {
            'device'          : devise_data.device,
            'api_pk'          : devise_data.pk,
            'fields_api_data' : fields,
            'fields_data_json': json.dumps(fields),
            'fields'          : json.dumps(SOIL_LIFE_FIELDS),
            'latitude'        : devise_location.latitude if devise_location else '',
            'longitude'       : devise_location.longitude if devise_location else '',
        }

    elif "atmos-sense-api-overview" in request.path:
        template_name   = 'agriapp/atmos_sense_api_details.html'
        devise_data     = get_object_or_404(DeviseApisFields.objects.select_related('farmer'), pk=kwargs['pk'])
        fields          = {field.name: getattr(devise_data, field.name) for field in DeviseApisFields._meta.get_fields()}
        devise_location = DeviseLocation.objects.filter(devise=devise_data.device).first()
        fields.pop('device', None)
        fields.pop('created_at', None)
        fields.pop('farmer', None)
        context         = {
            'device'          : devise_data.device,
            'api_pk'          : devise_data.pk,
            'fields_api_data' : fields,
            'fields_data_json': json.dumps(fields),
            'fields'          : json.dumps(ATMO_SENSE_FIELDS),
            'latitude'        : devise_location.latitude if devise_location else '',
            'longitude'       : devise_location.longitude if devise_location else '',
            'linked_farmer'   : devise_data.farmer,
            'available_farmers': Farmer.objects.filter(soil_partner=devise_data.device.user) if devise_data.device.user_id else Farmer.objects.none(),
            'farmer_link_kind': 'fields',
            'farmer_link_pk'  : devise_data.pk,
            'sp_user_pk'      : devise_data.device.user_id,
        }

    elif "ph-bottle-api-overview" in request.path:
        template_name   = 'agriapp/ph_bottle_api_details.html'
        devise_data     = get_object_or_404(DeviseApisFields.objects.select_related('farmer'), pk=kwargs['pk'])
        fields          = {field.name: getattr(devise_data, field.name) for field in DeviseApisFields._meta.get_fields()}
        devise_location = DeviseLocation.objects.filter(devise=devise_data.device).first()
        fields.pop('device', None)
        fields.pop('created_at', None)
        fields.pop('farmer', None)
        context         = {
            'device'          : devise_data.device,
            'api_pk'          : devise_data.pk,
            'fields_api_data' : fields,
            'fields_data_json': json.dumps(fields),
            'fields'          : json.dumps(PH_BOTTLE_FIELDS),
            'latitude'        : devise_location.latitude if devise_location else '',
            'longitude'       : devise_location.longitude if devise_location else '',
            'linked_farmer'   : devise_data.farmer,
            'available_farmers': Farmer.objects.filter(soil_partner=devise_data.device.user) if devise_data.device.user_id else Farmer.objects.none(),
            'farmer_link_kind': 'fields',
            'farmer_link_pk'  : devise_data.pk,
            'sp_user_pk'      : devise_data.device.user_id,
        }

    elif "leaflenz-api-overview" in request.path:
        template_name = 'agriapp/leaflenz_api_details.html'
        devise_data   = get_object_or_404(DeviseApisFields, pk=kwargs['pk'])
        raw_label     = devise_data.tag or 'fallback'
        plant_name, disease_name = parse_class_label(raw_label)
        details       = get_disease_details(raw_label)
        context       = {
            'device'       : devise_data.device,
            'api_pk'       : devise_data.pk,
            'reading'      : devise_data,
            'plant_name'   : plant_name,
            'disease_name' : disease_name,
            'is_healthy'   : disease_name.lower() == 'healthy',
            'confidence_pct': round((devise_data.field1 or 0) * 100, 1),
            'description'  : details.get('description', 'N/A'),
            'symptoms'     : details.get('symptoms', 'N/A'),
            'treatment'    : details.get('treatment_prevention', 'N/A'),
        }

    else :
        api                = get_object_or_404(DeviseApis.objects.select_related('farmer'), pk=kwargs['pk'])
        template_name      = 'agriapp/api_soil_sathi_details.html'
        all_dynamic_fields = UserFunctions.get_all_dynamic_fields()
        dynamic_field_data = {field.field_name : (UserFunctions.get_all_dynamic_field_value(api, field).field_value if UserFunctions.get_all_dynamic_field_value(api, field) else 0.0) for field in all_dynamic_fields}
        crops_data         = FertilizerCalculation.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
        fields             = [f.name for f in DeviseApis._meta.get_fields() if f.name not in ['columndata', 'soil_map_point', 'channeldata', 'id', 'device', 'serial_no', 'created_at', 'crop_type', 'area_name', 'devise_id']]
        fields_data        = [getattr(api, i) for i in fields]
        import random

        fert_state       = request.GET.get('fert_state', '').strip()
        fert_crop        = request.GET.get('fert_crop', '').strip()
        fertilizer_states = get_fertilizer_states()

        # 'recommendation' (Crop Recommendation tab) and 'crop_recommendation_v2'
        # (Crop Match tab) both need a live Open-Meteo climate fetch, which was
        # blocking this page's initial render even when those tabs were never
        # opened. Both are now fetched lazily by their own tab's JS instead —
        # see api_recommendation_text / api_tab_croprec below.
        context = {
            'api'                       : api,
            'devise_name'               : api.device.name,
            'dynamic_fields'            : dynamic_field_data,
            'crops_data'                : crops_data,
            'fields'                    : ','.join(fields),
            'fields_data'               : ','.join(map(str, fields_data)),
            'fields_data_colors'        : ','.join([f"rgba({random.randint(100,255)}, 0, 0, 0.5)" for i in fields_data]),
            'soil_nutrients'            : api,
            'fertilizer_recommendation' : build_fertilizer_recommendation(api, fert_state or None, fert_crop or None),
            'fertilizer_states'         : fertilizer_states,
            'fertilizer_state_crops_json': json.dumps({s: get_fertilizer_crops_for_state(s) for s in fertilizer_states}),
            'crop_rec_states'           : get_crop_rec_states(),
            'linked_farmer'             : api.farmer,
            'available_farmers'         : Farmer.objects.filter(soil_partner=api.device.user) if api.device.user_id else Farmer.objects.none(),
            'farmer_link_kind'          : 'soilsaathi',
            'farmer_link_pk'            : api.pk,
            'sp_user_pk'                : api.device.user_id,
        }

    return render(request, template_name = template_name, context=context)

@admin_required
def api_recommendation_text(request, pk):
    """Crop Recommendation tab's ML result, fetched lazily (needs a live
    Open-Meteo climate call) only when that tab is actually opened."""
    api = get_object_or_404(DeviseApis, pk=pk)
    return JsonResponse({'recommendation': build_recommendation(api)})

@admin_required
def api_tab_croprec(request, pk):
    """Crop Match tab content, fetched lazily (needs a live Open-Meteo climate
    call) only when that tab is actually opened. Returns an HTML fragment."""
    api           = get_object_or_404(DeviseApis.objects.select_related('farmer'), pk=pk)
    croprec_state = request.GET.get('croprec_state', '').strip()
    context = {
        'api'                    : api,
        'crop_recommendation_v2' : build_crop_recommendation_v2(api, croprec_state or None),
        'crop_rec_states'        : get_crop_rec_states(),
    }
    return render(request, 'agriapp/_tab_croprec_content.html', context)

@admin_required
def api_yield_options(request, pk):
    """Hierarchy + prefill for the yield estimator, fetched lazily only when
    the Yield Predictor tab is opened — keeps it off the initial page load."""
    api    = get_object_or_404(DeviseApis.objects.select_related('farmer'), pk=pk)
    farmer = api.farmer if api.farmer_id else None

    yield_hierarchy = get_yield_hierarchy()
    yield_state     = next((s for s in yield_hierarchy if farmer and s.lower() == (farmer.state or '').lower()), '')
    yield_district   = ''
    if yield_state and farmer:
        yield_district = next((d for d in yield_hierarchy[yield_state] if d.lower() == (farmer.district or '').lower()), '')
    yield_crop = ''
    if yield_district:
        yield_crop = next((c for c in yield_hierarchy[yield_state][yield_district] if c.lower() == (api.crop_type or '').lower()), '')

    return JsonResponse({
        'hierarchy': yield_hierarchy,
        'prefill': {
            'soc'     : api.oc or 0.5,
            'pH'      : api.ph or 6.5,
            'N'       : api.nitrogen or 200,
            'P'       : api.phosphorous or 20,
            'K'       : api.potassium or 150,
            'state'   : yield_state,
            'district': yield_district,
            'crop'    : yield_crop,
            'lat'     : api.latitude,
            'lon'     : api.longitude,
        },
    })

@admin_required
def api_yield_predict(request, pk):
    api    = get_object_or_404(DeviseApis, pk=pk)
    district = request.GET.get('district', '').strip()
    crop     = request.GET.get('crop', '').strip()
    if not district or not crop:
        return JsonResponse({"error": "District and crop are required."}, status=400)
    soc = float(request.GET.get('soc', api.oc or 0.5))
    pH  = float(request.GET.get('pH', api.ph or 6.5))
    N   = float(request.GET.get('N', api.nitrogen or 200))
    P   = float(request.GET.get('P', api.phosphorous or 20))
    K   = float(request.GET.get('K', api.potassium or 150))
    result = estimate_yield(district, crop, soc, pH, N, P, K, lat=api.latitude, lon=api.longitude)
    return JsonResponse(result)

@admin_required
def api_yield_history(request, pk):
    # No historical per-year yield series is available yet for this data source.
    return JsonResponse({"years": {}})

@admin_required
def link_farmer_to_reading(request, kind, pk):
    """Link an existing farmer to a single sensor reading (any device type).
    `kind` is 'soilsaathi' for DeviseApis or 'fields' for DeviseApisFields
    (shared by PHBottle/AtmosSense/SoilLIFE/LeafLenz). Only a farmer already
    registered under the reading's own device owner (soil partner) can be
    linked — scoped directly in the lookup below."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Method not allowed.')
    Model   = DeviseApis if kind == 'soilsaathi' else DeviseApisFields
    reading = get_object_or_404(Model, pk=pk)
    farmer  = get_object_or_404(Farmer, pk=request.POST.get('farmer_id'), soil_partner=reading.device.user)
    reading.farmer = farmer
    reading.save(update_fields=['farmer'])
    messages.success(request, f'Linked to farmer "{farmer.farmer_name}".')
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or '/')

class UpdateApi(AdminRequiredMixin, UpdateView):
    model         = DeviseApis
    fields        = '__all__'
    template_name = 'agriapp/update-api.html'

    def get_context_data(self, **kwargs):
        context = super(UpdateApi, self).get_context_data(**kwargs)
        pk      = self.kwargs['pk']
        messages.success(self.request, "API updated successfully")
        return context

    def get_success_url(self):
        return reverse('api-overview', kwargs={'pk': self.kwargs['pk']})

class CreateApi(AdminRequiredMixin, CreateView):
    model         = DeviseApis
    fields        = '__all__'
    template_name = 'agriapp/update-api.html'
    success_url   = '/add-api'

def api_thresholds_validation(data):
    red, orange, blue, green = data['red'], data['orange'], data['blue'], data['green']
    if (green >= blue) or (blue <= green or blue >= orange) or (orange >= red or orange <= blue) or (red <= orange):
        return False
    else :
        return True

class APIThresholdForm(AdminRequiredMixin, CreateView):
    template_name = 'agriapp/api_threshold_form.html'
    model         = APICountThreshold
    fields        = '__all__'

    def get_context_data(self, **kwargs):
        context       = super().get_context_data(**kwargs)
        context['pk'] = self.kwargs['pk']
        return context
    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.kwargs['pk']})
    
    def get_initial(self):
        devise = get_object_or_404(Devise, pk=self.kwargs['pk'])
        return {'devise' : devise}

    def form_valid(self, form):
        if api_thresholds_validation(form.cleaned_data):
            return super().form_valid(form)
        else:
            form.add_error(None, "Please add valid thresholds.)")
            return self.form_invalid(form)

class APIThresholdFormUpdate(AdminRequiredMixin, UpdateView):
    template_name = 'agriapp/api_threshold_form.html'
    model         = APICountThreshold
    fields        = '__all__'   

    def get_context_data(self, **kwargs):
        context       = super().get_context_data(**kwargs)
        context['pk'] = self.kwargs['devise_pk']
        return context

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.kwargs['devise_pk']})

    def form_valid(self, form):
        if api_thresholds_validation(form.cleaned_data):
            return super().form_valid(form)
        else:
            form.add_error(None, "Please add valid thresholds.)")
            return self.form_invalid(form)

from django.http import JsonResponse
import json

@admin_required
def create_or_update_threshold(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed."}, status=405)

    try:
        devise = Devise.objects.get(pk=pk)
    except Devise.DoesNotExist:
        return JsonResponse({"error": "Devise not found."}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    data['devise'] = devise.pk

    try:
        instance = APICountThreshold.objects.get(devise=devise)
        serializer = APICountThresholdSerializer(instance, data=data)
    except APICountThreshold.DoesNotExist:
        serializer = APICountThresholdSerializer(data=data)

    if serializer.is_valid():
        if not api_thresholds_validation(serializer.validated_data):
            return JsonResponse({"error": "Please add valid thresholds."}, status=400)

        serializer.save()
        return JsonResponse(serializer.data, status=200)
    else:
        return JsonResponse(serializer.errors, status=400)

@admin_required
def get_all_NPK_values(request):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed."}, status=405)

    from django.db.models import Q
    queryset = DeviseApis.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False
    ).exclude(
        latitude=0,
        longitude=0
    ).filter(
        Q(nitrogen__gt=0) | Q(phosphorous__gt=0) | Q(potassium__gt=0)
    )

    data = list(queryset.values('latitude', 'longitude', 'nitrogen', 'phosphorous', 'potassium'))

    return JsonResponse({'data': data})

@admin_required
def change_password(request, uid):
    template_name = 'agriapp/change_password.html'
    context       = dict()
    if request.method == 'GET':
        context = {
            'username' : uid
        }
    elif request.method == 'POST':
        if UserFunctions.change_password(uid, request.POST['password']):
            messages.success(request, "Password changed successfully")
        else:
            messages.error(request, "User not found")
        return redirect(f"/user-details/{uid}/")
    return render(request, template_name = template_name, context=context)

class AtmoSSenseDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/atmos_sense_dashboard.html'

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='atmo_sense')
        device_apis       = {}
        device_api_counts = {}
        for device in devices:
            count                        = DeviseApisFields.objects.filter(device=device).count()
            device.api_count             = count
            device_api_counts[device.id] = count

        # Serialize both headers and APIs to JSON
        context['devices']           = devices
        context['api_headers_json']  = json.dumps(ATMO_SENSE_FIELDS)
        context['api_headers']       = ATMO_SENSE_FIELDS
        context['device_apis']       = json.dumps(device_apis)
        context['device_api_counts'] = device_api_counts
        context['active_page']       = 'atmos-sense'
        return context

class AtmoSSenseAPIDetails(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/atmos_sense_api_details.html'

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='atmo_sense')
        device_api_counts = {}
        for device in devices:
            count                        = DeviseApisFields.objects.filter(device=device).count()
            device.api_count             = count
            device_api_counts[device.id] = count

        context['devices']           = devices
        context['api_headers_json']  = json.dumps(ATMO_SENSE_FIELDS)
        context['api_headers']       = ATMO_SENSE_FIELDS
        context['device_api_counts'] = device_api_counts
        return context

class SoilLifeDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/soil_life_dashboard.html'

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='soil_life')
        device_api_counts = {}
        for device in devices:
            count                        = DeviseApisFields.objects.filter(device=device).count()
            device.api_count             = count
            device_api_counts[device.id] = count

        context['devices']           = devices
        context['api_headers_json']  = json.dumps(SOIL_LIFE_FIELDS)
        context['api_headers']       = SOIL_LIFE_FIELDS
        context['device_api_counts'] = device_api_counts
        context['active_page']       = 'soil-life'
        return context

class PHBottleDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/ph_bottle_dashboard.html'

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='ph_bottle')
        device_api_counts = {}
        for device in devices:
            count                        = DeviseApisFields.objects.filter(device=device).count()
            device.api_count             = count
            device_api_counts[device.id] = count

        context['devices']           = devices
        context['api_headers_json']  = json.dumps(PH_BOTTLE_FIELDS)
        context['api_headers']       = PH_BOTTLE_FIELDS
        context['device_api_counts'] = device_api_counts
        context['active_page']       = 'ph-bottle'
        return context


class SoiLENZDashboard(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/soil-saathi-dashboard.html'

    def get_context_data(self, **kwargs):
        context   = super().get_context_data(**kwargs)
        devices   = list(Devise.objects.filter(devise_type='soilsaathi').values())
        locations = {loc.devise_id: (loc.latitude, loc.longitude) for loc in DeviseLocation.objects.all()}

        for device in devices:
            device_id           = device.get("id")
            lat, lng            = locations.get(device_id, (0.0, 0.0))
            device["latitude"]  = lat
            device["longitude"] = lng

        context = {
            'devises'             : json.dumps(devices, cls=DjangoJSONEncoder),
            'devise_count'        : len(devices),
            'api_counts'          : DeviseApis.objects.filter(device__devise_type="soilsaathi").count(),
            'active_page'         : 'soil-saathi',
            'dynamic_fields_count': ColumnName.objects.all().count(),
        }
        return context

class AdminOverviewDashboard(AdminRequiredMixin, TemplateView):
    """Experimental admin analytics overview, backed by real queries against
    Farmer / Devise / DeviseApis(Fields) / PartnerPayment / UserRequest etc.
    See agriapp/overview_dashboard.py for the aggregation logic."""
    template_name = 'agriapp/admin_overview_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'admin-overview'
        context.update(build_overview_context())
        return context

class Dashboard(AdminRequiredMixin, TemplateView):
    template_name = 'agriapp/admin_panel.html'
    def get_context_data(self, **kwargs):
        devise_name = ''
        chart_date  = []
        pk          = ''
        year        = ''
        state       = ''
        if len(self.request.GET):
            pk    = self.request.GET['pk']
            year  = self.request.GET['year']
            state = self.request.GET['state']
            chart_date, devise_name = get_dashboard_chart_data(pk, year, state)
        context           = super().get_context_data(**kwargs)
        devises           = Devise.objects.all()
        notifications_all = ContactDetails.objects.all()
        years             = list(set(get_years_for_filter()))
        years.sort()
        
        ss_api_counts = DeviseApis.objects.filter(device__devise_type="soilsaathi").count()
        sl_api_counts = DeviseApisFields.objects.filter(device__devise_type="soil_life").count()
        as_api_counts = DeviseApisFields.objects.filter(device__devise_type="atmo_sense").count()
        pb_api_counts = DeviseApisFields.objects.filter(device__devise_type="ph_bottle").count()
        devices = list(Devise.objects.values())
        locations     = {loc.devise_id: (loc.latitude, loc.longitude) for loc in DeviseLocation.objects.all()}

        for device in devices:
            device_id           = device.get("id")
            lat, lng            = locations.get(device_id, (0.0, 0.0))  # Default to (0.0, 0.0) if no location
            device["latitude"]  = lat
            device["longitude"] = lng

        context = {
            'devises'            : json.dumps(devices, cls=DjangoJSONEncoder),
            'ss_api_counts'      : ss_api_counts,
            'sl_api_counts'      : sl_api_counts,
            'as_api_counts'      : as_api_counts,
            'pb_api_counts'      : pb_api_counts,
            'api_counts'         : ss_api_counts + sl_api_counts + as_api_counts + pb_api_counts,
            'active_notification': ContactDetails.objects.filter(status=True).exists(),
            'devise_locations'   : json.dumps(locations),
            # 'chart_data'            : chart_date,
            # 'devise_name'           : devise_name,
            # 'devise_counts'         : len(devises),
            # 'api_counts'            : len(DeviseApis.objects.all()),
            # 'dynamic_fields'        : len(ColumnName.objects.all()),
            # 'notification_counts'   : len(ContactDetails.objects.all()),
            # 'notification_inactive' : notifications_all.filter(status=False),
            # 'years'                 : years,
            # 'states'                : states,
            'active_page'           : 'dashboard',
        }
        return context

def get_downloadable_data_format(crops_data, crop, time):
    rows = [[f'API call at {time}', f'THE RECOMMENDED DOSES OF FERTILIZER FOR CROP "{crop}" ARE:']]
    for crop_fertilizer_data in crops_data['crop_fertilizer']:
        for crop_data in crop_fertilizer_data:
            rows.append(['', crop_data])
        rows.append([''])
    
    rows.append(['Remedy, Fertility, Fym and Target yield'])
    for crop_fym_data in crops_data['fym']:
        for fym in crop_fym_data:
            rows.append(['', fym])
    return rows
    
def draw_gauge(value, label):
    fig, ax = plt.subplots(figsize=(2.5, 1.5))
    ax.set_xlim(-1, 1)
    ax.set_ylim(-0.5, 1)
    ax.axis('off')
    ax.set_title(label, fontsize=10)

    # Draw semicircle
    wedge = plt.Circle((0, 0), 1, fill=False, edgecolor='black')
    ax.add_artist(wedge)

    # Draw ticks and labels
    for i in range(0, 15):
        angle = (i / 14) * 180
        x = 0.9 * np.cos(np.radians(180 - angle))
        y = 0.9 * np.sin(np.radians(180 - angle))
        ax.plot([0, x], [0, y], color='gray', linewidth=0.5)

    # Needle
    needle_angle = (value / 14) * 180
    x = 0.9 * np.cos(np.radians(180 - needle_angle))
    y = 0.9 * np.sin(np.radians(180 - needle_angle))
    ax.plot([0, x], [0, y], color='red', linewidth=2)

    buf = io.BytesIO()
    canvas = FigureCanvas(fig)
    canvas.print_png(buf)
    plt.close(fig)
    buf.seek(0)
    return buf

def _build_api_response_pdf(pk):
    """Generate soil-parameters PDF for reading `pk`. Returns a FileResponse."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    logo_path = os.path.join(os.getcwd(), 'static/logo3.PNG')
    c.drawImage(logo_path, 450, 780, width=100, height=40)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "ArkaShine Innovations Pvt Ltd")

    c.setFont("Helvetica", 9)
    c.drawString(50, 785, "Address : H. NO.9.1 2-226, 11th Cross, Bhawani Rice Mill Road")
    c.drawString(50, 772, "Vidyanagar colony, Bidar, Karnataka, India, 585403")

    if pk is not None:
        api      = get_object_or_404(DeviseApis, pk=pk)
        location = DeviseLocation.objects.filter(devise=api.device).first()

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, 740, f"Area name : {api.area_name}")
        c.drawString(50, 725, f"API call time : {api.created_at}")
        c.drawString(50, 710, f"Crop : {api.crop_type}")

        c.drawString(320, 740, f"Latitude : {location.latitude if location else ''}")
        c.drawString(320, 725, f"Longitude : {location.longitude if location else ''}")
        c.drawString(320, 710, f"Phone : +91 9611297893")

        ph_gauge = ImageReader(draw_gauge(api.ph, "pH"))
        ec_gauge = ImageReader(draw_gauge(api.ec, "EC"))
        c.drawImage(ph_gauge, 100, 600, width=150, height=100)
        c.drawImage(ec_gauge, 300, 600, width=150, height=100)

        c.setFont("Helvetica-Bold", 10)
        y = 550
        c.drawString(50, y, "Parameters")
        c.drawString(250, y, "Unit")
        c.drawString(350, y, "Value")

        table_data = [
            ("(0.51–0.75)", "%", "0.29"),
            ("Available Phosphorus (11–25)", "Kg/acre", "108.00"),
            ("Available Potassium (60–120)", "Kg/acre", "204.00"),
            ("Available Calcium as Ca (>300)", "mg/kg", "468.10"),
            ("Available Magnesium as Mg (>120)", "mg/kg", "106.80"),
            ("Available Sulphur as S >10", "mg/kg", "30.11"),
            ("Available Boron", "mg/kg", "0.74"),
            ("Available Zinc as Zn (1.00)", "mg/kg", "2.30"),
            ("Available Iron as Fe (24.50)", "mg/kg", "37.56"),
            ("Available Copper as Cu (1.20)", "mg/kg", "1.50"),
            ("Available Manganese as Mn", "mg/kg", "71.35"),
        ]

        c.setFont("Helvetica", 10)
        y -= 20
        for row in table_data:
            c.drawString(50, y, row[0])
            c.drawString(250, y, row[1])
            c.drawString(350, y, row[2])
            y -= 15
    else:
        c.drawString(50, 700, "No data available")

    c.showPage()
    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="soil_parameters.pdf")


@admin_required
def download_api_response_pdf(request, **kwargs):
    return _build_api_response_pdf(kwargs.get('pk'))

    
@admin_required
def download_api_response_csv(request, **kwargs):
    import csv
    from django.http import HttpResponse

    response                        = HttpResponse(content_type = 'text/csv')
    response['Content-Disposition'] = 'attachment; filename = response.csv'
    writer                          = csv.writer(response)
    if 'pk' in  kwargs:
        api        = get_object_or_404(DeviseApis, pk=kwargs['pk'])
        crops_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
        rows       = get_downloadable_data_format(crops_data, api.crop_type, api.created_at)
    else:
        rows = [['no data available']]
    writer.writerows(rows)
    return response

@admin_required
def dynamic_fields(request, **kwargs):
    template_name = 'agriapp/dynamic_fields.html'
    columns       = UserFunctions.get_all_dynamic_fields()
    context       = {
        'columns' : columns,
        'columns_count' : len(columns),
    }
    return render(request, template_name = template_name, context=context)

@admin_required
def delete_field(request, id):
    field = ColumnName.objects.get(id=id)
    field.delete()
    messages.success(request, "Field deleted successfully.")
    return redirect('/dynamic-fields/')

@admin_required
def add_field(request):
    template_name = 'agriapp/add_field.html'
    if request.method== 'GET':
        return render(request, template_name = template_name)
    elif request.method == 'POST':
        field_name = request.POST['field'].strip().replace(' ', '_')
        if field_name:
            ColumnName.objects.create(field_name=field_name)
            messages.success(request, "Field added successfully.")
            return redirect('/dynamic-fields/')
        else :
            messages.error(request, "Please enter valid field name.")
            return redirect('/add_field/')


class UpdateDeviceLocation(AdminRequiredMixin, UpdateView):
    model         = DeviseLocation
    fields        = ['latitude', 'longitude']
    template_name = 'agriapp/update_location.html'

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.request.POST['success']})

class AddDeviceLocation(AdminRequiredMixin, CreateView):
    model         = DeviseLocation
    fields        = ['devise', 'latitude', 'longitude']
    template_name = 'agriapp/update_location.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Location updated successfully")
        return response

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.request.POST['success']})

    def get_initial(self):
        return {
        'devise':self.kwargs['pk'],
    }

# Columns shown by default in the table for each device type.
# Everything else gets hidden and revealed via the "All Cols" toggle.
# Kept server-side so the frontend never needs to know field names.
_SUMMARY_KEYS = {
    'soilsaathi': ['id', 'tag', 'ph', 'ec', 'oc', 'crop_type', 'farmer_name', 'created_at'],
    'atmo_sense': ['id', 'tag', 'image_path', 'field1', 'field2', 'field3', 'field4', 'field5', 'farmer_name', 'created_at'],
    'soil_life' : ['id', 'tag', 'image_path', 'field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8', 'farmer_name', 'created_at'],
    'ph_bottle' : ['id', 'tag', 'field1', 'field2', 'field3', 'field4', 'farmer_name', 'created_at'],
    'soil_map'  : ['id', 'tag', 'field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'created_at'],
}


class GetDeviseApiCallsJsonData(LoginRequiredMixin, View):
    login_url           = '/user-login/'
    redirect_field_name = 'next'

    def get(self, request, *args, **kwargs):
        id             = kwargs.get('id')  # Use 'id' instead of 'pk'
        headers        = {}
        api_calls_data = []  # Initialize the list for api calls data

        page             = int(request.GET.get('page', 1))
        per_page         = int(request.GET.get('per_page', 100))  # default 100 records per page
        field_thresholds = {}

        try:
            devise    = Devise.objects.get(pk=id)
            farmer_id = request.GET.get('farmer_id')
            match devise.devise_type:
                case "soilsaathi":
                    headers          = SOIL_SAATHI_FIELDS
                    field_thresholds = SOIL_SAATHI_FIELD_THRESHOLDS
                    queryset         = DeviseApis.objects.filter(device=devise).order_by('-created_at')
                case "atmo_sense":
                    headers  = ATMO_SENSE_FIELDS
                    queryset = DeviseApisFields.objects.filter(device=devise).order_by('-created_at')
                case "soil_life":
                    headers  = SOIL_LIFE_FIELDS
                    queryset = DeviseApisFields.objects.filter(device=devise).order_by('-created_at')
                case "ph_bottle":
                    headers  = PH_BOTTLE_FIELDS
                    queryset = DeviseApisFields.objects.filter(device=devise).order_by('-created_at')
                case "leaflenz":
                    headers  = LEAFLENZ_FIELDS
                    queryset = DeviseApisFields.objects.filter(device=devise).order_by('-created_at')
                case _:
                    return JsonResponse({'error': 'Invalid device type'}, status=400)
            if farmer_id:
                queryset = queryset.filter(farmer_id=farmer_id)

            # ✅ Pagination
            paginator      = Paginator(queryset, per_page)
            page_obj       = paginator.get_page(page)
            api_calls_data = list(page_obj.object_list.values())

            # ✅ Convert timestamps to local timezone
            bangalore_tz = pytz.timezone('Asia/Kolkata')
            for item in api_calls_data:
                if item.get('created_at'):
                    utc_dt = item['created_at']
                    if timezone.is_naive(utc_dt):
                        utc_dt = timezone.make_aware(utc_dt, tz=pytz.UTC)
                    local_dt = utc_dt.astimezone(bangalore_tz)
                    item['created_at'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')

            # ✅ Attach farmer names
            farmer_ids = {item.get('farmer_id') for item in api_calls_data if item.get('farmer_id')}
            farmer_map = {}
            if farmer_ids:
                farmer_map = {f.pk: f.farmer_name
                              for f in Farmer.objects.filter(pk__in=farmer_ids).only('id', 'farmer_name')}
            for item in api_calls_data:
                item['farmer_name'] = farmer_map.get(item.get('farmer_id')) or '—'
                # ✅ Build full URL for image_path
                if item.get('image_path'):
                    item['image_path'] = request.build_absolute_uri(item['image_path'])

        except Devise.DoesNotExist:
            return JsonResponse({'error': 'Devise not found'}, status=404)

        headers_with_farmer = dict(headers)
        headers_with_farmer['farmer_name'] = 'Farmer'

        # ✅ Final response
        return JsonResponse({
            'headers'         : headers_with_farmer,
            'summary_keys'    : _SUMMARY_KEYS.get(devise.devise_type, []),
            'data'            : api_calls_data,
            'devise_type'     : devise.devise_type,
            'field_thresholds': field_thresholds,
            'pagination'      : {
                'current_page' : page,
                'per_page'     : per_page,
                'total_pages'  : paginator.num_pages,
                'total_records': paginator.count,
            },
        })

class GetDeviseApiCallsJsonDataForChart(LoginRequiredMixin, View):
    login_url           = '/user-login/'
    redirect_field_name = 'next'

    def get(self, *args, **kwargs):
        from django.views import View
        from django.utils.dateformat import DateFormat
        from django.utils.formats import get_format
        from collections import defaultdict
        from calendar import month_abbr
        id               = kwargs.get('id')
        headers          = {}
        npk_grouped_data = defaultdict(list)
        tag_set          = set()

        try:
            devise = Devise.objects.get(pk=id)

            match devise.devise_type:
                case "soilsaathi":
                    headers = SOIL_SAATHI_FIELDS
                    api_calls_data = DeviseApis.objects.filter(device=devise).values()
                case "atmo_sense":
                    headers        = ATMO_SENSE_FIELDS
                    api_calls_data = DeviseApisFields.objects.filter(device=devise).values()
                case "soil_life":
                    headers        = SOIL_LIFE_FIELDS
                    api_calls_data = DeviseApisFields.objects.filter(device=devise).values()
                case "ph_bottle":
                    headers        = PH_BOTTLE_FIELDS
                    api_calls_data = DeviseApisFields.objects.filter(device=devise).values()
                case _:
                    return JsonResponse({'error': 'Unsupported devise type'}, status=400)

            for entry in api_calls_data:
                timestamp = entry.get("created_at") or entry.get("timestamp") or entry.get("date")
                if not timestamp:
                    continue
                
                # Format as "Jan-2024"
                month_year = f"{month_abbr[timestamp.month]}-{timestamp.year}"

                # Remove non-nutrient fields (like device id, created_at, etc.)
                nutrient_data = {
                    key: value
                    for key, value in entry.items()
                    if key in headers  # Keep only known nutrient fields
                }

                npk_grouped_data[month_year].append(nutrient_data)
                tag = entry.get('tag')
                if tag:
                    tag_set.add(tag)

        except Devise.DoesNotExist:
            return JsonResponse({'error': 'Devise not found'}, status=404)

        return JsonResponse({'headers': headers, 'data': dict(npk_grouped_data),'tags': sorted(list(tag_set))})

class GetApiHeadersJsonData(View):

    def get(self, *args, **kwargs):
        devise_type = kwargs.get('devise_type', '') 
        match devise_type:
            case "soilsaathi":
                headers = SOIL_SAATHI_FIELDS
            case "atmo_sense":
                headers = ATMO_SENSE_FIELDS
            case "soil_life":
                headers = SOIL_LIFE_FIELDS
            case _:
                headers = []
        return JsonResponse({'headers': headers})

class GetApiFieldsJsonData(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        devise_type = kwargs.get('devise_type', '')  
        id          = kwargs.get('id', '')  

        match devise_type:
            case "soilsaathi":
                fields = SOIL_SAATHI_FIELDS
            case "atmo_sense":
                fields = ATMO_SENSE_FIELDS
            case "soil_life":
                fields = SOIL_LIFE_FIELDS
            case "ph_bottle":
                fields = PH_BOTTLE_FIELDS
            case "":
                fields = SOIL_LIFE_FIELDS
            case _:
                fields = {}

        # Fields to exclude
        exclude_keys = {'id', 'created_at', 'image_path', 'crop_type'}

        # Filter out unwanted keys
        filtered_data = {k: v for k, v in fields.items() if k not in exclude_keys}

        return JsonResponse({'data': filtered_data})

@method_decorator(csrf_exempt, name='dispatch')
class SaveApiFieldsJsonData(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        try:
            devise_id = kwargs.get('devise_id', '')
            data = json.loads(request.body)

            # Get the device based on devise_id
            device = get_object_or_404(Devise, id=devise_id)
            devise_type = device.devise_type
            
            # Check if api_id is provided in the data for updating an existing instance
            api_id = kwargs.get('api_id', None)

            if devise_type == "soilsaathi":
                if api_id:  # If api_id exists, update the existing record
                    api_instance = get_object_or_404(DeviseApis, id=api_id, device=device)
                    for field, value in data.items():
                        setattr(api_instance, field, value)
                    api_instance.save()
                    message = 'Data updated successfully.'
                else:  # If api_id does not exist, create a new record
                    api_instance = DeviseApis.objects.create(device=device, devise_id=devise_id, **data)
                    message = 'Data saved successfully.'
            else:
                if api_id:  # If api_id exists, update the existing record
                    api_instance = get_object_or_404(DeviseApisFields, id=api_id, device=device)
                    for field, value in data.items():
                        setattr(api_instance, field, value)
                    api_instance.save()
                    message = 'Data updated successfully.'
                else:  # If api_id does not exist, create a new record
                    api_instance = DeviseApisFields.objects.create(device=device, **data)
                    message = 'Data saved successfully.'

            return JsonResponse({'status': 'success', 'message': message})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class GetApiDataJsonData(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        try:
            devise_id = kwargs.get('devise_id')
            api_id    = kwargs.get('api_id')

            # Get the device
            device = get_object_or_404(Devise, id=devise_id)

            # Choose the field dictionary based on the device type
            if device.devise_type == "soilsaathi":
                api_data = get_object_or_404(DeviseApis, id=api_id, device=device)
                field_map = SOIL_SAATHI_FIELDS
            elif device.devise_type == "atmo_sense":
                api_data  = get_object_or_404(DeviseApisFields, id=api_id, device=device)
                field_map = ATMO_SENSE_FIELDS
            elif device.devise_type == "soil_life":
                api_data  = get_object_or_404(DeviseApisFields, id=api_id, device=device)
                field_map = SOIL_LIFE_FIELDS
            elif device.devise_type == "ph_bottle":
                api_data  = get_object_or_404(DeviseApisFields, id=api_id, device=device)
                field_map = PH_BOTTLE_FIELDS
            else:
                return JsonResponse({'status': 'error', 'message': 'Unknown device type.'}, status=400)

            # Convert model to dictionary, but only include the fields that are in the field map
            fields_data = {}
            for field in api_data._meta.fields:
                field_name = field.name
                if field_name in field_map:
                    fields_data[field_name] = getattr(api_data, field_name)

            return JsonResponse({'status': 'success', 'data': fields_data})

        except Exception as e:
            print(f"Error: {str(e)}")  # Print the exception for debugging
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)



# ── Forgot-password request (web form) ───────────────────────────────────────

def forgot_password_request(request):
    """
    Public view — no login required.
    User fills in username/email and optionally phone.
    Creates a UserRequest(type=forgot_password) so the admin sees it in Notifications.
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email    = request.POST.get('email', '').strip()
        phone    = request.POST.get('phone', '').strip()

        if not username or not email:
            messages.error(request, "Username and email are required.")
            return render(request, 'authapp/forgot_password.html')

        user = User.objects.filter(username=username, email=email).first()

        UserRequest.objects.create(
            user         = user,
            username     = username,
            email        = email,
            phone        = phone,
            request_type = UserRequest.FORGOT_PASSWORD,
            message      = f"User '{username}' has requested a password reset.",
        )
        messages.success(request, "Your request has been sent. An admin will reset your password shortly.")
        return render(request, 'authapp/forgot_password.html', {'submitted': True})

    return render(request, 'authapp/forgot_password.html')


# ── Change-password request (web — logged-in user notifies admin) ─────────────

@user_login_required
def change_password_request(request):
    """
    Logged-in user requests an admin-assisted password change.
    Creates a UserRequest(type=change_password) visible in admin Notifications.
    """
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        user    = request.user

        # Prevent duplicate pending requests
        existing = UserRequest.objects.filter(
            user=user,
            request_type=UserRequest.CHANGE_PASSWORD,
            status=UserRequest.STATUS_PENDING,
        ).exists()

        if existing:
            messages.warning(request, "You already have a pending password change request. Please wait for the admin to process it.")
        else:
            UserRequest.objects.create(
                user         = user,
                username     = user.username,
                email        = user.email,
                phone        = '',
                request_type = UserRequest.CHANGE_PASSWORD,
                message      = message or f"User '{user.username}' has requested a password change.",
            )
            messages.success(request, "Your request has been sent to the admin.")

        return redirect('user-page')

    return render(request, 'authapp/change_password_request.html')


# ── Resolve a UserRequest (admin action from notifications) ───────────────────

@admin_required
def resolve_user_request(request, pk):
    """Mark a UserRequest as resolved from the notifications page."""
    req = get_object_or_404(UserRequest, pk=pk)
    req.status = UserRequest.STATUS_RESOLVED
    req.save()
    messages.success(request, f"Request from '{req.username}' marked as resolved.")
    return redirect('notifications')


# ── Delete a notification (admin action from notifications page) ─────────────

@admin_required
def delete_user_request(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    req = get_object_or_404(UserRequest, pk=pk)
    req.delete()
    return JsonResponse({'success': True})

@admin_required
def delete_contact_notification(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    contact = get_object_or_404(ContactDetails, pk=pk)
    contact.delete()
    return JsonResponse({'success': True})


# ── Soil Partner Interest / Enquiry (public) ──────────────────────────────────

def soil_partner_enquiry(request):
    """
    Public view — no login required.
    Any external user can express interest in becoming a soil partner.
    Creates a UserRequest(type=soil_partner_interest) visible in admin Notifications.
    """
    if request.method == 'POST':
        name    = request.POST.get('name',    '').strip()
        email   = request.POST.get('email',   '').strip()
        phone   = request.POST.get('phone',   '').strip()
        message = request.POST.get('message', '').strip()
        state   = request.POST.get('state',   '').strip()
        city    = request.POST.get('city',    '').strip()

        if not name or not email or not phone:
            messages.error(request, "Name, email, and phone are required.")
            return render(request, 'authapp/soil_partner_enquiry.html', {
                'form_data': request.POST,
            })

        UserRequest.objects.create(
            user         = None,
            username     = name,
            email        = email,
            phone        = phone,
            request_type = UserRequest.SOIL_PARTNER_INTEREST,
            message      = message or f"{name} is interested in becoming a Soil Partner. State: {state}, City: {city}",
        )
        return render(request, 'authapp/soil_partner_enquiry.html', {'submitted': True})

    return render(request, 'authapp/soil_partner_enquiry.html')


@admin_required
def delete_api_call(request, pk):
    """Delete a single API call record (DeviseApis or DeviseApisFields), along with its linked image file, if any."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    device_type = request.POST.get('device_type', '')
    if device_type == 'soilsaathi':
        obj = get_object_or_404(DeviseApis, pk=pk)
    else:
        obj = get_object_or_404(DeviseApisFields, pk=pk)
        if obj.image_path and obj.image_path.startswith(settings.MEDIA_URL):
            file_path = os.path.join(settings.MEDIA_ROOT, obj.image_path[len(settings.MEDIA_URL):])
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
    obj.delete()
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────────────────────
#  Location autocomplete AJAX endpoints
# ─────────────────────────────────────────────────────────────
from .location_data import INDIA_STATES_DISTRICTS

@login_required
def location_states(request):
    states = sorted(INDIA_STATES_DISTRICTS.keys())
    return JsonResponse({'states': states})

@login_required
def location_districts(request):
    state = request.GET.get('state', '')
    districts = sorted(INDIA_STATES_DISTRICTS.get(state, []))
    return JsonResponse({'districts': districts})


# ─────────────────────────────────────────────────────────────
#  Farmer views
# ─────────────────────────────────────────────────────────────
from django.contrib.auth.mixins import LoginRequiredMixin

def _is_soil_partner(user):
    try:
        return user.profile.user_type == 'soil_partner'
    except UserProfile.DoesNotExist:
        return False

def soil_partner_required(function):
    def check(user):
        return user.is_superuser or _is_soil_partner(user)
    return login_required(login_url='/user-login/')(
        user_passes_test(check, login_url='/acess_denied/')(function)
    )


@admin_required
def farmer_list(request):
    import json
    from django.db.models import Count, Q, Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone as tz
    if request.user.is_superuser:
        base_qs = Farmer.objects.select_related('soil_partner').all()
    elif _is_soil_partner(request.user):
        base_qs = Farmer.objects.filter(soil_partner=request.user)
    else:
        return redirect('/acess_denied/')

    farmers = base_qs.annotate(
        soilsaathi_count=Count('soilsaathi_readings', distinct=True),
        atmo_count=Count('sensor_readings', filter=Q(sensor_readings__device__devise_type='atmo_sense'), distinct=True),
        sl_count=Count('sensor_readings',   filter=Q(sensor_readings__device__devise_type='soil_life'),  distinct=True),
        pb_count=Count('sensor_readings',   filter=Q(sensor_readings__device__devise_type='ph_bottle'),  distinct=True),
        sm_count=Count('sensor_readings',   filter=Q(sensor_readings__device__devise_type='soil_map'),   distinct=True),
    ).order_by('-created_at')

    today      = tz.localdate()
    month_start = today.replace(day=1)
    history_qs  = FarmerStatusHistory.objects.filter(farmer__in=base_qs)

    kpi = {
        'total'           : base_qs.count(),
        'registered'      : base_qs.filter(status='registered').count(),
        'sample_collected': base_qs.filter(status='sample_collected').count(),
        'testing_done'    : base_qs.filter(status='testing_done').count(),
        'report_delivered': base_qs.filter(status='report_delivered').count(),
        'today_collected' : history_qs.filter(status='sample_collected', timestamp__date=today).values('farmer').distinct().count(),
        'today_tested'    : history_qs.filter(status='testing_done',     timestamp__date=today).values('farmer').distinct().count(),
        'today_delivered' : history_qs.filter(status='report_delivered', timestamp__date=today).values('farmer').distinct().count(),
        'month_collected' : history_qs.filter(status='sample_collected', timestamp__date__gte=month_start).values('farmer').distinct().count(),
        'month_tested'    : history_qs.filter(status='testing_done',     timestamp__date__gte=month_start).values('farmer').distinct().count(),
        'month_delivered' : history_qs.filter(status='report_delivered', timestamp__date__gte=month_start).values('farmer').distinct().count(),
        'pending_test'    : base_qs.filter(status='sample_collected').count(),
        'pending_report'  : base_qs.filter(status='testing_done').count(),
    }

    crops   = sorted(set(base_qs.values_list('crop',   flat=True).exclude(crop='')))
    villages = sorted(set(base_qs.values_list('village', flat=True).exclude(village='')))

    return render(request, 'agriapp/farmer_list.html', {
        'farmers'             : farmers,
        'kpi'                 : kpi,
        'crops'               : crops,
        'villages'            : villages,
        'active_page'         : 'farmers',
        'farmer_status_choices': FARMER_STATUS_CHOICES,
        'season_choices'      : SEASON_CHOICES,
        'today'               : today,
    })


@soil_partner_required
def create_farmer(request):
    soil_partners = User.objects.filter(profile__user_type='soil_partner') if request.user.is_superuser else []
    if request.method == 'POST':
        data         = request.POST
        sp           = request.user if not request.user.is_superuser else get_object_or_404(User, pk=data.get('soil_partner_id'))
        aadhaar      = data.get('aadhaar_number', '').strip()
        existing     = Farmer.objects.filter(soil_partner=sp, aadhaar_number=aadhaar).first() if aadhaar else None

        if existing and not data.get('reset_confirm'):
            return render(request, 'agriapp/create_farmer.html', {
                'duplicate_farmer' : existing,
                'season_choices'   : SEASON_CHOICES,
                'soil_partners'    : soil_partners,
                'active_page'      : 'farmers',
                'prefill'          : data,
            })

        if existing and data.get('reset_confirm') == '1':
            existing.status = 're_registered'
            existing.save()
            FarmerStatusHistory.objects.create(farmer=existing, status='re_registered')
            messages.success(request, f'Farmer "{existing.farmer_name}" status reset to Re-Registered.')
            return redirect(f'/farmer/{existing.pk}/')

        farmer = Farmer(
            soil_partner   = sp,
            farmer_name    = data.get('farmer_name', '').strip(),
            phone          = data.get('phone', '').strip(),
            email          = data.get('email', '').strip(),
            aadhaar_number = aadhaar,
            mobile         = data.get('mobile', '').strip(),
            state          = data.get('state', '').strip(),
            district       = data.get('district', '').strip(),
            village        = data.get('village', '').strip(),
            address        = data.get('address', '').strip(),
            latitude       = data.get('latitude') or None,
            longitude      = data.get('longitude') or None,
            land_area      = data.get('land_area') or 0.0,
            survey_number  = data.get('survey_number', '').strip(),
            plot_number    = data.get('plot_number', '').strip(),
            crop           = data.get('crop', '').strip(),
            season         = data.get('season', ''),
        )
        if request.FILES.get('farmer_image'):
            farmer.farmer_image = request.FILES['farmer_image']
        farmer.save()
        FarmerStatusHistory.objects.create(farmer=farmer, status='registered')
        messages.success(request, 'Farmer registered successfully.')
        return redirect(f'/farmer/{farmer.pk}/')

    preselected_sp = request.GET.get('sp')
    return render(request, 'agriapp/create_farmer.html', {
        'season_choices'  : SEASON_CHOICES,
        'soil_partners'   : soil_partners,
        'preselected_sp'  : preselected_sp,
        'active_page'     : 'farmers',
    })


@login_required
def farmer_detail(request, pk):
    from collections import defaultdict
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return redirect('/acess_denied/')

    history = farmer.status_history.order_by('timestamp')

    from django.db.models import Count as _Count

    # Per-device-type summary: count + distinct devices used
    ss_devices = (
        DeviseApis.objects.filter(farmer=farmer)
        .values('device__id', 'device__name', 'device__devise_id')
        .annotate(count=_Count('id')).order_by('device__id')
    )
    sensor_devices = (
        DeviseApisFields.objects.filter(farmer=farmer)
        .values('device__id', 'device__name', 'device__devise_id', 'device__devise_type')
        .annotate(count=_Count('id')).order_by('device__id')
    )

    def _sensor_summary(dtype):
        rows = [r for r in sensor_devices if r['device__devise_type'] == dtype]
        return {'count': sum(r['count'] for r in rows), 'devices': rows}

    api_readings = {
        'soilsaathi': {'label': 'SoiLENZ',   'icon': 'fa-temperature-low', 'color': '#1a73e8',
                       'count': sum(r['count'] for r in ss_devices), 'devices': list(ss_devices)},
        'atmo_sense': {'label': 'SoilSparsh', 'icon': 'fa-wind',            'color': '#0097a7', **_sensor_summary('atmo_sense')},
        'soil_life':  {'label': 'SoilLIFE',   'icon': 'fa-leaf',            'color': '#2e7d32', **_sensor_summary('soil_life')},
        'ph_bottle':  {'label': 'PHBottle',    'icon': 'fa-vial',            'color': '#7b1fa2', **_sensor_summary('ph_bottle')},
        'soil_map':   {'label': 'SoilMap',     'icon': 'fa-map-marked-alt',  'color': '#e65100', **_sensor_summary('soil_map')},
    }
    total_api_calls = sum(v['count'] for v in api_readings.values())

    return render(request, 'agriapp/farmer_detail.html', {
        'farmer'          : farmer,
        'history'         : history,
        'status_choices'  : FARMER_STATUS_CHOICES,
        'farmer_status_choices': FARMER_STATUS_CHOICES,
        'season_choices'  : SEASON_CHOICES,
        'api_readings'    : api_readings,
        'total_api_calls' : total_api_calls,
        'active_page'     : 'farmers',
    })


@login_required
def update_farmer(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    data   = request.POST
    fields = ['farmer_name', 'phone', 'mobile', 'email', 'aadhaar_number',
              'state', 'district', 'village', 'address', 'land_area',
              'survey_number', 'plot_number', 'crop', 'season']
    for f in fields:
        if f in data:
            setattr(farmer, f, data[f])
    for f in ('latitude', 'longitude'):
        if data.get(f):
            setattr(farmer, f, data[f])
        else:
            setattr(farmer, f, None)
    if request.FILES.get('farmer_image'):
        if farmer.farmer_image:
            try:
                import os as _os
                if _os.path.isfile(farmer.farmer_image.path):
                    _os.remove(farmer.farmer_image.path)
            except Exception:
                pass
        farmer.farmer_image = request.FILES['farmer_image']
    farmer.save()
    return JsonResponse({'success': True, 'message': 'Farmer updated successfully.'})


@login_required
def farmer_device_readings(request, pk, device_id):
    """Paginated readings for a single farmer + device combo (JSON). Used by farmer detail expand."""
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    device   = get_object_or_404(Devise, pk=device_id)
    page     = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 50)), 200)

    bangalore_tz = pytz.timezone('Asia/Kolkata')

    match device.devise_type:
        case 'soilsaathi':
            headers  = SOIL_SAATHI_FIELDS
            qs       = DeviseApis.objects.filter(device=device, farmer=farmer).order_by('-created_at')
        case 'atmo_sense':
            headers  = ATMO_SENSE_FIELDS
            qs       = DeviseApisFields.objects.filter(device=device, farmer=farmer).order_by('-created_at')
        case 'soil_life':
            headers  = SOIL_LIFE_FIELDS
            qs       = DeviseApisFields.objects.filter(device=device, farmer=farmer).order_by('-created_at')
        case 'ph_bottle':
            headers  = PH_BOTTLE_FIELDS
            qs       = DeviseApisFields.objects.filter(device=device, farmer=farmer).order_by('-created_at')
        case _:
            return JsonResponse({'error': 'Unsupported device type.'}, status=400)

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)
    data      = list(page_obj.object_list.values())

    for item in data:
        if item.get('created_at'):
            utc_dt = item['created_at']
            if timezone.is_naive(utc_dt):
                utc_dt = timezone.make_aware(utc_dt, tz=pytz.UTC)
            item['created_at'] = utc_dt.astimezone(bangalore_tz).strftime('%Y-%m-%d %H:%M:%S')

    return JsonResponse({
        'headers'    : headers,
        'data'       : data,
        'devise_type': device.devise_type,
        'pagination' : {
            'current_page' : page,
            'per_page'     : per_page,
            'total_pages'  : paginator.num_pages,
            'total_records': paginator.count,
        },
    })


@login_required
def check_aadhaar(request):
    aadhaar = request.GET.get('aadhaar', '').strip()
    sp_id   = request.GET.get('sp_id')
    if not aadhaar:
        return JsonResponse({'exists': False})
    if request.user.is_superuser and sp_id:
        qs = Farmer.objects.filter(aadhaar_number=aadhaar, soil_partner_id=sp_id)
    elif not request.user.is_superuser:
        qs = Farmer.objects.filter(aadhaar_number=aadhaar, soil_partner=request.user)
    else:
        qs = Farmer.objects.filter(aadhaar_number=aadhaar)
    f = qs.first()
    if f:
        return JsonResponse({
            'exists'        : True,
            'id'            : f.pk,
            'name'          : f.farmer_name,
            'phone'         : f.phone,
            'village'       : f.village,
            'status'        : f.status,
            'status_display': dict(FARMER_STATUS_CHOICES)[f.status],
            'detail_url'    : f'/farmer/{f.pk}/',
        })
    return JsonResponse({'exists': False})


@login_required
def update_farmer_status(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    new_status = request.POST.get('status', '')
    valid = [s[0] for s in FARMER_STATUS_CHOICES]
    if new_status not in valid:
        return JsonResponse({'error': 'Invalid status.'}, status=400)
    farmer.status = new_status
    farmer.save()
    FarmerStatusHistory.objects.create(farmer=farmer, status=new_status)
    return JsonResponse({'success': True, 'status': new_status, 'display': dict(FARMER_STATUS_CHOICES)[new_status]})


@login_required
def delete_farmer(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    farmer.delete()
    return JsonResponse({'success': True})


@login_required
def farmer_update_image(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    image = request.FILES.get('farmer_image')
    if not image:
        return JsonResponse({'error': 'No image file provided.'}, status=400)
    import os
    if farmer.farmer_image:
        try:
            if os.path.isfile(farmer.farmer_image.path):
                os.remove(farmer.farmer_image.path)
        except Exception:
            pass
    farmer.farmer_image = image
    farmer.save()
    return JsonResponse({'success': True, 'url': farmer.farmer_image.url})


@login_required
def farmer_delete_image(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    farmer = get_object_or_404(Farmer, pk=pk)
    if not request.user.is_superuser and farmer.soil_partner != request.user:
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    if not farmer.farmer_image:
        return JsonResponse({'error': 'No image to delete.'}, status=400)
    import os
    try:
        if os.path.isfile(farmer.farmer_image.path):
            os.remove(farmer.farmer_image.path)
    except Exception:
        pass
    farmer.farmer_image = None
    farmer.save()
    return JsonResponse({'success': True})


# ── API reading image upload / delete (admin) ─────────────────────────────────

@admin_required
def api_reading_upload_image(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    record = get_object_or_404(DeviseApisFields, pk=pk)
    file = request.FILES.get('image')
    if not file:
        return JsonResponse({'error': 'No image file provided.'}, status=400)
    from django.core.files.storage import FileSystemStorage
    fs        = FileSystemStorage()
    file_name = fs.save(file.name, file)
    record.image_path = fs.url(file_name)
    record.save()
    return JsonResponse({'success': True, 'image_url': record.image_path})


@admin_required
def api_reading_delete_image(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    record = get_object_or_404(DeviseApisFields, pk=pk)
    if not record.image_path:
        return JsonResponse({'error': 'No image to delete.'}, status=400)
    record.image_path = None
    record.save()
    return JsonResponse({'success': True})


# ── Payment history (admin list) ──────────────────────────────────────────────

@admin_required
def payment_history(request):
    from django.db.models import Sum, Count, Q
    from django.db.models.functions import TruncMonth
    from django.utils import timezone as tz
    from datetime import timedelta
    from .dashboard_utils import month_buckets, month_labels, fill_monthly, trend_fields, format_inr_short

    qs = PartnerPayment.objects.select_related('user', 'farmer', 'created_by').prefetch_related('attachments')

    # Filters
    user_id        = request.GET.get('user_id', '').strip()
    status_filter  = request.GET.get('status', '').strip()
    date_from      = request.GET.get('date_from', '').strip()
    date_to        = request.GET.get('date_to', '').strip()
    paid_from      = request.GET.get('paid_from', '').strip()
    paid_to        = request.GET.get('paid_to', '').strip()
    min_amount     = request.GET.get('min_amount', '').strip()
    max_amount     = request.GET.get('max_amount', '').strip()

    if user_id:
        qs = qs.filter(user_id=user_id)
    if status_filter in ('pending', 'paid'):
        qs = qs.filter(status=status_filter)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if paid_from:
        qs = qs.filter(paid_at__date__gte=paid_from)
    if paid_to:
        qs = qs.filter(paid_at__date__lte=paid_to)
    if min_amount:
        try:
            qs = qs.filter(amount__gte=float(min_amount))
        except ValueError:
            pass
    if max_amount:
        try:
            qs = qs.filter(amount__lte=float(max_amount))
        except ValueError:
            pass

    totals = qs.aggregate(
        total_amount   = Sum('amount'),
        total_count    = Count('id'),
        distinct_users = Count('user', distinct=True),
        paid_amount    = Sum('amount', filter=Q(status='paid')),
        pending_amount = Sum('amount', filter=Q(status='pending')),
        paid_count     = Count('id', filter=Q(status='paid')),
        pending_count  = Count('id', filter=Q(status='pending')),
    )
    totals['avg_amount'] = (
        float(totals['total_amount']) / totals['total_count']
        if totals['total_amount'] and totals['total_count'] else 0
    )

    # ── Overview: charts + trends, all computed from the same filtered `qs` ──
    now           = tz.now()
    last_30       = now - timedelta(days=30)
    prev_30_start = now - timedelta(days=60)
    twelve_months_ago = now - timedelta(days=365)

    paid_last_30 = float(qs.filter(status='paid', created_at__gte=last_30).aggregate(t=Sum('amount'))['t'] or 0)
    paid_prev_30 = float(qs.filter(status='paid', created_at__gte=prev_30_start, created_at__lt=last_30).aggregate(t=Sum('amount'))['t'] or 0)
    count_last_30 = qs.filter(created_at__gte=last_30).count()
    count_prev_30 = qs.filter(created_at__gte=prev_30_start, created_at__lt=last_30).count()

    overview_kpis = {
        'collected_30d_display': format_inr_short(paid_last_30),
        'records_30d'          : count_last_30,
    }
    overview_kpis.update(trend_fields('collected', paid_last_30, paid_prev_30))
    overview_kpis.update(trend_fields('records', count_last_30, count_prev_30))

    buckets_12 = month_buckets(12)
    paid_by_month = (
        qs.filter(status='paid', created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(total=Sum('amount')).order_by('month')
    )
    pending_by_month = (
        qs.filter(status='pending', created_at__gte=twelve_months_ago)
        .annotate(month=TruncMonth('created_at')).values('month')
        .annotate(total=Sum('amount')).order_by('month')
    )
    monthly_trend = {
        'labels' : month_labels(buckets_12),
        'paid'   : [float(v) for v in fill_monthly(paid_by_month, buckets_12, 'total')],
        'pending': [float(v) for v in fill_monthly(pending_by_month, buckets_12, 'total')],
    }

    status_split = {
        'labels': ['Paid', 'Pending'],
        'data'  : [float(totals['paid_amount'] or 0), float(totals['pending_amount'] or 0)],
    }

    top_partners_rows = list(
        qs.filter(status='paid').values('user__username', 'user__first_name', 'user__last_name')
        .annotate(total=Sum('amount')).order_by('-total')[:5]
    )
    max_partner_total = max((float(r['total']) for r in top_partners_rows), default=0)
    top_partners = [
        {
            'name' : (f"{r['user__first_name']} {r['user__last_name']}".strip() or r['user__username']),
            'total': float(r['total']),
            'pct'  : round(float(r['total']) / max_partner_total * 100) if max_partner_total else 0,
        }
        for r in top_partners_rows
    ]

    pending_qs           = qs.filter(status='pending')
    pending_over_30_count = pending_qs.filter(created_at__lt=last_30).count()
    oldest_pending        = pending_qs.order_by('created_at').first()
    oldest_pending_days   = (now - oldest_pending.created_at).days if oldest_pending else 0

    overview = {
        'kpis'                : overview_kpis,
        'monthly_trend_json'  : json.dumps(monthly_trend, cls=DjangoJSONEncoder),
        'status_split_json'   : json.dumps(status_split, cls=DjangoJSONEncoder),
        'top_partners'        : top_partners,
        'pending_over_30_count': pending_over_30_count,
        'oldest_pending_days' : oldest_pending_days,
    }

    soil_partners = User.objects.filter(profile__user_type='soil_partner').order_by('username')

    from django.core.paginator import Paginator
    paginator   = Paginator(qs.order_by('-created_at'), 25)
    page_number = request.GET.get('page', 1)
    page_obj    = paginator.get_page(page_number)

    return render(request, 'agriapp/payment_history.html', {
        'payments'      : page_obj,
        'page_obj'      : page_obj,
        'soil_partners' : soil_partners,
        'totals'        : totals,
        'overview'      : overview,
        'filters'       : {
            'user_id': user_id, 'status': status_filter,
            'date_from': date_from, 'date_to': date_to,
            'paid_from': paid_from, 'paid_to': paid_to,
            'min_amount': min_amount, 'max_amount': max_amount,
        },
        'active_page'   : 'payment_history',
    })


# ── Add a payment record (admin, AJAX from user_details) ─────────────────────

@admin_required
def add_payment(request, uid):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    target_user = get_object_or_404(User, username=uid)

    amount      = request.POST.get('amount', '').strip()
    description = request.POST.get('description', '').strip()
    farmer_id   = request.POST.get('farmer_id', '').strip()
    status_val  = request.POST.get('status', 'pending').strip()
    if status_val not in ('pending', 'paid'):
        status_val = 'pending'

    if not amount:
        return JsonResponse({'error': 'Amount is required.'}, status=400)
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'Amount must be a positive number.'}, status=400)

    farmer = None
    if farmer_id:
        try:
            farmer = Farmer.objects.get(pk=farmer_id, soil_partner=target_user)
        except Farmer.DoesNotExist:
            return JsonResponse({'error': 'Farmer not found or does not belong to this user.'}, status=400)

    from django.utils import timezone as tz
    paid_at = tz.now() if status_val == 'paid' else None
    payment = PartnerPayment.objects.create(
        user        = target_user,
        farmer      = farmer,
        amount      = amount,
        description = description,
        status      = status_val,
        paid_at     = paid_at,
        created_by  = request.user,
    )
    for f in request.FILES.getlist('attachments'):
        PaymentAttachment.objects.create(payment=payment, file=f)

    return JsonResponse({
        'success'    : True,
        'payment_id' : payment.pk,
        'amount'     : str(payment.amount),
        'description': payment.description,
        'status'     : payment.status,
        'paid_at'    : payment.paid_at.strftime('%d %b %Y') if payment.paid_at else '',
        'created_at' : payment.created_at.strftime('%d %b %Y, %H:%M'),
        'farmer_name': farmer.farmer_name if farmer else '',
    })


# ── Delete a payment record ───────────────────────────────────────────────────

@admin_required
def delete_payment(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    payment = get_object_or_404(PartnerPayment, pk=pk)
    import os
    for att in payment.attachments.all():
        try:
            if os.path.isfile(att.file.path):
                os.remove(att.file.path)
        except Exception:
            pass
    payment.delete()
    return JsonResponse({'success': True})


# ── Edit a payment record (admin) ────────────────────────────────────────────

@admin_required
def edit_payment(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    payment = get_object_or_404(PartnerPayment, pk=pk)

    amount      = request.POST.get('amount', '').strip()
    description = request.POST.get('description', '').strip()
    status_val  = request.POST.get('status', '').strip()

    if amount:
        try:
            payment.amount = float(amount)
        except ValueError:
            return JsonResponse({'error': 'Invalid amount.'}, status=400)
    if description:
        payment.description = description
    if status_val in ('pending', 'paid'):
        from django.utils import timezone as tz
        if status_val == 'paid' and payment.status != 'paid':
            payment.paid_at = tz.now()
        elif status_val == 'pending':
            payment.paid_at = None
        payment.status = status_val
    payment.save()

    for f in request.FILES.getlist('attachments'):
        PaymentAttachment.objects.create(payment=payment, file=f)

    attachments = [
        {'id': a.pk, 'url': a.file.url, 'name': a.file.name.split('/')[-1]}
        for a in payment.attachments.all()
    ]
    return JsonResponse({
        'success'    : True,
        'amount'     : str(payment.amount),
        'description': payment.description,
        'status'     : payment.status,
        'paid_at'    : payment.paid_at.strftime('%d %b %Y, %H:%M') if payment.paid_at else '',
        'attachments': attachments,
    })


# ── Delete a single payment attachment (admin) ────────────────────────────────

@admin_required
def delete_payment_attachment(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    import os
    att = get_object_or_404(PaymentAttachment, pk=pk)
    try:
        if os.path.isfile(att.file.path):
            os.remove(att.file.path)
    except Exception:
        pass
    att.delete()
    return JsonResponse({'success': True})


# ── Toggle payment status (admin: pending ↔ paid) ─────────────────────────────

@admin_required
def toggle_payment_status(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    payment = get_object_or_404(PartnerPayment, pk=pk)
    from django.utils import timezone
    if payment.status == PartnerPayment.STATUS_PENDING:
        payment.status  = PartnerPayment.STATUS_PAID
        payment.paid_at = timezone.now()
    else:
        payment.status  = PartnerPayment.STATUS_PENDING
        payment.paid_at = None
    payment.save()
    return JsonResponse({
        'success': True,
        'status' : payment.status,
        'paid_at': payment.paid_at.strftime('%d %b %Y, %H:%M') if payment.paid_at else '',
    })


# ── My Payment History (soil partner's own view) ──────────────────────────────

@login_required
def my_payment_history(request):
    from django.db.models import Sum, Count
    profile = getattr(request.user, 'profile', None)
    if not profile or profile.user_type != 'soil_partner':
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    from django.db.models import Q
    qs = PartnerPayment.objects.filter(user=request.user).select_related('farmer').prefetch_related('attachments')

    date_from     = request.GET.get('date_from', '').strip()
    date_to       = request.GET.get('date_to', '').strip()
    paid_from     = request.GET.get('paid_from', '').strip()
    paid_to       = request.GET.get('paid_to', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if paid_from:
        qs = qs.filter(paid_at__date__gte=paid_from)
    if paid_to:
        qs = qs.filter(paid_at__date__lte=paid_to)
    if status_filter in ('pending', 'paid'):
        qs = qs.filter(status=status_filter)

    totals = qs.aggregate(
        total_amount   = Sum('amount'),
        total_count    = Count('id'),
        paid_amount    = Sum('amount', filter=Q(status='paid')),
        pending_amount = Sum('amount', filter=Q(status='pending')),
        paid_count     = Count('id', filter=Q(status='paid')),
        pending_count  = Count('id', filter=Q(status='pending')),
    )

    return render(request, 'agriapp/my_payment_history.html', {
        'payments'   : qs,
        'totals'     : totals,
        'filters'    : {
            'date_from': date_from, 'date_to': date_to,
            'paid_from': paid_from, 'paid_to': paid_to,
            'status': status_filter,
        },
        'active_page': 'my_payments',
    })


# ── Location search (Nominatim) ───────────────────────────────────────────────

import requests as _loc_requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as drf_status
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.openapi import OpenApiTypes

_NOMINATIM_URL     = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {"User-Agent": "AgroClimatApp/1.0 (test@gmail.com)"}


@extend_schema(tags=['Services'], summary='Location name search (Nominatim)')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def location_search(request):
    q = request.query_params.get('q', '').strip()
    if not q:
        return Response({'results': []})
    try:
        resp = _loc_requests.get(
            _NOMINATIM_URL,
            params={'q': q, 'format': 'json', 'limit': 6, 'accept-language': 'en', 'addressdetails': 1},
            headers=_NOMINATIM_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        results = [
            {'name': item.get('display_name', ''), 'lat': float(item['lat']),
             'lon': float(item['lon']), 'type': item.get('type', ''),
             'address': item.get('address', {})}
            for item in resp.json()
        ]
        return Response({'results': results})
    except _loc_requests.Timeout:
        return Response({'error': 'Location service timed out'}, status=drf_status.HTTP_504_GATEWAY_TIMEOUT)
    except Exception as e:
        return Response({'error': str(e)}, status=drf_status.HTTP_502_BAD_GATEWAY)


def get_marker_color(devise):
    if devise:
        api_thresholds = APICountThreshold.objects.filter(devise=devise).first()
        if devise.devise_type == 'soilsaathi':
            api_count = len(DeviseApis.objects.filter(device=devise))
        else:
            api_count = len(DeviseApisFields.objects.filter(device=devise))
        color = 'pink'

        if api_thresholds:
            if api_count >= api_thresholds.red:
                color = 'red'
            if api_count >= api_thresholds.orange and api_count <= api_thresholds.red:
                color = 'orange'
            if api_count >= api_thresholds.blue and api_count <= api_thresholds.orange:
                color = 'blue'
            if api_count >= api_thresholds.green and api_count <= api_thresholds.blue:
                color = 'green'
            if api_count < api_thresholds.green:
                color = 'pink'
    return color


@login_required(login_url='/admin-login/')
def map_view(request, **kwargs):
    zoom = 0
    pk = ''

    if request.method == 'POST':
        pk = request.POST['pk']
    elif kwargs:
        pk = kwargs['pk']

    if pk:
        devises = DeviseLocation.objects.filter(devise__pk=pk)
        zoom = 19
    else:
        devises = DeviseLocation.objects.all()

    display_devises_location = dict()
    for devices_location in devises:
        display_devises_location[devices_location.pk] = {
            'name': devices_location.devise.name,
            'latitude': devices_location.latitude,
            'longitude': devices_location.longitude,
            'devise_pk': devices_location.devise.pk,
            'color': get_marker_color(devices_location.devise),
        }

    context = {
        'filter_devise_list': DeviseLocation.objects.all(),
        'devises': display_devises_location,
        'zoom': zoom,
    }
    return render(request, 'agriapp/map_index.html', context=context)
