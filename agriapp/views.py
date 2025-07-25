from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect # redirect to direct url redirect(to)
from django.contrib import auth
from django.contrib.auth.decorators import login_required, user_passes_test

from .forms import ContactForm, DeviseForm
from .models import ContactDetails, Devise, DeviseApis, APICountThreshold, ColumnName, DeviseLocation, DeviseApisFields, SOIL_LIFE_FIELDS, ATMO_SENSE_FIELDS, SOIL_SAATHI_FIELDS, SOIL_SAATHI_FIELD_THRESHOLDS, DEVICE_NAMES

from . import UserFunctions
from django.views.generic import UpdateView, TemplateView, CreateView, View
from django.urls import reverse
from django.contrib import messages #import messages
from datetime import datetime
from map.views import get_marker_color
from django.contrib.auth.models import User, Group
from .devise_details import *
from .import FertilizerCalculation

from django.shortcuts import get_object_or_404
from django.conf import settings

from django.http import JsonResponse, FileResponse

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

from .serializers import APICountThresholdSerializer 
import pytz
from django.utils import timezone

# Admin access only decorator
def admin_required(function):
    return user_passes_test(lambda user: user.is_superuser)(function)

# Staff access only decorator
def staff_required(function):
    return user_passes_test(lambda user: user.is_staff)(function)

# Create your views here.
# def user_login_access(request):
#     user = request.user

#     if not user.is_staff and user.is_authenticated:
        # devise = get_object_or_404(Devise, devise_id=user.username)
        # apis   = DeviseApis.objects.filter(device=devise).count()

        # api_thresholds = APICountThreshold.objects.filter(devise=devise).first()
        # remaining = max(0, api_thresholds.red - apis) if api_thresholds else 0

        # session_data = {
        #     'pk'            : devise.pk,
        #     'name'          : devise.name,
        #     'serial_no'     : devise.serial_no,
        #     'devise_id'     : devise.devise_id,
        #     'chipset_no'    : devise.chipset_no,
        #     'email'         : devise.email,
        #     'phone'         : devise.phone,
        #     'address1'      : devise.address1,
        #     'address2'      : devise.address2,
        #     'land'          : devise.land,
        #     'purchase_date' : str(devise.purchase_date),
        #     'time_of_sale'  : str(devise.time_of_sale),
        #     'warrenty'      : str(devise.warrenty),
        #     'amount_paid'   : devise.amount_paid,
        #     'balance_amount': devise.balance_amount,
        #     'api_usage'     : apis,
        #     'api_threshold' : bool(api_thresholds),
        #     'used'          : apis,
        #     'color'         : get_marker_color(devise),
        #     'remaining'     : remaining,
        # }

        # request.session.update(session_data)

        # return redirect('/devise_user_details/')
        
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

# def login(request):
#     context = dict()
#     if request.method == 'GET':
#         template_name = 'login1.html'
#     elif request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         user     = auth.authenticate(username = username, password = password)
#         if user is not None:
#             auth.login(request,user)
#             resp = user_login_access(request)
#             if  resp:
#                 return resp
#             return redirect('/dashboard/')
#         else:
#             template_name = 'login1.html'
#             context       =  {'error' : 'Invalid username or password'}
#     return render(request, template_name, context = context)

def dashboard(request):
    return redirect('/welcome/')

def userPage(request):
    linked_devices = Devise.objects.filter(user__username=request.user.username)  # Fetch all devices linked to the user
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
            case "atmo_sense" | "soil_life":
                devise.api_used = DeviseApisFields.objects.filter(device=devise).count()
            case _:
                devise.api_used = 0

    context = {
        "linked_devices": linked_devices, # Add linked devices to the context"
    }
    return render(request, 'devise_user_details.html', context)

from django.shortcuts import render, redirect
from django.contrib import auth

