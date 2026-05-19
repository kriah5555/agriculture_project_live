from django.db import models
from django.contrib.auth.models import User

# Create your models here.

from . import FertilizerCalculation as f

CROP_LIST      = f.get_crop_list()

DEVICE_NAMES = {
    'soilsaathi': 'SoiLENZ',
    'atmo_sense': 'SoilSparsh',
    'soil_life' : 'SoilLIFE',
    'ph_bottle' : 'PHBottle',
    'soil_map'  : 'SoilMap',
}

DEVICE_CHOICES = list(DEVICE_NAMES.items())

SOIL_SAATHI_FIELDS = {
    'id'                   : 'ID',
    'tag'                  : 'Tag',
    #'electrical_conduction': 'Electrical Conduction (dS/m)',
    'nitrogen'             : 'Nitrogen(kg/ha)',
    'phosphorous'          : 'P(kg/ha)',
    'potassium'            : 'K(kg/ha)',
    'calcium'              : 'Ca(meq/100g)',
    'magnesium'            : 'Mg(meq/100g)',
    'sulphur'              : 'S(ppm)',
    'zinc'                 : 'Zn(ppm)',
    'manganese'            : 'Mn(ppm)',
    'iron'                 : 'Fe(ppm)',
    'copper'               : 'Cu(ppm)',
    'boron'                : 'B(ppm)',
    # 'molybdenum'           : 'Molybdenum (ppm)',
    # 'chlorine'             : 'Chlorine (ppm)',
    # 'nickel'               : 'Nickel (ppm)',
    # 'organic_carboa'       : 'Organic Carbon (%)',
    'ph'                   : 'Ph(pH)',
    'ec'                   : 'Ec(dS/m)',
    'oc'                   : 'Oc(%)',
    'crop_type'            : 'Crop Type',
    'created_at'           : 'Requested At',
    'latitude'             : 'Latitude',
    'longitude'            : 'Longitude',
}

SOIL_SAATHI_FIELD_THRESHOLDS = {
    'nitrogen'             : {'min': 280, 'max': 560},
    'phosphorous'          : {'min': 22, 'max': 56},
    'potassium'            : {'min': 141, 'max': 336},
    'sulphur'              : {'min': 10, 'max': 20},
    'zinc'                 : {'min': 0.6, 'max': 0.6},
    'boron'                : {'min': 0.5, 'max': 0.5},
    'calcium'              : {'min': 1.5, 'max': 1.5},
    'magnesium'            : {'min': 1.0, 'max': 1.0},
    'manganese'            : {'min': 5.0, 'max': 9.0},
    'copper'               : {'min': 0.6, 'max': 1.0},
    'iron'                 : {'min': 6.5, 'max': 10.5},
    'organic_carboa'       : {'min': 0.5, 'max': 0.75},
    'oc'                   : {'min': 0.5, 'max': 0.75},
    'ph'                   : {'min': 6.5, 'max': 7.3},
    'electrical_conduction': {'min': 1.0, 'max': 4.0},
    'ec'                   : {'min': 1.0, 'max': 4.0}
}

ATMO_SENSE_FIELDS = {
    'id'        : 'ID',
    'tag'       : 'Tag',
    'image_path': 'Image',
    'field1'    : "Soil Temp (°C)",
    'field2'    : "Soil Moisture (%)",
    'field3'    : "Atmos Temp (°C)",
    'field4'    : "Atmos Humidity (%)",
    'field5'    : "Light Intensity (lux)",
    'latitude'  : 'Latitude',
    'longitude' : 'Longitude',
    'created_at': 'Requested At',
}

SOIL_LIFE_FIELDS = {
    'id'        : 'ID',
    'tag'       : 'Tag',
    'image_path': 'Image',
    'field1'    : "CO₂ (ppm)",
    'field2'    : "Methane (ppm)",
    'field3'    : "Ammonia (ppm)",
    'field4'    : "Nitrous Oxide (ppm)",
    'field5'    : "Temperature (°C)",
    'field6'    : "Humidity (%)",
    'field7'    : "Atmospheric Pressure (hPa)",
    'field8'    : "Microbial Content (%)",
    'latitude'  : 'Latitude',
    'longitude' : 'Longitude',
    'created_at': 'Requested At',
}

