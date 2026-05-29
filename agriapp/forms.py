from django import forms
from .models import ContactDetails, Devise

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactDetails
        fields = ['mail', 'phone', 'message', 'name']

# Device types that require devise_id to be filled
_STANDARD_DEVICE_TYPES = {'soilsaathi', 'atmo_sense', 'soil_life', 'ph_bottle'}
# Only Device ID is conditionally required (standard types only)
_CONDITIONAL_FIELDS    = ['devise_id']
# All other hardware/address/date fields are always optional for every device type
_ALWAYS_OPTIONAL       = [
    'serial_no', 'chipset_no', 'phone', 'email', 'address1', 'address2',
    'purchase_date', 'time_of_sale',
]

class DeviseForm(forms.ModelForm):
    class Meta:
        model = Devise
        fields = [
            'name',
            'serial_no',
            'devise_id',
            'chipset_no',
            'email',
            'phone',
            'address1',
            'address2',
            'purchase_date',
            'time_of_sale',
            'warrenty',
            'amount_paid',
            'balance_amount',
            'land',
            'devise_type',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Conditional fields: required only for standard device types (enforced in clean())
        for f in _CONDITIONAL_FIELDS:
            self.fields[f].required = False
        # Always-optional fields: never required for any device type
        for f in _ALWAYS_OPTIONAL:
            self.fields[f].required = False

    def clean(self):
        cleaned = super().clean()
        devise_type = cleaned.get('devise_type')
        if devise_type in _STANDARD_DEVICE_TYPES:
            for f in _CONDITIONAL_FIELDS:
                if not cleaned.get(f):
                    self.add_error(f, 'This field is required for this device type.')
        return cleaned