def login(request):
    template_mapping = {
        'user-login': 'login.html',
        'admin-login': 'login1.html'
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

class Users(TemplateView):
    template_name = "users.html"
    
    def get_context_data(self, **kwargs):
        context                = super().get_context_data(**kwargs)
        group                  = Group.objects.get(name='deviseowner')
        users_in_group         = User.objects.filter(groups=group)
        context['active_page'] = "users"
        context['users']       = users_in_group
        
        return context

class UserForm(forms.Form):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(max_length=15)

def create_user(request):
    if request.method == "POST":
        form = UserForm(request.POST)

        if form.is_valid():
            # Extract cleaned data
            first_name = form.cleaned_data['first_name']
            last_name  = form.cleaned_data['last_name']
            username   = form.cleaned_data['username']
            email      = form.cleaned_data['email']
            password   = form.cleaned_data['password']

            # Check if the username already exists
            if User.objects.filter(username=username).exists():
                form.add_error('username', 'Username already exists')
                return render(request, 'create-user.html', {'form': form})

            # Check if the email already exists
            if User.objects.filter(email=email).exists():
                form.add_error('email', 'Email already exists')
                return render(request, 'create-user.html', {'form': form})
            UserFunctions.create_user(username, email, first_name, last_name, password)
            messages.success(request,"User created successfully")

            # Redirect to the users list page (or success page)
            return redirect('/users')
        else:
            # If the form is invalid, render the form again with errors
            return render(request, 'create-user.html', {'form': form})
    else:
        form = UserForm()  # Empty form for GET request
        return render(request, 'create-user.html', {'form': form})

@login_required
def add_devise(request, uid=None):
    # resp = user_login_access(request)  
    # if resp:
    #     return resp
        
    context = {'message': ''}
    user    = UserFunctions.get_user_by_username(uid)

    if request.method == 'GET':
        template_name = "add_devise.html"
    elif request.method == 'POST':
        form = DeviseForm(request.POST)
        if form.is_valid():
            # Save the devise with the user
            devise      = form.save(commit=False)  # Don't commit yet to set the user
            devise.user = user  # Assign the logged-in user
            devise.save()
            messages.success(request, "Device added successfully")
            return redirect(f"/user-details/{uid}")  # Redirect to device list page after saving
        else:
            errors = form.errors
            field_errors = dict()
            for error in errors:
                field_errors[error] = errors[error]

            # Keep the form values and field errors if the form is invalid
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
            return render(request, 'add_devise.html', {'devise': default_values, 'field_errors': field_errors})

    return render(request, template_name, context)

def edit_devise(request, **kwargs):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    context              = {'message' : ''}
    devise               = Devise.objects.get(pk = kwargs['pk'])
    devise.purchase_date = datetime.strptime(str(devise.purchase_date), '%Y-%m-%d')
    devise.warrenty      = datetime.strptime(str(devise.warrenty), '%Y-%m-%d')
    if request.method == 'GET':
        template_name = "add_devise.html"
        context       = {
            'devise'        : devise,
            'warrenty'      : str(devise.warrenty.date()),
            'purchase_date' : str(devise.purchase_date.date()),
            'time_of_sale'  : str(devise.time_of_sale),
            'disabled'      : 'readonly'
        }
    elif request.method == 'POST':
        form = DeviseForm(request.POST or None, instance=devise)
        if form.is_valid():
            form.save()
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
            return render(request, 'add_devise.html', {'field_errors': field_errors, 'devise' : devise, 'disabled' : 'disabled'})
    return render(request, template_name = template_name, context=context)

def notifications(request, **kwargs):
    if (kwargs):
       data = ContactDetails.objects.get(pk = kwargs['pk'])
       data.status = False
       data.save()
    
    notifications_all = ContactDetails.objects.all()
    template_name     = 'notifications.html'
    context           = {
        'notification_active'   : notifications_all.filter(status=True),
        'notification_inactive' : notifications_all.filter(status=False),
    }
    return render(request, template_name = template_name, context = context)

def devise_list(request, **kwargs):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    if request.method == 'POST':
        pk = request.POST['pk']
        if pk:
            devises = Devise.objects.filter(pk=request.POST['pk'], devise_type='soilsaathi')
        else :
            devises = Devise.objects.filter(devise_type='soilsaathi')
    else:
        devises = Devise.objects.filter(devise_type='soilsaathi')

    template_name     = 'device_list.html'
    
    context = {
        'devise_count' :len(devises),
        'devises'      : devises,
    }
    return render(request, template_name = template_name, context = context)

def api_list(request, **kwargs):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    n, p, k, name = '', '', '', ''
    if request.method == 'POST':
        # n = request.POST['n']
        # p = request.POST['p']
        # k = request.POST['k']
        name = request.POST['area_name']
        
    devise = Devise.objects.get(pk = kwargs['pk'])
    apis = DeviseApis.objects.filter(device__pk=kwargs['pk'], area_name__contains=name)
    template_name     = 'api_list.html'
    context = {
        'api_count'   : len(apis),
        'apis'        : apis,
        'devise' : devise,
    }
    return render(request, template_name = template_name, context = context)

def devise_details(request, **kwargs):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    devise  = Devise.objects.get(pk = kwargs['pk'])

    if devise.devise_type == 'soilsaathi':
        apis = DeviseApis.objects.filter(device=devise)
    else:
        apis = DeviseApisFields.objects.filter(device=devise)
        
    template_name = "devise_details1.html"
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
        'location'      : DeviseLocation.objects.filter(devise=devise)
    }
    return render(request, template_name = template_name, context=context)

