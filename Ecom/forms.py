from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import User, Profile, Address

User = get_user_model()

# ========== CUSTOMER SIGNUP FORM ==========
class CustomerSignupForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}),
        validators=[validate_password]
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )
    terms_accepted = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must accept the terms and conditions'}
    )
    
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match')
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered')
        return email
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if User.objects.filter(phone=phone).exists():
                raise forms.ValidationError('This phone number is already registered')
        return phone

# ========== ADMIN SIGNUP FORM ==========
class AdminSignupForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}),
        validators=[validate_password]
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )
    admin_secret_key = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter admin secret key'}),
        required=True
    )
    
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        admin_secret_key = cleaned_data.get('admin_secret_key')
        
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match')
        
        if admin_secret_key != 'ADMIN@123':
            raise forms.ValidationError('Invalid admin secret key')
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered')
        return email
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            if User.objects.filter(phone=phone).exists():
                raise forms.ValidationError('This phone number is already registered')
        return phone

# ========== LOGIN FORM ==========
class LoginForm(forms.Form):
    login_identifier = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter email or phone number'
        }),
        label='Email or Phone'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'})
    )
    
    def clean_login_identifier(self):
        login_identifier = self.cleaned_data.get('login_identifier')
        if not login_identifier:
            raise forms.ValidationError('Please enter your email or phone number.')
        return login_identifier

# ========== OTP VERIFICATION FORM ==========
class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center otp-input',
            'placeholder': 'Enter 6-digit OTP',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autofocus': True
        })
    )

# ========== FORGOT PASSWORD FORM ==========
class ForgotPasswordForm(forms.Form):
    login_identifier = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter email or phone number'
        }),
        label='Email or Phone'
    )
    
    def clean_login_identifier(self):
        login_identifier = self.cleaned_data.get('login_identifier')
        if not login_identifier:
            raise forms.ValidationError('Please enter your email or phone number.')
        return login_identifier

# ========== RESET PASSWORD FORM ==========
class ResetPasswordForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password'}),
        validators=[validate_password]
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Passwords do not match')
        return cleaned_data

# ========== CHANGE PASSWORD FORM ==========
class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter current password'})
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password'}),
        validators=[validate_password]
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Passwords do not match')
        return cleaned_data

# ========== PROFILE UPDATE FORM ==========
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture', 'bio', 'date_of_birth', 'gender']
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Tell us about yourself'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
        }

# ========== USER UPDATE FORM ==========
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['full_name', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
        }
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Check if phone is used by another user
            if User.objects.filter(phone=phone).exclude(id=self.instance.id).exists():
                raise forms.ValidationError('This phone number is already registered')
        return phone

# ========== ADDRESS FORM ==========
class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'address_type', 'full_name', 'phone', 'address_line1', 
            'address_line2', 'landmark', 'city', 'state', 'pincode', 'country', 'is_default'
        ]
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'House number, street name'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apartment, suite, etc. (optional)'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nearby landmark (optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter city'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter state'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter pincode'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter country'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone and not phone.isdigit():
            raise forms.ValidationError('Phone number should contain only digits')
        if phone and len(phone) < 10:
            raise forms.ValidationError('Phone number must be at least 10 digits')
        return phone
    
    def clean_pincode(self):
        pincode = self.cleaned_data.get('pincode')
        if pincode and not pincode.isdigit():
            raise forms.ValidationError('Pincode should contain only digits')
        if pincode and len(pincode) != 6:
            raise forms.ValidationError('Pincode must be 6 digits')
        return pincode
    
from django import forms
from .models import (
    Category, SubCategory, Product, ProductImage, 
    ProductVariant, VariantImage, ProductReview
)

# ========== CATEGORY FORM ==========
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter category name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter description'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ========== SUBCATEGORY FORM ==========
class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = ['category', 'name', 'description', 'image', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter subcategory name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter description'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# ========== PRODUCT FORM ==========
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'brand', 'category', 'subcategory',
            'short_description', 'description', 'specifications', 'features',
            'color', 'size', 'weight', 'dimensions', 'material',
            'warranty_months', 'warranty_details',
            'price', 'discount_percentage',
            'stock_quantity', 'low_stock_threshold',
            'is_active', 'is_featured', 'is_new', 'is_best_seller'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique SKU'}),
            'brand': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brand name'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'subcategory': forms.Select(attrs={'class': 'form-control'}),
            'short_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brief description for listings'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Full product description with HTML formatting'}),
            'specifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Technical specifications with HTML formatting'}),
            'features': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Key features with HTML formatting'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Red, Blue, Black'}),
            'size': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., M, L, XL, 42, 50'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Weight in kg'}),
            'dimensions': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'L x W x H in cm'}),
            'material': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Cotton, Steel, Plastic'}),
            'warranty_months': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Warranty in months (e.g., 12)'}),
            'warranty_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detailed warranty information'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Original price'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Discount %'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Available stock'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Low stock alert level'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_new': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_best_seller': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = SubCategory.objects.filter(category_id=category_id, is_active=True)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.category:
            self.fields['subcategory'].queryset = self.instance.category.subcategories.filter(is_active=True)
        else:
            self.fields['subcategory'].queryset = SubCategory.objects.filter(is_active=True)
    
    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        
        return sku
    
    def clean_discount_percentage(self):
        discount = self.cleaned_data.get('discount_percentage')
        if discount and discount < 0:
            raise forms.ValidationError('Discount cannot be negative.')
        if discount and discount > 100:
            raise forms.ValidationError('Discount cannot exceed 100%.')
        return discount
    
    def clean_warranty_months(self):
        warranty = self.cleaned_data.get('warranty_months')
        if warranty and warranty < 0:
            raise forms.ValidationError('Warranty cannot be negative.')
        return warranty