PH_BOTTLE_FIELDS = {
    'id'        : 'ID',
    'tag'       : 'Tag',
    'field1'    : "pH Value",
    'field2'    : "pH Voltage (mV)",
    'field3'    : "EC Value (mS/cm)",
    'field4'    : "EC Voltage (mV)",
    'latitude'  : 'Latitude',
    'longitude' : 'Longitude',
    'created_at': 'Requested At',
}

SOIL_MAP_FIELDS = {
    'id'        : 'ID',
    'tag'       : 'Tag',
    'field1'    : 'pH',
    'field2'    : 'EC (dS/m)',
    'field3'    : 'Nitrogen (kg/ha)',
    'field4'    : 'Phosphorus (kg/ha)',
    'field5'    : 'Potassium (kg/ha)',
    'field6'    : 'Organic Carbon (%)',
    'field7'    : 'Sulfur (ppm)',
    'field8'    : 'Iron/Fe (ppm)',
    'field9'    : 'Zinc/Zn (ppm)',
    'field10'   : 'Copper/Cu (ppm)',
    'field11'   : 'Boron/B (ppm)',
    'field12'   : 'Manganese/Mn (ppm)',
    'field13'   : 'Sand (%)',
    'field14'   : 'Clay (%)',
    'field15'   : 'Silt (%)',
    'field16'   : 'NDVI',
    'field17'   : 'Temperature (°C)',
    'field18'   : 'Rainfall (mm)',
    'field19'   : 'Elevation (m)',
    'latitude'  : 'Latitude',
    'longitude' : 'Longitude',
    'created_at': 'Uploaded At',
}

class ContactDetails(models.Model):
    name       = models.CharField(max_length=255)
    phone      = models.CharField(max_length=255, unique=True)
    mail       = models.EmailField(unique=True)
    message    = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    status     = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Devise(models.Model):
    name           = models.CharField(max_length=255)
    serial_no      = models.CharField(max_length=255, unique=True)
    devise_id      = models.CharField(max_length=255, unique=True) #devise id or user name
    chipset_no     = models.CharField(max_length=255, unique=True)
    email          = models.EmailField()
    phone          = models.CharField(max_length=255)
    address1       = models.CharField(max_length=255)
    address2       = models.CharField(max_length=255)
    purchase_date  = models.DateField()
    time_of_sale   = models.TimeField()
    warrenty       = models.DateField()
    amount_paid    = models.FloatField()
    balance_amount = models.FloatField(default=0)
    land           = models.FloatField(default=0.0)
    created_at     = models.DateTimeField(auto_now_add=True)
    devise_type    = models.CharField(max_length=255, choices = DEVICE_CHOICES, default='soilsaathi')
    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices', null=True, blank=True)

    def __str__(self):
        return self.name + ' ' + self.devise_id