def user_details(request, **kwargs):
    # resp = user_login_access(request)
    # if resp: 
    #     return resp
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
            case "atmo_sense" | "soil_life":
                devise.api_used = DeviseApisFields.objects.filter(device=devise).count()
            case _:
                devise.api_used = 0  
    
    context = {
        "user"          : user,
        "linked_devices": linked_devices, # Add linked devices to the context
    }

    template_name = "user_details.html"
    return render(request, template_name=template_name, context=context)

def api_overview(request, **kwargs):
    template_name = ''
    context       = dict()
    if "soil-life-api-overview" in request.path:
        template_name   = 'soil_life_api_details.html'
        devise_data     = DeviseApisFields.objects.get(pk=kwargs['pk'])
        fields          = {field.name: getattr(devise_data, field.name) for field in DeviseApisFields._meta.get_fields()}
        devise_location = DeviseLocation.objects.filter(devise=devise_data.device).first()
        fields.pop('device', None)
        fields.pop('created_at', None)
        context         = {
            'device'          : devise_data.device,
            'fields_api_data' : fields,
            'fields_data_json': json.dumps(fields),
            'fields'          : json.dumps(SOIL_LIFE_FIELDS),
            'latitude'        : devise_location.latitude if devise_location else '',
            'longitude'       : devise_location.longitude if devise_location else '',
        }

    elif "atmos-sense-api-overview" in request.path:
        template_name   = 'atmos_sense_api_details.html'
        devise_data     = DeviseApisFields.objects.get(pk=kwargs['pk'])
        fields          = {field.name: getattr(devise_data, field.name) for field in DeviseApisFields._meta.get_fields()}
        devise_location = DeviseLocation.objects.filter(devise=devise_data.device).first()
        fields.pop('device', None)
        fields.pop('created_at', None)
        context         = {
            'device'          : devise_data.device,
            'fields_api_data' : fields,
            'fields_data_json': json.dumps(fields),
            'fields'          : json.dumps(ATMO_SENSE_FIELDS),
            'latitude'        : devise_location.latitude if devise_location else '',
            'longitude'       : devise_location.longitude if devise_location else '',
        }

    else :
        api                = DeviseApis.objects.get(pk=kwargs['pk'])
        template_name      = "api_soil_sathi_details.html"
        all_dynamic_fields = UserFunctions.get_all_dynamic_fields()
        dynamic_field_data = {field.field_name : (UserFunctions.get_all_dynamic_field_value(api, field).field_value if UserFunctions.get_all_dynamic_field_value(api, field) else 0.0) for field in all_dynamic_fields}
        crops_data         = FertilizerCalculation.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
        fields             = [f.name for f in DeviseApis._meta.get_fields() if f.name not in ['columndata', 'id', 'device', 'serial_no', 'created_at', 'crop_type', 'area_name', 'devise_id']]
        fields_data        = [getattr(api, i) for i in fields]
        import random

        context = {
            'api'                : api,
            'devise_name'        : api.device.name,
            'dynamic_fields'     : dynamic_field_data,
            'crops_data'         : crops_data,
            'fields'             : ','.join(fields),
            'fields_data'        : ','.join(map(str, fields_data)),
            'fields_data_colors' : ','.join([f"rgba({random.randint(100,255)}, 0, 0, 0.5)" for i in fields_data]),
        }

    return render(request, template_name = template_name, context=context)

class UpdateApi(UpdateView):
    model         = DeviseApis
    fields        = '__all__'
    template_name = 'update-api.html'
    
    def get_context_data(self, **kwargs):
        context = super(UpdateApi, self).get_context_data(**kwargs)
        pk      = self.kwargs['pk']
        messages.success(self.request, "API updated successfully")
        return context

    def get_success_url(self):
        return reverse('api-overview', kwargs={'pk': self.kwargs['pk']})

