from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect # redirect to direct url redirect(to)
from django.contrib import auth
from django.contrib.auth.decorators import login_required

from .forms import ContactForm, DeviseForm
from .models import ContactDetails, Devise, DeviseApis, APICountThreshold, ColumnName, DeviseLocation

from . import UserFuncrtions
from django.views.generic import UpdateView, TemplateView, CreateView
from django.urls import reverse
from django.contrib import messages #import messages
from datetime import datetime
from map.views import get_marker_color
from django.contrib.auth.models import User
from .devise_details import *
from .import FertilizerCalculation

# Create your views here.

def user_login_access(request):
    user = request.user
    if not user.is_staff and user.is_authenticated:
        devise    = Devise.objects.filter(devise_id=user.username).first()
        apis      = DeviseApis.objects.filter(device=devise)
        used      = 0
        remaining = 0
        if (len(apis)):
            api_thresholds = APICountThreshold.objects.filter(devise=devise).first()
            if api_thresholds:
                val       = api_thresholds.red - len(apis)
                used      = len(apis)
                remaining = 0 if (val < 0) else api_thresholds.red - len(apis)

        request.session['pk']             = devise.pk
        request.session['name']           = devise.name
        request.session['serial_no']      = devise.serial_no
        request.session['devise_id']      = devise.devise_id
        request.session['chipset_no']     = devise.chipset_no
        request.session['email']          = devise.email
        request.session['phone']          = devise.phone
        request.session['address1']       = devise.address1
        request.session['address2']       = devise.address2
        request.session['land']           = devise.land
        request.session['purchase_date']  = str(devise.purchase_date)
        request.session['time_of_sale']   = str(devise.time_of_sale)
        request.session['warrenty']       = str(devise.warrenty)
        request.session['amount_paid']    = devise.amount_paid
        request.session['balance_amount'] = devise.balance_amount
        request.session['api_usage']      = len(apis)
        request.session['api_threshold']  = True if (api_thresholds) else False
        request.session['used']           = used
        request.session['color']          = get_marker_color(devise)
        request.session['remaining']      = remaining

        return redirect('/devise_user_details/')

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

def login(request):
    context = dict()
    if request.method == 'GET':
        template_name = 'login1.html'
    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = auth.authenticate(username = username, password = password)
        if user is not None:
            auth.login(request,user)
            resp = user_login_access(request)
            if  resp:
                return resp
            return redirect('/dashboard/')
        else:
            template_name = 'login1.html'
            context       =  {'error' : 'Invalid username or password'}
    return render(request, template_name, context = context)
    
def logout(request):
    auth.logout(request)
    return redirect('/')

def users(request):
    resp = user_login_access(request)
    if  resp:
        return resp
    template_name = "users.html"
    return render(request, template_name)

def add_devise(request):
    resp = user_login_access(request)
    if  resp:
        return resp
    context = {'message' : ''}
    if request.method == 'GET':
        template_name = "add_devise.html"
    elif request.method == 'POST':
        form = DeviseForm(request.POST)
        if form.is_valid():
            form.save()
            UserFuncrtions.create_user(request.POST['devise_id'], request.POST['email'])
            template_name = 'device_list.html'
            messages.success(request,"Device added successfully")
            return redirect("/device-list/")
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
            }
            return render(request, 'add_devise.html', {'devise' : default_values, 'field_errors' : field_errors})
    return render(request, template_name = template_name, context=context)

def edit_devise(request, **kwargs):
    resp = user_login_access(request)
    if  resp:
        return resp
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
        }
    elif request.method == 'POST':
        form = DeviseForm(request.POST or None, instance=devise)
        if form.is_valid():
            form.save()
            messages.success(request,"Device updated successfully")
            return redirect("/device-list/")
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
            }
            return render(request, 'add_devise.html', {'field_errors': field_errors, 'devise' : devise, })
    return render(request, template_name = template_name, context=context)

def notifications(request, **kwargs):
    resp = user_login_access(request)
    if  resp:
        return resp
    if (kwargs):
       data = ContactDetails.objects.get(pk = kwargs['pk'])
       data.status = False
       data.save()
    
    notifications_all = ContactDetails.objects.all()
    template_name     = 'notifications.html'
    context = {
        'notification_active'   : notifications_all.filter(status=True),
        'notification_inactive' : notifications_all.filter(status=False),
    }
    return render(request, template_name = template_name, context = context)

