# offline_sales/models.py

from django.db import models
from django.utils import timezone
from django.conf import settings
import uuid
import random
import string

# ============================================
# STORE SETTINGS MODEL
# ============================================

class StoreSettings(models.Model):
    """Store configuration for offline sales"""
    
    store_name = models.CharField(max_length=200)
    store_logo = models.ImageField(upload_to='store/', blank=True, null=True)
    store_address = models.TextField()
    store_phone = models.CharField(max_length=15)
    store_email = models.EmailField()
    store_website = models.URLField(blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    invoice_prefix = models.CharField(max_length=10, default='INV-')
    invoice_start_number = models.IntegerField(default=1001)
    terms_conditions = models.TextField(blank=True)
    footer_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'store_settings'
        verbose_name = 'Store Setting'
        verbose_name_plural = 'Store Settings'
    
    def __str__(self):
        return self.store_name
    
    def get_next_invoice_number(self):
        """Generate next invoice number"""
        current = self.invoice_start_number
        self.invoice_start_number += 1
        self.save()
        return f"{self.invoice_prefix}{str(current).zfill(6)}"


# ============================================
# PRODUCT BARCODE MODEL
# ============================================

class ProductBarcode(models.Model):
    """Store barcode information for products and variants"""
    
    BARCODE_TYPES = [
        ('product', 'Product'),
        ('variant', 'Variant'),
    ]
    
    # Reference to Ecom models - FIXED: Using 'Ecom' app
    product = models.ForeignKey(
        'Ecom.Product', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='barcodes'
    )
    variant = models.ForeignKey(
        'Ecom.ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='barcodes'
    )
    barcode_type = models.CharField(max_length=10, choices=BARCODE_TYPES, default='product')
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True, null=True)
    barcode_text = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_barcodes'
        verbose_name = 'Product Barcode'
        verbose_name_plural = 'Product Barcodes'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.product:
            return f"{self.product.name} - {self.barcode_text}"
        elif self.variant:
            return f"{self.variant.product.name} - {self.variant.name} - {self.barcode_text}"
        return self.barcode_text


# 

class OfflineCustomer(models.Model):
    """Store offline customer details for walk-in sales"""
    
    # Basic Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    
    # Purchase Statistics
    total_purchases = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    last_purchase_at = models.DateTimeField(null=True, blank=True)
    
    # Additional
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'offline_customers'
        verbose_name = 'Offline Customer'
        verbose_name_plural = 'Offline Customers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.phone}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def customer_type(self):
        return 'Offline'

# ============================================
# OFFLINE ORDER MODEL
# ============================================

class OfflineOrder(models.Model):
    """Store offline sales orders"""
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('online', 'Online'),
        ('upi', 'UPI'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Order Identification
    order_number = models.CharField(max_length=20, unique=True)
    invoice_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    # Customer - FIXED: Using 'Ecom' app for User model
    customer = models.ForeignKey(
        'Ecom.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='offline_orders'
    )
    offline_customer = models.ForeignKey(
        'OfflineCustomer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='orders'
    )
    
    # Customer Details (cached)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=15)
    customer_address = models.TextField(blank=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    product_discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    offer_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Payment
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='cash')
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Order Status
    status = models.CharField(max_length=10, choices=ORDER_STATUS, default='pending')
    
    # Staff - FIXED: Using 'Ecom' app for User model
    created_by = models.ForeignKey(
        'Ecom.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='offline_sales'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'offline_orders'
        verbose_name = 'Offline Order'
        verbose_name_plural = 'Offline Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Offline Order #{self.order_number} - {self.customer_name}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = 'OFF' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)
    
    @property
    def total_discount(self):
        return self.product_discount_total + self.offer_discount + self.coupon_discount
    
    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


# ============================================
# OFFLINE ORDER ITEM MODEL
# ============================================

class OfflineOrderItem(models.Model):
    """Store offline order items"""
    
    order = models.ForeignKey('OfflineOrder', on_delete=models.CASCADE, related_name='items')
    
    # Product Information - FIXED: Using 'Ecom' app
    product = models.ForeignKey(
        'Ecom.Product', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    variant = models.ForeignKey(
        'Ecom.ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50)
    barcode_text = models.CharField(max_length=100, blank=True, null=True)
    
    # Quantity & Pricing
    quantity = models.PositiveIntegerField(default=1)
    original_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'offline_order_items'
        verbose_name = 'Offline Order Item'
        verbose_name_plural = 'Offline Order Items'
    
    def __str__(self):
        return f"{self.quantity} x {self.product_name} ({self.order.order_number})"