class CreateApi(CreateView):
    model         = DeviseApis
    fields        = '__all__'
    template_name = 'update-api.html'
    success_url   = '/add-api'
    
    # def get_context_data(self, **kwargs):
    #     context = super(UpdateApi, self).get_context_data(**kwargs)
    #     pk = self.kwargs['pk']
    #     messages.success(self.request, "API updated successfully")
    #     return context

    # def get_success_url(self):
    #     return reverse('welcome')

def api_thresholds_validation(data):
    red, orange, blue, green = data['red'], data['orange'], data['blue'], data['green']
    if (green >= blue) or (blue <= green or blue >= orange) or (orange >= red or orange <= blue) or (red <= orange):
        return False
    else :
        return True

class APIThresholdForm(CreateView):
    template_name = 'api_threshold_form.html'
    model         = APICountThreshold
    fields        = '__all__'

    def get_context_data(self, **kwargs):
        context       = super().get_context_data(**kwargs)
        context['pk'] = self.kwargs['pk']
        return context
    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.kwargs['pk']})
    
    def get_initial(self):
        devise = Devise.objects.get(pk = self.kwargs['pk'])
        return {'devise' : devise}

    def form_valid(self, form):
        if api_thresholds_validation(form.cleaned_data):
            return super().form_valid(form)
        else:
            form.add_error(None, "Please add valid thresholds.)")
            return self.form_invalid(form)

class APIThresholdFormUpdate(UpdateView):
    template_name = 'api_threshold_form.html'
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

def change_password(request, uid):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
        
    template_name = 'change_password.html'
    context       = dict()
    if request.method == 'GET':
        context = {
            'username' : uid
        }
    elif request.method == 'POST':
        UserFunctions.change_password(uid, request.POST['password'])
        messages.success(request, "password changes successfully")
        return redirect(f"/user-details/{uid}/")
    return render(request, template_name = template_name, context=context)

