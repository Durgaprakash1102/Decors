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

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Coupon, Offer, Order, OrderItem, 
    Cart, CartItem, Wishlist, WishlistItem, Transaction
)

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_display', 'image_preview', 'min_order_amount', 'usage_limit', 'used_count', 'is_active', 'valid_from', 'valid_to']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code', 'description']
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    
    def image_preview(self, obj):
        if obj.image and obj.image.url:
            return format_html('<img src="{}" width="50" height="50" style="object-fit:cover;border-radius:4px;" />', obj.image.url)
        return "-"
    image_preview.short_description = 'Image'
    
    def discount_display(self, obj):
        if obj.discount_type == 'percentage':
            return format_html('<span style="color:#dc3545;font-weight:bold;">{}% OFF</span>', obj.discount_value)
        return format_html('<span style="color:#28a745;font-weight:bold;">₹{} OFF</span>', obj.discount_value)
    discount_display.short_description = 'Discount'


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['name', 'offer_type', 'discount_value', 'is_active', 'valid_from', 'valid_to']
    list_filter = ['offer_type', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(Order)
admin.site.register(OrderItem)
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['order', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'status']
    search_fields = ['order__order_number', 'razorpay_transaction_id', 'razorpay_payment_id', 'razorpay_refund_id']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['order', 'transaction_type', 'razorpay_transaction_id', 'amount']
        return self.readonly_fields
    
admin.site.register(Product)
admin.site.register(ProductVariant)