def devise_list(request, **kwargs):
    resp = user_login_access(request)
    if  resp:
        return resp
    if request.method == 'POST':
        pk = request.POST['pk']
        if pk:
            devises = Devise.objects.filter(pk=request.POST['pk'])
        else :
            devises = Devise.objects.all()
    else:
        devises = Devise.objects.all()

    devices = Devise.objects.all()
    template_name     = 'device_list.html'
    
    context = {
        'devise_count' :len(devises),
        'devises'      : devises,
        'devices'      : devices,
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
    resp = user_login_access(request)
    if  resp:
        return resp
    devise  = Devise.objects.get(pk = kwargs['pk'])

    # for i in range(56):
    #     DeviseApis.objects.create(
    #         device=devise,
    #         area_name='bond'+str(i),
    #         devise_id=70099+i,
    #         serial_no=1208827+i,
    #         electrical_conduction=89,
    #         nitrogen=13,
    #         phosphorous=45,
    #         potassium=98,
    #         calcium=43,
    #         magnesium=23,
    #         zinc=55,
    #         manganese=78,
    #         iron=89,
    #         copper=65,
    #         boron=12,
    #         molybdenum=49,
    #         chlorine=23,
    #         nickel=44,
    #         organic_carboa=12,
    #         )


    apis          = DeviseApis.objects.filter(device=devise)
    template_name = "devise_details1.html"
    used          = 0
    remaining     = 0
    if (len(apis)):
        api_thresholds = APICountThreshold.objects.filter(devise=devise).first()
        if api_thresholds:
            val       = api_thresholds.red - len(apis)
            used      = len(apis)
            remaining = 0 if (val < 0) else api_thresholds.red - len(apis)

    context       = {
        'devise'        : devise,
        'api_usage'     : len(apis),
        'api_threshold' : APICountThreshold.objects.filter(devise=devise).first(),
        'used'          : used,
        'color'         : get_marker_color(devise),
        'remaining'     : remaining,
        'location'      : DeviseLocation.objects.filter(devise=devise)
    }
    return render(request, template_name = template_name, context=context)

def api_overview(request, **kwargs):
    # resp = user_login_access(request)
    # if  resp:
    #     return resp
    api = DeviseApis.objects.get(pk=kwargs['pk'])
    template_name = "api_details.html"
    all_dynamic_fields = UserFuncrtions.get_all_dynamic_fields()
    dynamic_field_data = {field.field_name : (UserFuncrtions.get_all_dynamic_field_value(api, field).field_value if UserFuncrtions.get_all_dynamic_field_value(api, field) else 0.0) for field in all_dynamic_fields}
    # crops_data = FertilizerCalculation.get_All_crops(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
    crops_data = FertilizerCalculation.get_All_crops(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
    fields = [f.name for f in DeviseApis._meta.get_fields() if f.name not in ['columndata', 'id', 'device', 'serial_no', 'created_at', 'crop_type', 'area_name', 'devise_id']]
    fields_data = [getattr(api, i) for i in fields]
    import random

    context = {
        'api' : api,
        'devise_name' : api.device.name,
        'dynamuc_fields' : dynamic_field_data,
        'crops_data' : crops_data,
        'fields'      : ','.join(fields),
        'fields_data'      : ','.join(map(str, fields_data)),
        'fields_data_colors' : ','.join([f"rgba({random.randint(100,255)}, 0, 0, 0.5)" for i in fields_data]),
    }
    return render(request, template_name = template_name, context=context)

class UpdateApi(UpdateView):
    model = DeviseApis
    fields = '__all__'
    template_name = 'updaet-api.html'
    
    def get_context_data(self, **kwargs):
        context = super(UpdateApi, self).get_context_data(**kwargs)
        pk = self.kwargs['pk']
        messages.success(self.request, "API updated successfully")
        return context

    def get_success_url(self):
        return reverse('api-overview', kwargs={'pk': self.kwargs['pk']})

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
        context = super().get_context_data(**kwargs)
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
        context = super().get_context_data(**kwargs)
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

def change_password(request, **kwargs):
    resp = user_login_access(request)
    if  resp:
        return resp
    template_name = 'change_password.html'
    context       = dict()
    devise        = Devise.objects.filter(pk=kwargs['pk']).first()
    if request.method == 'GET':
        context = {
            'devise' : devise
        }
    elif request.method == 'POST':
        UserFuncrtions.change_password(devise.devise_id, request.POST['password'])
        messages.success(request, "password changes successfully")
        return redirect('/device-list/')
    return render(request, template_name = template_name, context=context)

def dashboard(request):
    resp = user_login_access(request)
    if  resp:
        return resp
    return redirect('/welcome/')

class Dashboard(TemplateView):
    template_name = "dashboard.html"
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
        states            = get_all_states()
        years.sort()
        context = {
            'devises'               : devises,
            'chart_data'            : chart_date,
            'devise_name'           : devise_name,
            'devise_counts'         : len(devises),
            'api_counts'            : len(DeviseApis.objects.all()),
            'dynamic_fields'        : len(ColumnName.objects.all()),
            'notification_counts'   : len(ContactDetails.objects.all()),
            'notification_active'   : notifications_all.filter(status=True),
            'notification_inactive' : notifications_all.filter(status=False),
            'years'                 : years,
            'states'                : states,
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
    
def download_api_response_pdf(request, **kwargs):
    from django.http import FileResponse
    import io
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import letter
    from django.http import FileResponse
    import os

    api = DeviseApis.objects.get(pk = kwargs['pk'])
    lines = []

    # craete byte streem buffer
    beffer = io.BytesIO()
    # create canvas
    c = canvas.Canvas(beffer, pagesize = (595.27,841.89), bottomup = 0)
    image = os.path.join(os.getcwd()) + '\static\logo3.PNG'
    c.drawImage(image, 450, 50, 100, 40) # adding image x, y, width, eight
    # create a text object
    textob = c.beginText()
    textob.setTextOrigin(inch, inch)
    textob.setFont('Helvetica', 14)

    # add some lines to text
    

    # lines = [
    #     'Line1',
    #     'Line1',
    #     'Line1',
    #     'Line1',
    # ]
    # for line in lines:
    #     textob.textLine(line)
    textob.textLine(f'                 ArkaShine Innovations Pvt Ltd')
    textob.setFont('Helvetica', 10)
    if 'pk' in  kwargs:
        api = DeviseApis.objects.get(pk=kwargs['pk'])
        crops_data = FertilizerCalculation.get_All_crops(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
        device_location = DeviseLocation.objects.filter(devise=api.device)
        textob.textLine(f'API call time :  {api.created_at}')
        textob.textLine(f'Crop          :  {api.crop_type}')
        textob.textLine(f'N             :  {api.nitrogen}')
        textob.textLine(f'P             :  {api.phosphorous}')
        textob.textLine(f'K             :  {api.potassium}')
        textob.textLine(f'PH            :  {api.ph}')
        textob.textLine(f'EC            :  {api.ec}')
        textob.textLine(f'OC            :  {api.oc}')
        if (device_location) : 
            device_location = device_location.first()
            textob.textLine(f'latitude          :  {device_location.latitude}')
            textob.textLine(f'longitude          :  {device_location.longitude}')
        textob.textLine(f'Phone         :  +91 9611297893')
        textob.textLine(f'Area name     :  {api.area_name}')
        textob.textLine(f'THE RECOMMENDED DOSES OF FERTILIZER FOR CROP "{api.crop_type}" ARE:')
        for crop_fertilizer_data in crops_data['crop_fertilizer']:
            for crop_data in crop_fertilizer_data:
                textob.textLine('---->'+crop_data)
            textob.textLine(' ')
        textob.textLine('Remedy, Fertility, Fym and Target yield')
        for crop_fym_data in crops_data['fym']:
            for fym in crop_fym_data:
                textob.textLine('---->'+fym)
    else:
        textob.textLine('no data available')

    textob.setFillColorCMYK(0.8,0,0,0.3)
    textob.textLine(' ')
    textob.textLine('Address : H. NO.9.1 2-226, 11th Cross, Bhawani Rice Mill Road')
    textob.textLine('Vidyanagar colony, Bidar, Karnataka, lndia, 585403')
    c.drawText(textob)
    c.showPage()
    c.save()
    beffer.seek(0)

    return FileResponse(beffer, as_attachment=True, filename="recomanded.pdf")

    
def download_api_response_csv(request, **kwargs):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type = 'text/csv')
    response['Content-Disposition'] = 'attachment; filename = response.csv'
    writer = csv.writer(response)
    if 'pk' in  kwargs:
        api = DeviseApis.objects.get(pk=kwargs['pk'])
        crops_data = FertilizerCalculation.get_All_crops(api.nitrogen, api.phosphorous, api.potassium, api.ph, api.ec, api.oc, api.crop_type)
        rows = get_downloadable_data_format(crops_data, api.crop_type, api.created_at)
    else:
        rows = [['no data available']]
    writer.writerows(rows)
    return response

def dynamic_fields(request, **kwargs):
    resp = user_login_access(request)
    if  resp:
        return resp
    template_name = 'dynamic_fields.html'
    columns = UserFuncrtions.get_all_dynamic_fields()
    context = {
        'columns' : columns,
        'columns_count' : len(columns),
    }
    return render(request, template_name = template_name, context=context)

def delete_field(request, id):
    field = ColumnName.objects.get(id=id)
    field.delete()
    messages.success(request, "Field deleted successfully.")
    return redirect('/dynamic_fields/')

def add_field(request):
    resp = user_login_access(request)
    if  resp:
        return resp
    template_name = "add_field.html"
    if request.method== 'GET':
        return render(request, template_name = template_name)
    elif request.method == 'POST':
        field_name = request.POST['field'].strip().replace(' ', '_')
        if field_name:
            ColumnName.objects.create(field_name=field_name)
            messages.success(request, "Field added successfully.")
            return redirect('/dynamic_fields/')
        else :
            messages.error(request, "Please enter valid field name.")
            return redirect('/add_field/')


class UpdateDeviceLocation(UpdateView):
    model = DeviseLocation
    fields = ['latitude', 'longitude']
    template_name = 'update_location.html'

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.request.POST['success']})

class AddDeviceLocation(CreateView):
    model = DeviseLocation
    fields = ['devise', 'latitude', 'longitude']
    template_name = 'update_location.html'

    def get_context_data(self, **kwargs):
        context = super(AddDeviceLocation, self).get_context_data(**kwargs)
        pk = self.kwargs['pk']
        messages.success(self.request, "Location updated successfully")
        return context

    def get_success_url(self):
        return reverse('device-details', kwargs={'pk': self.request.POST['success']})

    def get_initial(self):
        return {
        'devise':self.kwargs['pk'],
    }