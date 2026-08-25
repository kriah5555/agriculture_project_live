from django.db import models
from django.contrib.auth.models import User

# Create your models here.

from . import FertilizerCalculation as f

CROP_LIST      = f.get_crop_list()

DEVICE_NAMES = {
    'soilsaathi'    : 'SoiLENZ',
    'atmo_sense'    : 'SoilSparsh',
    'soil_life'     : 'SoilLIFE',
    'ph_bottle'     : 'PHBottle',
    'soil_map'      : 'SoilMap',
    'carbon_credits': 'CarbonCredits',
    'leaflenz'      : 'LeafLenz',
}

DEVICE_ICONS = {
    'soilsaathi'    : 'fa-leaf',
    'atmo_sense'    : 'fa-wind',
    'soil_life'     : 'fa-seedling',
    'ph_bottle'     : 'fa-flask',
    'soil_map'      : 'fa-map',
    'carbon_credits': 'fa-coins',
    'leaflenz'      : 'fa-camera',
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

LEAFLENZ_FIELDS = {
    'id'        : 'ID',
    'tag'       : 'Predicted Label',
    'image_path': 'Leaf Image',
    'field1'    : 'Confidence (%)',
    'latitude'  : 'Latitude',
    'longitude' : 'Longitude',
    'created_at': 'Scanned At',
}

class ContactDetails(models.Model):
    name       = models.CharField(max_length=255)
    phone      = models.CharField(max_length=255, unique=True)
    mail       = models.EmailField(unique=True)
    message    = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    status     = models.BooleanField(default=True)

    def __str__(self):
        return f"Contact: {self.name} | {self.mail or self.phone}"

class Devise(models.Model):
    name           = models.CharField(max_length=255)
    serial_no      = models.CharField(max_length=255, unique=True, blank=True, null=True, default=None)
    devise_id      = models.CharField(max_length=255, unique=True, blank=True, null=True, default=None) #devise id or user name
    chipset_no     = models.CharField(max_length=255, unique=True, blank=True, null=True, default=None)
    email          = models.EmailField(blank=True, default='')
    phone          = models.CharField(max_length=255, blank=True, default='')
    address1       = models.CharField(max_length=255, blank=True, default='')
    address2       = models.CharField(max_length=255, blank=True, default='')
    purchase_date  = models.DateField(blank=True, null=True)
    time_of_sale   = models.TimeField(blank=True, null=True)
    warrenty       = models.DateField()
    amount_paid    = models.FloatField()
    balance_amount = models.FloatField(default=0)
    land           = models.FloatField(default=0.0)
    created_at     = models.DateTimeField(auto_now_add=True)
    devise_type    = models.CharField(max_length=255, choices = DEVICE_CHOICES, default='soilsaathi')
    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices', null=True, blank=True)

    def __str__(self):
        type_label  = DEVICE_NAMES.get(self.devise_type, self.devise_type)
        owner       = self.user.username if self.user_id else 'no-user'
        identifier  = self.devise_id or self.serial_no or f'pk:{self.pk}'
        return f"[{type_label}] {self.name or 'Unnamed'} ({identifier}) — {owner}"

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
        if not self.device_id:
            return f"SoiLENZ reading #{self.pk or 'new'}"
        type_label  = DEVICE_NAMES.get(self.device.devise_type, self.device.devise_type)
        owner       = self.device.user.username if self.device.user_id else 'no-user'
        date_str    = self.created_at.strftime('%d %b %Y %H:%M') if self.created_at else 'new'
        farmer_str  = f' | farmer:{self.farmer.farmer_name}' if self.farmer_id else ''
        return (f"[{type_label}] {self.device.name} / {owner}"
                f" — pH:{self.ph} EC:{self.ec} OC:{self.oc}"
                f"{farmer_str} | #{self.pk} {date_str}")

# CHANNEL_FIELD_MAP: incoming `channel_data[<key>]` request param -> ChannelData field name.
# Kept next to the model (rather than in the view) since both the API parser and any
# future list/export code need this same mapping.
CHANNEL_FIELD_MAP = {
    'a_val'      : 'ch_a',
    'b_val'      : 'ch_b',
    'c_val'      : 'ch_c',
    'd_val'      : 'ch_d',
    'e_val'      : 'ch_e',
    'f_val'      : 'ch_f',
    'g_val'      : 'ch_g',
    'h_val'      : 'ch_h',
    'r_val'      : 'ch_r',
    'i_val'      : 'ch_i',
    's_val'      : 'ch_s',
    'j_val'      : 'ch_j',
    't_val'      : 'ch_t',
    'u_val'      : 'ch_u',
    'v_val'      : 'ch_v',
    'w_val'      : 'ch_w',
    'k_val'      : 'ch_k',
    'l_val'      : 'ch_l',
    'u2_val'     : 'ch_u2',
    'v2_val'     : 'ch_v2',
    'w2_val'     : 'ch_w2',
    'ph_val'     : 'ph',
    'ec_val'     : 'ec',
    'oc_val'     : 'oc_percent',
    'ca_val'     : 'ca_meq',
    'mg_val'     : 'mg_meq',
    'n_val'      : 'n_kg_ha',
    'p2o5_val'   : 'p2o5',
    'k2o_val'    : 'k2o',
    'so4_val'    : 'so4',
    'fe_val'     : 'fe_ppm',
    'mn_val'     : 'mn_ppm',
    'cu_val'     : 'cu_ppm',
    'zn_val'     : 'zn_ppm',
    'boron_val'  : 'boron_ppm',
}

# CHANNEL_EXPORT_COLUMNS: (field_name, display header) in a fixed order, used by both
# the admin list/detail view and the xlsx export so the column order stays in sync.
CHANNEL_EXPORT_COLUMNS = [
    ('ch_a',       'A 410nm'),
    ('ch_b',       'B 435nm'),
    ('ch_c',       'C 460nm'),
    ('ch_d',       'D 485nm'),
    ('ch_e',       'E 510nm'),
    ('ch_f',       'F 535nm'),
    ('ch_g',       'G 560nm'),
    ('ch_h',       'H 585nm'),
    ('ch_r',       'R 610nm'),
    ('ch_i',       'I 645nm'),
    ('ch_s',       'S 680nm'),
    ('ch_j',       'J 705nm'),
    ('ch_t',       'T 730nm'),
    ('ch_u',       'U 760nm'),
    ('ch_v',       'V 810nm'),
    ('ch_w',       'W 860nm'),
    ('ch_k',       'K 900nm'),
    ('ch_l',       'L 940nm'),
    ('ch_u2',      'U 320nm'),
    ('ch_v2',      'V 280nm'),
    ('ch_w2',      'W 200nm'),
    ('ph',         'PH'),
    ('ec',         'EC'),
    ('oc_percent', 'OC%'),
    ('ca_meq',     'Ca (meq)'),
    ('mg_meq',     'Mg (meq)'),
    ('n_kg_ha',    'N Kg/ha'),
    ('p2o5',       'P2O5'),
    ('k2o',        'K2O'),
    ('so4',        'SO4'),
    ('fe_ppm',     'Fe (ppm)'),
    ('mn_ppm',     'Mn (ppm)'),
    ('cu_ppm',     'Cu (ppm)'),
    ('zn_ppm',     'Zn (ppm)'),
    ('boron_ppm',  'B (ppm)'),
]

class ChannelData(models.Model):
    """
    Per-channel sensor snapshot of each add_data API call, kept alongside DeviseApis.
    One field per spectral channel / derived soil parameter (rather than a JSON blob)
    so rows are directly listable, filterable, and exportable as columns.
    Rows older than RETENTION_DAYS are purged automatically — this table is
    short-term only, not a permanent record.
    """
    RETENTION_DAYS = 180

    device       = models.ForeignKey(to='Devise', on_delete=models.CASCADE, null=True, blank=True)
    api          = models.ForeignKey(to='DeviseApis', on_delete=models.CASCADE, null=True, blank=True,
                                      help_text='The specific add_data API call this channel data came from')

    ch_a         = models.FloatField(null=True, blank=True, help_text='A 410nm')
    ch_b         = models.FloatField(null=True, blank=True, help_text='B 435nm')
    ch_c         = models.FloatField(null=True, blank=True, help_text='C 460nm')
    ch_d         = models.FloatField(null=True, blank=True, help_text='D 485nm')
    ch_e         = models.FloatField(null=True, blank=True, help_text='E 510nm')
    ch_f         = models.FloatField(null=True, blank=True, help_text='F 535nm')
    ch_g         = models.FloatField(null=True, blank=True, help_text='G 560nm')
    ch_h         = models.FloatField(null=True, blank=True, help_text='H 585nm')
    ch_r         = models.FloatField(null=True, blank=True, help_text='R 610nm')
    ch_i         = models.FloatField(null=True, blank=True, help_text='I 645nm')
    ch_s         = models.FloatField(null=True, blank=True, help_text='S 680nm')
    ch_j         = models.FloatField(null=True, blank=True, help_text='J 705nm')
    ch_t         = models.FloatField(null=True, blank=True, help_text='T 730nm')
    ch_u         = models.FloatField(null=True, blank=True, help_text='U 760nm')
    ch_v         = models.FloatField(null=True, blank=True, help_text='V 810nm')
    ch_w         = models.FloatField(null=True, blank=True, help_text='W 860nm')
    ch_k         = models.FloatField(null=True, blank=True, help_text='K 900nm')
    ch_l         = models.FloatField(null=True, blank=True, help_text='L 940nm')
    ch_u2        = models.FloatField(null=True, blank=True, help_text='U 320nm')
    ch_v2        = models.FloatField(null=True, blank=True, help_text='V 280nm')
    ch_w2        = models.FloatField(null=True, blank=True, help_text='W 200nm')

    ph           = models.FloatField(null=True, blank=True)
    ec           = models.FloatField(null=True, blank=True)
    oc_percent   = models.FloatField(null=True, blank=True, help_text='OC %')
    ca_meq       = models.FloatField(null=True, blank=True, help_text='Ca (meq)')
    mg_meq       = models.FloatField(null=True, blank=True, help_text='Mg (meq)')
    n_kg_ha      = models.FloatField(null=True, blank=True, help_text='N Kg/ha')
    p2o5         = models.FloatField(null=True, blank=True)
    k2o          = models.FloatField(null=True, blank=True)
    so4          = models.FloatField(null=True, blank=True)
    fe_ppm       = models.FloatField(null=True, blank=True, help_text='Fe (ppm)')
    mn_ppm       = models.FloatField(null=True, blank=True, help_text='Mn (ppm)')
    cu_ppm       = models.FloatField(null=True, blank=True, help_text='Cu (ppm)')
    zn_ppm       = models.FloatField(null=True, blank=True, help_text='Zn (ppm)')
    boron_ppm    = models.FloatField(null=True, blank=True, help_text='B (ppm)')

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"ChannelData #{self.pk} ({self.created_at})"

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
        if not self.device_id:
            return f"Sensor reading #{self.pk or 'new'}"
        type_label = DEVICE_NAMES.get(self.device.devise_type, self.device.devise_type)
        owner      = self.device.user.username if self.device.user_id else 'no-user'
        date_str   = self.created_at.strftime('%d %b %Y %H:%M') if self.created_at else 'new'
        tag_str    = f' [{self.tag}]' if self.tag else ''
        farmer_str = f' | farmer:{self.farmer.farmer_name}' if self.farmer_id else ''
        return (f"[{type_label}] {self.device.name} / {owner}"
                f"{tag_str}{farmer_str} | #{self.pk} {date_str}")

class DeviseLocation(models.Model):
    devise     = models.ForeignKey(to='Devise', on_delete=models.CASCADE, unique=True)
    latitude   = models.FloatField(default=15.3173)
    longitude  = models.FloatField(default=75.7139)
    status     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        device_str = str(self.devise) if self.devise_id else 'Unknown device'
        return f"Location: {device_str} @ ({self.latitude:.4f}, {self.longitude:.4f})"

class APICountThreshold(models.Model):
    devise = models.ForeignKey(to='Devise', on_delete=models.CASCADE, unique=True)
    red    = models.IntegerField(default=100)
    orange = models.IntegerField(default=80)
    blue   = models.IntegerField(default=50)
    green  = models.IntegerField(default=20)

    def __str__(self):
        device_str = str(self.devise) if self.devise_id else 'Unknown device'
        return f"Threshold [{device_str}]: Red={self.red} Orange={self.orange} Blue={self.blue} Green={self.green}"


class UserRequest(models.Model):
    """
    Stores user-initiated requests (forgot password, change password) as well as
    system-raised device usage alerts (usage_warning, usage_limit_reached).
    Each entry appears in the admin Notifications page as an unread item
    until an admin marks it resolved.
    """
    FORGOT_PASSWORD       = 'forgot_password'
    CHANGE_PASSWORD       = 'change_password'
    SOIL_PARTNER_INTEREST = 'soil_partner_interest'
    USAGE_WARNING         = 'usage_warning'
    USAGE_LIMIT_REACHED   = 'usage_limit_reached'
    REQUEST_TYPES = [
        (FORGOT_PASSWORD,       'Forgot Password'),
        (CHANGE_PASSWORD,       'Change Password Request'),
        (SOIL_PARTNER_INTEREST, 'Soil Partner Interest'),
        (USAGE_WARNING,         'Usage Warning'),
        (USAGE_LIMIT_REACHED,   'Usage Limit Reached'),
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
    device       = models.ForeignKey(
        'Devise', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='usage_requests',
        help_text='Set for usage_warning / usage_limit_reached alerts, linking back to the device.',
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

    def __str__(self):
        return f"Column: {self.field_name}"

class ColumnData(models.Model):
    field       = models.ForeignKey(to = 'ColumnName', on_delete = models.CASCADE)
    api         = models.ForeignKey(to = 'DeviseApis', on_delete = models.CASCADE, unique = True)
    field_value = models.FloatField(default = 0.0)

    def __str__(self):
        field_name = self.field.field_name if self.field_id else '?'
        return f"ColumnData: {field_name} = {self.field_value} (reading #{self.api_id})"


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
    address        = models.CharField(max_length=255, blank=True, default='')
    latitude       = models.FloatField(null=True, blank=True)
    longitude      = models.FloatField(null=True, blank=True)
    land_area      = models.FloatField(default=0.0)
    survey_number  = models.CharField(max_length=50, blank=True, default='')
    plot_number    = models.CharField(max_length=50, blank=True, default='')
    crop           = models.CharField(max_length=255)
    season         = models.CharField(max_length=10, choices=SEASON_CHOICES)
    status         = models.CharField(max_length=20, choices=FARMER_STATUS_CHOICES, default='registered')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        partner = self.soil_partner.username if self.soil_partner_id else 'no-partner'
        return f"{self.farmer_name} ({self.village}, {self.district}) — SP: {partner} [{self.get_status_display()}]"

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


# ── Soil Visualizer (soil_visualizer app: plot boundary + soil-sample points) ──

class Plot(models.Model):
    devise     = models.ForeignKey(Devise, on_delete=models.CASCADE, related_name='soil_map_plots')
    name       = models.CharField(max_length=255)
    geometry   = models.JSONField(help_text="GeoJSON Polygon of the land parcel")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.devise.name})"


class Point(models.Model):
    """
    A soil-sample point placed on the map within a Plot boundary. Either
    linked to an existing reading (parameters pulled live from it — "Add
    position" flow, and a single reading can have more than one point) or
    fully manual (parameters entered by hand — "Add manual point" flow, for
    ground-truth samples the device never took).
    """
    devise      = models.ForeignKey(Devise, on_delete=models.CASCADE, related_name='soil_map_points')
    plot        = models.ForeignKey(Plot, on_delete=models.CASCADE, null=True, blank=True, related_name='points')
    reading     = models.ForeignKey(DeviseApis, on_delete=models.CASCADE, null=True, blank=True, related_name='soil_map_points')
    coordinates = models.JSONField(null=True, blank=True, help_text="{'lat': <float>, 'lon': <float>} — auto-filled from the plot's polygon centroid when not given")
    parameters  = models.JSONField(default=dict, blank=True, help_text="Manual parameter readings — only used when not linked to a reading")
    sample_date = models.DateField()
    notes       = models.TextField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sample_date']

    def save(self, *args, **kwargs):
        # Auto-fill coordinates from the plot's polygon centroid when not given —
        # the normal path now, since a point is created by drawing a boundary
        # rather than picking a lat/long directly.
        if (not self.coordinates or self.coordinates.get('lat') is None or self.coordinates.get('lon') is None) and self.plot_id and self.plot.geometry:
            from shapely.geometry import shape
            try:
                centroid = shape(self.plot.geometry).centroid
                self.coordinates = {'lat': centroid.y, 'lon': centroid.x}
            except Exception:
                pass
        super().save(*args, **kwargs)

    def get_parameters(self):
        """Live parameter dict — from the linked reading if present, else the manual JSON."""
        if self.reading_id:
            r = self.reading
            return {
                'ph': r.ph, 'ec': r.ec, 'n': r.nitrogen, 'p': r.phosphorous, 'k': r.potassium,
                'organic_carbon': r.oc, 's': r.sulphur, 'fe': r.iron, 'zn': r.zinc,
                'cu': r.copper, 'b': r.boron, 'mn': r.manganese,
            }
        return self.parameters or {}

    def __str__(self):
        return f"Point {self.id} @ {self.devise.name}"