class AtmoSSenseDashboard(TemplateView):
    template_name = "atmos_sense_dashboard.html"

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='atmo_sense')
        device_apis       = {}
        device_api_counts = {}
        for device in devices:
            api_fields             = DeviseApisFields.objects.filter(device=device)
            device_apis[device.id] = [
                {
                    'id'        : field.pk,
                    'image_path': field.image_path,
                    'field1'    : field.field1,
                    'field2'    : field.field2,
                    'field3'    : field.field3,
                    'field4'    : field.field4,
                    'field5'    : field.field5,
                    'field6'    : field.field6,
                    'field7'    : field.field7,
                    'field8'    : field.field8,
                    'field9'    : field.field9,
                    'field10'   : field.field10,
                    'crop_type' : field.crop_type,
                    'created_at': field.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for field in api_fields
            ]
            device.api_count = api_fields.count()  # Add count directly to device object
            device_api_counts[device.id] = api_fields.count()


        # Serialize both headers and APIs to JSON
        context['devices']           = devices
        context['api_headers_json']  = json.dumps(ATMO_SENSE_FIELDS)  # Convert headers to JSON
        context['api_headers']       = ATMO_SENSE_FIELDS  # Pass the dictionary directly
        context['device_apis']       = json.dumps(device_apis)  # Convert API data to JSON
        context['device_api_counts'] = device_api_counts  # Pass the device API counts to the template
        context['active_page']       = 'atmos-sense'  # Pass the device API counts to the template
        device_api_counts_json       = json.dumps(device_api_counts)
        return context

class AtmoSSenseAPIDetails(TemplateView):
    template_name = "atmos_sense_api_details.html"

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='atmo_sense')
        device_apis       = {}
        device_api_counts = {}
        for device in devices:
            api_fields             = DeviseApisFields.objects.filter(device=device)
            device_apis[device.id] = [
                {
                    'id'        : field.pk,
                    'image_path': field.image_path,
                    'field1'    : field.field1,
                    'field2'    : field.field2,
                    'field3'    : field.field3,
                    'field4'    : field.field4,
                    'field5'    : field.field5,
                    'field6'    : field.field6,
                    'field7'    : field.field7,
                    'field8'    : field.field8,
                    'field9'    : field.field9,
                    'field10'   : field.field10,
                    'crop_type' : field.crop_type,
                    'created_at': field.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for field in api_fields
            ]
            device.api_count             = api_fields.count()  # Add count directly to device object
            device_api_counts[device.id] = api_fields.count()

        # Serialize both headers and APIs to JSON
        context['devices']           = devices
        context['api_headers_json']  = json.dumps(ATMO_SENSE_FIELDS)  # Convert headers to JSON
        context['api_headers']       = ATMO_SENSE_FIELDS  # Pass the dictionary directly
        context['device_apis']       = json.dumps(device_apis)  # Convert API data to JSON
        context['device_api_counts'] = device_api_counts  # Pass the device API counts to the template
        device_api_counts_json       = json.dumps(device_api_counts)
        return context

class SoilLifeDashboard(TemplateView):
    template_name = "soil_life_dashboard.html"

    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        devices           = Devise.objects.filter(devise_type='soil_life')
        device_apis       = {}
        device_api_counts = {}
        for device in devices:
            api_fields             = DeviseApisFields.objects.filter(device=device)
            device_apis[device.id] = [
                {
                    'id'        : field.pk,
                    'image_path': field.image_path,
                    'field1'    : field.field1,
                    'field2'    : field.field2,
                    'field3'    : field.field3,
                    'field4'    : field.field4,
                    'field5'    : field.field5,
                    'field6'    : field.field6,
                    'field7'    : field.field7,
                    'field8'    : field.field8,
                    'field9'    : field.field9,
                    'field10'   : field.field10,
                    'crop_type' : field.crop_type,
                    'created_at': field.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
                for field in api_fields
            ]
            device.api_count             = api_fields.count()  # Add count directly to device object
            device_api_counts[device.id] = api_fields.count()

        # Serialize both headers and APIs to JSON
        context['devices']           = devices
        context['api_headers_json']  = json.dumps(SOIL_LIFE_FIELDS)  # Convert headers to JSON
        context['api_headers']       = SOIL_LIFE_FIELDS  # Pass the dictionary directly
        context['device_apis']       = json.dumps(device_apis)  # Convert API data to JSON
        context['device_api_counts'] = device_api_counts  # Pass the device API counts to the template
        context['active_page']       = 'soil-life'  # Pass the device API counts to the template
        device_api_counts_json       = json.dumps(device_api_counts)
        return context

class SoiLENZDashboard(TemplateView):
    template_name = "soil-saathi-dashboard.html"
    def get_context_data(self, **kwargs):
        context           = super().get_context_data(**kwargs)
        notifications_all = ContactDetails.objects.all()
        devices           = list(Devise.objects.filter(devise_type='soilsaathi').values())
        locations         = {loc.devise_id: (loc.latitude, loc.longitude) for loc in DeviseLocation.objects.all()}

        for device in devices:
            device_id           = device.get("id")
            lat, lng            = locations.get(device_id, (0.0, 0.0))  # Default to (0.0, 0.0) if no location
            device["latitude"]  = lat
            device["longitude"] = lng

        context = {
            'devises'             : json.dumps(devices, cls=DjangoJSONEncoder),
            'devise_count'        : len(devices),
            'api_counts'          : DeviseApis.objects.filter(device__devise_type="soilsaathi").count(),
            'active_page'         : 'soil-saathi',
            'dynamic_fields_count': ColumnName.objects.all().count()
        }
        return context

class Dashboard(TemplateView):
    template_name = "admin_panel.html"
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
            'api_counts'         : ss_api_counts + sl_api_counts + as_api_counts,
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
    
# # To doload PDF response for API
# def download_api_response_pdf(request, **kwargs):
#     from django.http import FileResponse
#     import io
#     from reportlab.pdfgen import canvas
#     from reportlab.lib.units import inch
#     from reportlab.lib.pagesizes import letter
#     from django.http import FileResponse
#     import os

#     api   = DeviseApis.objects.get(pk = kwargs['pk'])
#     lines = []

#     # craete byte streem buffer
#     beffer = io.BytesIO()
#     # create canvas
#     c     = canvas.Canvas(beffer, pagesize = (595.27,841.89), bottomup = 0)
#     image = os.path.join(os.getcwd(), 'static/logo3.PNG')
#     c.drawImage(image, 450, 50, 100, 40) # adding image x, y, width, eight
#     # create a text object
#     textob = c.beginText()
#     textob.setTextOrigin(inch, inch)
#     textob.setFont('Helvetica', 14)

#     textob.textLine(f'                 ArkaShine Innovations Pvt Ltd')
#     textob.setFont('Helvetica', 10)
#     if 'pk' in  kwargs:
#         api = DeviseApis.objects.get(pk=kwargs['pk'])
#         crops_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
#         device_location = DeviseLocation.objects.filter(devise=api.device)
#         textob.textLine(f'API call time :  {api.created_at}')
#         textob.textLine(f'Crop          :  {api.crop_type}')
#         textob.textLine(f'N             :  {api.nitrogen}')
#         textob.textLine(f'P             :  {api.phosphorous}')
#         textob.textLine(f'K             :  {api.potassium}')
#         textob.textLine(f'PH            :  {api.ph}')
#         textob.textLine(f'EC            :  {api.ec}')
#         textob.textLine(f'OC            :  {api.oc}')
#         if (device_location) : 
#             device_location = device_location.first()
#             textob.textLine(f'latitude          :  {device_location.latitude}')
#             textob.textLine(f'longitude          :  {device_location.longitude}')
#         textob.textLine(f'Phone         :  +91 9611297893')
#         textob.textLine(f'Area name     :  {api.area_name}')
#         textob.textLine(f'THE RECOMMENDED DOSES OF FERTILIZER FOR CROP "{api.crop_type}" ARE:')
#         for crop_fertilizer_data in crops_data['crop_fertilizer']:
#             for crop_data in crop_fertilizer_data:
#                 textob.textLine('---->'+crop_data)
#             textob.textLine(' ')
#         textob.textLine('Remedy, Fertility, Fym and Target yield')
#         for crop_fym_data in crops_data['fym']:
#             for fym in crop_fym_data:
#                 textob.textLine('---->'+fym)
#     else:
#         textob.textLine('no data available')

#     textob.setFillColorCMYK(0.8,0,0,0.3)
#     textob.textLine(' ')
#     textob.textLine('Address : H. NO.9.1 2-226, 11th Cross, Bhawani Rice Mill Road')
#     textob.textLine('Vidyanagar colony, Bidar, Karnataka, lndia, 585403')
#     c.drawText(textob)
#     c.showPage()
#     c.save()
#     beffer.seek(0)

#     return FileResponse(beffer, as_attachment=True, filename="recomanded.pdf")

# To doload PDF response for API
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

def download_api_response_pdf(request, **kwargs):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Logo
    logo_path = os.path.join(os.getcwd(), 'static/logo3.PNG')
    c.drawImage(logo_path, 450, 780, width=100, height=40)

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "ArkaShine Innovations Pvt Ltd")

    # Address
    c.setFont("Helvetica", 9)
    c.drawString(50, 785, "Address : H. NO.9.1 2-226, 11th Cross, Bhawani Rice Mill Road")
    c.drawString(50, 772, "Vidyanagar colony, Bidar, Karnataka, India, 585403")

    if 'pk' in kwargs:
        api = DeviseApis.objects.get(pk=kwargs['pk'])
        location = DeviseLocation.objects.filter(devise=api.device).first()

        # Left Column
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, 740, f"Area name : {api.area_name}")
        c.drawString(50, 725, f"API call time : {api.created_at}")
        c.drawString(50, 710, f"Crop : {api.crop_type}")

        # Right Column
        c.drawString(320, 740, f"Latitude : {location.latitude if location else ''}")
        c.drawString(320, 725, f"Longitude : {location.longitude if location else ''}")
        c.drawString(320, 710, f"Phone : +91 9611297893")

        # Gauges
        ph_gauge = draw_gauge(api.ph, "pH")
        ec_gauge = draw_gauge(api.ec, "EC")
        c.drawImage(ph_gauge, 100, 600, width=150, height=100)
        c.drawImage(ec_gauge, 300, 600, width=150, height=100)

        # Table Headers
        c.setFont("Helvetica-Bold", 10)
        y = 550
        c.drawString(50, y, "Parameters")
        c.drawString(250, y, "Unit")
        c.drawString(350, y, "Value")

        # Table Data (Example only, replace with actual data source)
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
    return FileResponse(buffer, as_attachment=True, filename="recommended.pdf")

    
