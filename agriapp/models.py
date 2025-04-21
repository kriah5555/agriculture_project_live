from django.db import models
from django.contrib.auth.models import User

# Create your models here.

from . import FertilizerCalculation as f

CROP_LIST        = f.get_crop_list()
DEVICE_CHOICES   = [('soilsaathi', 'Soil Saathi'),('atmo_sense', 'Atmo Sense'), ('soil_life', 'SoilLIFE')]

SOIL_SAATHI_FIELDS  = {
    'id'                   : 'ID',
    'tag'                  : 'Tag',
    'electrical_conduction': 'Electrical Conduction',
    'nitrogen'             : 'Nitrogen',
    'phosphorous'          : 'Phosphorous',
    'potassium'            : 'Potassium',
    'calcium'              : 'Calcium',
    'magnesium'            : 'Magnesium',
    'sulphur'              : 'Sulphur',
    'zinc'                 : 'Zinc',
    'manganese'            : 'Manganese',
    'iron'                 : 'Iron',
    'copper'               : 'Copper',
    'boron'                : 'Boron',
    'molybdenum'           : 'Molybdenum',
    'chlorine'             : 'Chlorine',
    'nickel'               : 'Nickel',
    'organic_carboa'       : 'Organic Carbon',
    'ph'                   : 'Ph',
    'ec'                   : 'Ec',
    'oc'                   : 'Oc',
    'crop_type'            : 'Crop Type',
    'created_at'           : 'Requested At',
    'latitude'             : 'Latitude',
    'longitude'            : 'Longitude',
}

ATMO_SENSE_FIELDS = {
    'id'        : 'ID',
    'image_path': 'Image',
    'field1'    : "Soil Temp",
    'field2'    : "soil Moisture",
    'field3'    : "Atmos Temp",
    'field4'    : "Atmos Humidity",
    'field5'    : "Light Intensity",
    'created_at': 'Requested At',
}

SOIL_LIFE_FIELDS  = {
    'id'        : 'ID',
    'image_path': 'Image',
    'field1'    : "Co2",
    'field2'    : "Methane",
    'field3'    : "Ammonia",
    'field4'    : "Nitrous Oxide",
    'field5'    : "Soil Temperature",
    'field6'    : "Soil Moisture",
    'field7'    : "Atmospheric Pressure",
    'created_at': 'Requested At',
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

    def __str__(self):
        return f"{self.device.devise_type}-{self.device.user.username}-{self.device.name}"

class DeviseApisFields(models.Model):
    device     = models.ForeignKey(to='Devise', on_delete=models.CASCADE)
    image_path = models.CharField(max_length=255, null=True, blank=True)
    field1     = models.FloatField(default=0.0) # Soil Temp
    field2     = models.FloatField(default=0.0) # soil Moisture
    field3     = models.FloatField(default=0.0) # Atmos Temp
    field4     = models.FloatField(default=0.0) # Atmos Humidity
    field5     = models.FloatField(default=0.0) # Light Intensity
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
    crop_type = models.CharField(max_length=255, choices=CROP_LIST, null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

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


class ColumnName(models.Model):
    field_name = models.CharField(max_length = 255, unique=True)

class ColumnData(models.Model):
    field       = models.ForeignKey(to = 'ColumnName', on_delete = models.CASCADE)
    api         = models.ForeignKey(to = 'DeviseApis', on_delete = models.CASCADE, unique = True)
    field_value = models.FloatField(default = 0.0)