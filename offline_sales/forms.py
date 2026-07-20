# offline_sales/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import StoreSettings, OfflineCustomer


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = [
            'store_name', 'store_logo', 'store_address', 'store_phone', 
            'store_email', 'store_website', 'gst_number', 'pan_number',
            'invoice_prefix', 'invoice_start_number', 'terms_conditions', 'footer_text'
        ]
        widgets = {
            'store_name': forms.TextInput(attrs={'class': 'form-control'}),
            'store_logo': forms.FileInput(attrs={'class': 'form-control'}),
            'store_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'store_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'store_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'store_website': forms.URLInput(attrs={'class': 'form-control'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control'}),
            'pan_number': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_start_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'terms_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'footer_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class OfflineCustomerForm(forms.ModelForm):
    class Meta:
        model = OfflineCustomer
        fields = [
            'first_name', 'last_name', 'phone', 'email', 'address', 'notes'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Enter address'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Add notes...'}),
        }
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove any non-digit characters
            phone = ''.join(filter(str.isdigit, phone))
            if len(phone) < 10:
                raise forms.ValidationError('Phone number must be at least 10 digits')
        return phone

# offline_sales/forms.py - Ensure Decimal handling

class OfflineSalePaymentForm(forms.Form):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('online', 'Online'),
    ]
    
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHODS,
        label='Payment Method',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    payment_reference = forms.CharField(
        max_length=100,
        required=False,
        label='Payment Reference (Optional)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transaction ID, Card Number, etc.'})
    )
    amount_received = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label='Amount Received',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    change_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label='Change Amount',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'})
    )
    
    def clean_amount_received(self):
        amount = self.cleaned_data.get('amount_received')
        if amount and amount <= 0:
            raise ValidationError('Amount received must be greater than 0.')
        return amount