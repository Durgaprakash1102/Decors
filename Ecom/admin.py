from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'full_name', 'role', 'is_active', 'is_verified', 'date_joined']
    list_filter = ['role', 'is_active', 'is_verified']
    search_fields = ['email', 'full_name', 'phone']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_verified', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'role'),
        }),
    )

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'date_of_birth']
    search_fields = ['user__email', 'user__full_name']
    list_filter = ['gender']

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'city', 'state', 'address_type', 'is_default']
    list_filter = ['address_type', 'is_default']
    search_fields = ['user__email', 'full_name', 'city', 'state']

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['user', 'otp_code', 'otp_type', 'is_used', 'created_at', 'expires_at']
    list_filter = ['otp_type', 'is_used']
    search_fields = ['user__email', 'otp_code']
    
    def has_add_permission(self, request):
        return False  # Prevent manual OTP creation from admin

# Register User with custom admin
admin.site.register(User, CustomUserAdmin)
admin.site.register(ProductReview)