def download_api_response_csv(request, **kwargs):
    import csv
    from django.http import HttpResponse

    response                        = HttpResponse(content_type = 'text/csv')
    response['Content-Disposition'] = 'attachment; filename = response.csv'
    writer                          = csv.writer(response)
    if 'pk' in  kwargs:
        api        = DeviseApis.objects.get(pk=kwargs['pk'])
        crops_data = FertilizerCalculation.get_crop_urea_dap_mop_dose(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
        rows       = get_downloadable_data_format(crops_data, api.crop_type, api.created_at)
    else:
        rows = [['no data available']]
    writer.writerows(rows)
    return response

def dynamic_fields(request, **kwargs):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    template_name = 'dynamic_fields.html'
    columns       = UserFunctions.get_all_dynamic_fields()
    context       = {
        'columns' : columns,
        'columns_count' : len(columns),
    }
    return render(request, template_name = template_name, context=context)

def delete_field(request, id):
    field = ColumnName.objects.get(id=id)
    field.delete()
    messages.success(request, "Field deleted successfully.")
    return redirect('/dynamic-fields/')

def add_field(request):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    template_name = "add_field.html"
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


class UpdateDeviceLocation(UpdateView):
    model         = DeviseLocation
    fields        = ['latitude', 'longitude']
    template_name = 'update_location.html'

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.request.POST['success']})

