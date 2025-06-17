from django import forms
from .models import ContactDetails, Devise

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactDetails
        fields = ['mail', 'phone', 'message', 'name']

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