# ========== PRODUCT VARIANT FORM ==========
class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            'name', 'sku', 'color', 'size', 'material', 'weight',
            'description', 'specifications', 'features',
            'warranty_months', 'warranty_details',
            'price', 'discount_percentage',
            'stock_quantity', 'low_stock_threshold',
            'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Variant name (e.g., Red - Medium)'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique variant SKU'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Red, Blue'}),
            'size': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., M, L, 42'}),
            'material': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Cotton, Steel'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Weight in kg'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Variant description with HTML formatting'}),
            'specifications': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Variant specifications with HTML formatting'}),
            'features': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Variant features with HTML formatting'}),
            'warranty_months': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Warranty in months'}),
            'warranty_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Detailed warranty information'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Original price'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Discount %'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Available stock'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Low stock alert level'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        
        return sku
    
    def clean_discount_percentage(self):
        discount = self.cleaned_data.get('discount_percentage')
        if discount and discount < 0:
            raise forms.ValidationError('Discount cannot be negative.')
        if discount and discount > 100:
            raise forms.ValidationError('Discount cannot exceed 100%.')
        return discount
    
    def clean_warranty_months(self):
        warranty = self.cleaned_data.get('warranty_months')
        if warranty and warranty < 0:
            raise forms.ValidationError('Warranty cannot be negative.')
        return warranty
    
# ========== PRODUCT REVIEW FORM ==========
class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['rating', 'title', 'review_text']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Review title'}),
            'review_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Write your review...'}),
        }

from django import forms

class CouponApplyForm(forms.Form):
    code = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter coupon code',
            'autocomplete': 'off'
        })
    )


class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter your shipping address'
        })
    )
    billing_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter your billing address (same as shipping if not specified)'
        }),
        required=False
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any special instructions?'
        }),
        required=False
    )

from django import forms
from .models import Coupon, Offer

# ============================================
# COUPON FORM
# ============================================

class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            'code', 'discount_type', 'discount_value', 'max_discount',
            'min_order_amount', 'usage_limit', 'valid_from', 'valid_to',
            'is_active', 'description', 'image'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., SAVE20',
                'style': 'text-transform:uppercase;'
            }),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 20'
            }),
            'max_discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 500'
            }),
            'min_order_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 1000'
            }),
            'usage_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 100'
            }),
            'valid_from': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'valid_to': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Coupon description...'
            }),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').upper().strip()
        if Coupon.objects.filter(code=code).exclude(id=self.instance.id).exists():
            raise forms.ValidationError('This coupon code already exists.')
        return code
    
    def clean_discount_value(self):
        value = self.cleaned_data.get('discount_value')
        if value and value <= 0:
            raise forms.ValidationError('Discount value must be greater than 0.')
        return value
    
    def clean_valid_from(self):
        valid_from = self.cleaned_data.get('valid_from')
        if valid_from:
            # Ensure timezone awareness
            from django.utils import timezone
            if timezone.is_naive(valid_from):
                valid_from = timezone.make_aware(valid_from)
        return valid_from
    
    def clean_valid_to(self):
        valid_to = self.cleaned_data.get('valid_to')
        if valid_to:
            from django.utils import timezone
            if timezone.is_naive(valid_to):
                valid_to = timezone.make_aware(valid_to)
        return valid_to
    
    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')
        
        if valid_from and valid_to and valid_from >= valid_to:
            raise forms.ValidationError('Valid To date must be after Valid From date.')
        
        return cleaned_data


# ============================================
# OFFER FORM
# ============================================

class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = [
            'name', 'offer_type', 'product', 'category',
            'discount_type', 'discount_value', 'max_discount',
            'min_order_amount', 'valid_from', 'valid_to',
            'is_active', 'description', 'banner_image', 'priority'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Summer Sale'
            }),
            'offer_type': forms.Select(attrs={
                'class': 'form-control',
                'id': 'offer_type'
            }),
            'product': forms.Select(attrs={
                'class': 'form-control',
                'id': 'product_select'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
                'id': 'category_select'
            }),
            'discount_type': forms.Select(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 20'
            }),
            'max_discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 500'
            }),
            'min_order_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'e.g., 1000'
            }),
            'valid_from': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'valid_to': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Offer description...'
            }),
            'banner_image': forms.FileInput(attrs={'class': 'form-control'}),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initially hide product and category fields
        self.fields['product'].required = False
        self.fields['category'].required = False
    
    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Name is required.')
        return name
    
    def clean_discount_value(self):
        value = self.cleaned_data.get('discount_value')
        if value and value <= 0:
            raise forms.ValidationError('Discount value must be greater than 0.')
        return value
    
    def clean(self):
        cleaned_data = super().clean()
        offer_type = cleaned_data.get('offer_type')
        product = cleaned_data.get('product')
        category = cleaned_data.get('category')
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')
        
        # Validate product/category based on offer type
        if offer_type == 'product' and not product:
            self.add_error('product', 'Please select a product for product offer.')
        elif offer_type == 'category' and not category:
            self.add_error('category', 'Please select a category for category offer.')
        
        # Validate dates
        if valid_from and valid_to and valid_from >= valid_to:
            raise forms.ValidationError('Valid To date must be after Valid From date.')
        
        return cleaned_data
    
# forms.py - Add this to your existing forms file

from django import forms
from .models import Banner

class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ['title', 'short_description', 'image', 'is_active']
        widgets = {
            'short_description': forms.Textarea(attrs={'rows': 3}),
        }