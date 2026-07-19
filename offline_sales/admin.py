# offline_sales/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import StoreSettings, ProductBarcode, OfflineCustomer, OfflineOrder, OfflineOrderItem


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['store_name', 'store_phone', 'store_email', 'invoice_prefix', 'invoice_start_number']
    fieldsets = (
        ('Store Information', {
            'fields': ('store_name', 'store_logo', 'store_address', 'store_phone', 'store_email', 'store_website')
        }),
        ('Tax Information', {
            'fields': ('gst_number', 'pan_number')
        }),
        ('Invoice Settings', {
            'fields': ('invoice_prefix', 'invoice_start_number')
        }),
        ('Additional Content', {
            'fields': ('terms_conditions', 'footer_text')
        }),
    )


@admin.register(ProductBarcode)
class ProductBarcodeAdmin(admin.ModelAdmin):
    list_display = ['barcode_text', 'product', 'variant', 'barcode_type', 'barcode_image_preview', 'created_at']
    list_filter = ['barcode_type']
    search_fields = ['barcode_text', 'product__name', 'variant__sku']
    readonly_fields = ['barcode_image_preview']
    
    def barcode_image_preview(self, obj):
        if obj.barcode_image:
            return format_html('<img src="{}" width="100" height="40"/>', obj.barcode_image.url)
        return '-'
    barcode_image_preview.short_description = 'Barcode Image'


admin.site.register(OfflineCustomer)

admin.site.register(OfflineOrder)


admin.site.register(OfflineOrderItem)