class DeviseApis(models.Model):
    device                = models.ForeignKey(to='Devise', on_delete=models.CASCADE)
    farmer                = models.ForeignKey('Farmer', on_delete=models.SET_NULL, null=True, blank=True, related_name='soilsaathi_readings')
    area_name             = models.CharField(max_length=255)
    devise_id             = models.CharField(max_length=255)
    serial_no             = models.CharField(max_length=255)
    electrical_conduction = models.FloatField(default=0.0)
    nitrogen              = models.FloatField(default=0.0)
    phosphorous           = models.FloatField(default=0.0)
    potassium             = models.FloatField(default=0.0)
    calcium               = models.FloatField(default=0.0)
    magnesium             = models.FloatField(default=0.0)
    sulphur               = models.FloatField(default=0.0)
    zinc                  = models.FloatField(default=0.0)
    manganese             = models.FloatField(default=0.0)
    iron                  = models.FloatField(default=0.0)
    copper                = models.FloatField(default=0.0)
    boron                 = models.FloatField(default=0.0)
    molybdenum            = models.FloatField(default=0.0)
    chlorine              = models.FloatField(default=0.0)
    nickel                = models.FloatField(default=0.0)
    organic_carboa        = models.FloatField(default=0.0)
    ph                    = models.FloatField(default=0.0)
    ec                    = models.FloatField(default=0.0)
    oc                    = models.FloatField(default=0.0)
    crop_type             = models.CharField(max_length=255, choices = CROP_LIST)
    tag                   = models.CharField( max_length=255, null=True, blank=True, default=None)
    latitude              = models.FloatField(default=0.0)
    longitude             = models.FloatField(default=0.0)
    created_at            = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device.devise_type}-{self.device.user.username}-{self.device.name}"

class DeviseApisFields(models.Model):
    device     = models.ForeignKey(to='Devise', on_delete=models.CASCADE)
    farmer     = models.ForeignKey('Farmer', on_delete=models.SET_NULL, null=True, blank=True, related_name='sensor_readings')
    tag        = models.CharField( max_length=255, null=True, blank=True, default=None)
    image_path = models.CharField(max_length=255, null=True, blank=True)
    field1     = models.FloatField(default=0.0)
    field2     = models.FloatField(default=0.0)
    field3     = models.FloatField(default=0.0)
    field4     = models.FloatField(default=0.0)
    field5     = models.FloatField(default=0.0)
    field6     = models.FloatField(default=0.0)
    field7     = models.FloatField(default=0.0)
    field8     = models.FloatField(default=0.0)
    field9     = models.FloatField(default=0.0)
    field10    = models.FloatField(default=0.0)
    field11    = models.FloatField(default=0.0)
    field12    = models.FloatField(default=0.0)
    field13    = models.FloatField(default=0.0)
    field14    = models.FloatField(default=0.0)
    field15    = models.FloatField(default=0.0)
    field16    = models.FloatField(default=0.0)
    field17    = models.FloatField(default=0.0)
    field18    = models.FloatField(default=0.0)
    field19    = models.FloatField(default=0.0)
    crop_type  = models.CharField(max_length=255, choices=CROP_LIST, null=True, blank=True, default=None)
    latitude   = models.FloatField(null=True, blank=True, default=None)
    longitude  = models.FloatField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.device.devise_type}-{self.device.user.username}-{self.device.name}"

class DeviseLocation(models.Model):
    devise     = models.ForeignKey(to='Devise', on_delete=models.CASCADE, unique=True)
    latitude   = models.FloatField(default=15.3173)
    longitude  = models.FloatField(default=75.7139)
    status     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.devise.name

class APICountThreshold(models.Model):
    devise = models.ForeignKey(to='Devise', on_delete=models.CASCADE, unique=True)
    red    = models.IntegerField(default=100)
    orange = models.IntegerField(default=80)
    blue   = models.IntegerField(default=50)
    green  = models.IntegerField(default=20)

    def __str__(self):
        return self.devise.name


class UserRequest(models.Model):
    """
    Stores user-initiated requests (forgot password, change password).
    Each entry appears in the admin Notifications page as an unread item
    until an admin marks it resolved.
    """
    FORGOT_PASSWORD       = 'forgot_password'
    CHANGE_PASSWORD       = 'change_password'
    SOIL_PARTNER_INTEREST = 'soil_partner_interest'
    REQUEST_TYPES = [
        (FORGOT_PASSWORD,       'Forgot Password'),
        (CHANGE_PASSWORD,       'Change Password Request'),
        (SOIL_PARTNER_INTEREST, 'Soil Partner Interest'),
    ]
    STATUS_PENDING  = 'pending'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    user         = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='requests'
    )
    username     = models.CharField(max_length=150)
    email        = models.EmailField()
    phone        = models.CharField(max_length=20, blank=True, default='')
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPES)
    message      = models.CharField(max_length=500, blank=True, default='')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_request_type_display()} — {self.username}"

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING


class ColumnName(models.Model):
    field_name = models.CharField(max_length = 255, unique=True)

class ColumnData(models.Model):
    field       = models.ForeignKey(to = 'ColumnName', on_delete = models.CASCADE)
    api         = models.ForeignKey(to = 'DeviseApis', on_delete = models.CASCADE, unique = True)
    field_value = models.FloatField(default = 0.0)


USER_TYPE_CHOICES = [
    ('current_user', 'Current User'),
    ('soil_partner', 'Soil Partner'),
]

class UserProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type    = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='current_user')
    state        = models.CharField(max_length=100, blank=True, default='')
    district     = models.CharField(max_length=100, blank=True, default='')
    city_village = models.CharField(max_length=100, blank=True, default='')
    amount_paid  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status       = models.BooleanField(default=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_profiles')
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_user_type_display()}"


SEASON_CHOICES = [
    ('kharif', 'Kharif'),
    ('rabi',   'Rabi'),
    ('zaid',   'Zaid'),
]

FARMER_STATUS_CHOICES = [
    ('registered',       'Registered'),
    ('re_registered',    'Re-Registered'),
    ('sample_collected', 'Sample Collected'),
    ('testing_done',     'Testing Done'),
    ('report_delivered', 'Report Delivered'),
]

FARMER_STATUS_BADGE = {
    'registered':       'secondary',
    're_registered':    'info',
    'sample_collected': 'primary',
    'testing_done':     'warning',
    'report_delivered': 'success',
}

class Farmer(models.Model):
    soil_partner   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='farmers')
    farmer_name    = models.CharField(max_length=255)
    phone          = models.CharField(max_length=15)
    email          = models.EmailField(blank=True, default='')
    aadhaar_number = models.CharField(max_length=12)
    farmer_image   = models.ImageField(upload_to='farmers/', null=True, blank=True)
    mobile         = models.CharField(max_length=15, blank=True, default='')
    state          = models.CharField(max_length=100)
    district       = models.CharField(max_length=100)
    village        = models.CharField(max_length=100)
    latitude       = models.FloatField(null=True, blank=True)
    longitude      = models.FloatField(null=True, blank=True)
    land_area      = models.FloatField(default=0.0)
    crop           = models.CharField(max_length=255)
    season         = models.CharField(max_length=10, choices=SEASON_CHOICES)
    status         = models.CharField(max_length=20, choices=FARMER_STATUS_CHOICES, default='registered')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.farmer_name

    def badge_class(self):
        return FARMER_STATUS_BADGE.get(self.status, 'secondary')


class FarmerStatusHistory(models.Model):
    farmer    = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name='status_history')
    status    = models.CharField(max_length=20, choices=FARMER_STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.farmer.farmer_name} - {self.get_status_display()} at {self.timestamp}"


class PartnerPayment(models.Model):
    """
    A payment record for a soil partner.
    Admin adds these to track how much a partner has paid.
    status: pending → admin created the record; paid → payment confirmed received.
    """
    STATUS_PENDING = 'pending'
    STATUS_PAID    = 'paid'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID,    'Paid'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    farmer      = models.ForeignKey('Farmer', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=500, blank=True, default='')
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at  = models.DateTimeField(auto_now_add=True)
    paid_at     = models.DateTimeField(null=True, blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_payments')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — ₹{self.amount} [{self.status}] on {self.created_at:%d %b %Y}"

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID


class PaymentAttachment(models.Model):
    payment = models.ForeignKey(PartnerPayment, on_delete=models.CASCADE, related_name='attachments')
    file    = models.FileField(upload_to='payment_attachments/')

    def __str__(self):
        return f"Attachment for payment {self.payment_id}"