class AddDeviceLocation(CreateView):
    model         = DeviseLocation
    fields        = ['devise', 'latitude', 'longitude']
    template_name = 'update_location.html'

    def get_context_data(self, **kwargs):
        context = super(AddDeviceLocation, self).get_context_data(**kwargs)
        pk      = self.kwargs['pk']
        messages.success(self.request, "Location updated successfully")
        return context

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.request.POST['success']})

    def get_initial(self):
        return {
        'devise':self.kwargs['pk'],
    }

class GetDeviseApiCallsJsonData(View):

    def get(self, *args, **kwargs):
        id             = kwargs.get('id')  # Use 'id' instead of 'pk'
        headers        = {}
        api_calls_data = []  # Initialize the list for api calls data
        try:
            devise           = Devise.objects.get(pk=id)  # Use 'id' to fetch the Devise object
            field_thresholds = {}
            match devise.devise_type:
                case "soilsaathi":
                    headers          = SOIL_SAATHI_FIELDS
                    field_thresholds = SOIL_SAATHI_FIELD_THRESHOLDS
                    api_calls_data   = list(DeviseApis.objects.filter(device=devise).values())
                case "atmo_sense": 
                    headers        = ATMO_SENSE_FIELDS
                    api_calls_data = list(DeviseApisFields.objects.filter(device=devise).values())
                case "soil_life": 
                    headers        = SOIL_LIFE_FIELDS
                    api_calls_data = list(DeviseApisFields.objects.filter(device=devise).values())
                case _:
                    headers = []

            bangalore_tz = pytz.timezone('Asia/Kolkata')
            for item in api_calls_data:
                if item.get('created_at'):
                    utc_dt = item['created_at']
                    if timezone.is_naive(utc_dt):
                        utc_dt = timezone.make_aware(utc_dt, tz=pytz.UTC)  # <-- use tz=, not timezone=
                    local_dt = utc_dt.astimezone(bangalore_tz)
                    item['created_at'] = local_dt.strftime('%Y-%m-%d %H:%M:%S')

        except Devise.DoesNotExist:
            return JsonResponse({'error': 'Devise not found'}, status=404)

        return JsonResponse({'headers': headers, 'data': api_calls_data, 'devise_type': devise.devise_type, 'field_thresholds': field_thresholds})

class GetDeviseApiCallsJsonDataForChart(View):
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
                    headers = ATMO_SENSE_FIELDS
                    api_calls_data = DeviseApisFields.objects.filter(device=devise).values()
                case "soil_life":
                    headers = SOIL_LIFE_FIELDS
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

class GetApiFieldsJsonData(View):

    def get(self, *args, **kwargs):
        devise_type = kwargs.get('devise_type', '')  
        id          = kwargs.get('id', '')  

        match devise_type:
            case "soilsaathi":
                fields = SOIL_SAATHI_FIELDS
            case "atmo_sense" | "soil_life":
                fields = ATMO_SENSE_FIELDS if devise_type == "atmo_sense" else SOIL_LIFE_FIELDS
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
class SaveApiFieldsJsonData(View):

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

class GetApiDataJsonData(View):

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
                api_data = get_object_or_404(DeviseApisFields, id=api_id, device=device)
                field_map = ATMO_SENSE_FIELDS
            elif device.devise_type == "soil_life":
                api_data = get_object_or_404(DeviseApisFields, id=api_id, device=device)
                field_map = SOIL_LIFE_FIELDS
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

