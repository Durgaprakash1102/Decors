from decimal import Decimal

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from datetime import timedelta
import random

# ========== CUSTOM USER MANAGER ==========
class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, role='customer', **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, full_name, password, **extra_fields)

# ========== USER MODEL ==========
class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('customer', 'Customer'),
    ]
    
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    is_active = models.BooleanField(default=False)  # False until email verified
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_customer(self):
        return self.role == 'customer'

# ========== PROFILE MODEL ==========
class Profile(models.Model):
    GENDER_CHOICES = [
        ('', 'Select Gender'),
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'profiles'
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
    
    def __str__(self):
        return f"{self.user.full_name}'s Profile"
    
    def delete(self, *args, **kwargs):
        # Delete profile picture from storage when profile is deleted
        if self.profile_picture:
            import os
            from django.conf import settings
            if os.path.isfile(self.profile_picture.path):
                os.remove(self.profile_picture.path)
        super().delete(*args, **kwargs)

# ========== ADDRESS MODEL ==========
class Address(models.Model):
    ADDRESS_TYPES = [
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
        ('both', 'Both'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='shipping')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=50, default='India')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'addresses'
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.full_name} - {self.address_line1}, {self.city}"
    
    def save(self, *args, **kwargs):
        # If this address is set as default, unset all other default addresses for this user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

# ========== OTP MODEL ==========
# ========== OTP MODEL ==========
class OTP(models.Model):
    OTP_TYPES = [
        ('signup', 'Signup Verification'),
        ('login', 'Login 2FA'),
        ('forgot_password', 'Forgot Password'),
        ('change_password', 'Change Password'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps', null=True, blank=True)
    email = models.EmailField(null=True, blank=True)  # For pending users (signup)
    otp_code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPES)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'otps'
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.user:
            return f"{self.user.email} - {self.otp_code} ({self.otp_type})"
        return f"{self.email} - {self.otp_code} ({self.otp_type})"
    
    def is_valid(self):
        """Check if OTP is still valid (not used and not expired)"""
        return not self.is_used and timezone.now() <= self.expires_at
    
    def save(self, *args, **kwargs):
        # Auto-set expiry to 5 minutes from now if not provided
        if not self.pk and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

from django.db import models
from django.utils import timezone
from datetime import timedelta
import os
from django.conf import settings

# ========== CATEGORY MODEL ==========
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)

# ========== SUBCATEGORY MODEL ==========
class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='subcategories/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subcategories'
        verbose_name = 'SubCategory'
        verbose_name_plural = 'SubCategories'
        ordering = ['category', 'name']
        unique_together = ['category', 'name']
    
    def __str__(self):
        return f"{self.category.name} > {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(f"{self.category.name}-{self.name}")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)

# ========== PRODUCT MODEL ========== 
class Product(models.Model):
    # Basic Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    sku = models.CharField(max_length=50)
    brand = models.CharField(max_length=100, blank=True)
    
    # Category Relations
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    
    # Descriptions (HTML supported)
    short_description = models.TextField(max_length=500, help_text="Brief description shown in listings")
    description = models.TextField(help_text="Full product description (supports HTML formatting)")
    specifications = models.TextField(blank=True, help_text="Technical specifications (supports HTML formatting)")
    features = models.TextField(blank=True, help_text="Key features (supports HTML formatting)")
    
    # Product Attributes
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Weight in kg")
    dimensions = models.CharField(max_length=100, blank=True, help_text="L x W x H in cm")
    material = models.CharField(max_length=100, blank=True)
    
    # Warranty (in months)
    warranty_months = models.IntegerField(default=0, help_text="Warranty period in months")
    warranty_details = models.TextField(blank=True, help_text="Detailed warranty information")
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Original price")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount %")
    
    # Inventory
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    is_in_stock = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    is_best_seller = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        
        # Fix: Ensure stock_quantity is treated as integer
        if self.stock_quantity is None:
            self.stock_quantity = 0
        try:
            stock_qty = int(self.stock_quantity)
        except (ValueError, TypeError):
            stock_qty = 0
        self.is_in_stock = stock_qty > 0
        
        super().save(*args, **kwargs)
    
    @property
    def final_price(self):
        """Calculate final price after product discount"""
        if self.discount_percentage > 0:
            discount_amount = (self.price * self.discount_percentage) / 100
            return self.price - discount_amount
        return self.price
    
    @property
    def discount_amount(self):
        """Calculate product discount amount"""
        if self.discount_percentage > 0:
            return (self.price * self.discount_percentage) / 100
        return 0
    
    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold and self.stock_quantity > 0
    
    @property
    def is_out_of_stock(self):
        return self.stock_quantity <= 0
    
    @property
    def main_image(self):
        first_image = self.images.filter(is_primary=True).first()
        if not first_image:
            first_image = self.images.first()
        if first_image:
            return first_image.image.url
        return None
    
    @property
    def total_reviews(self):
        return self.reviews.filter(is_approved=True).count()
    
    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            total = sum(r.rating for r in reviews)
            return round(total / reviews.count(), 1)
        return 0
    
    @property
    def rating_distribution(self):
        """Get rating distribution {1: count, 2: count, ...}"""
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        reviews = self.reviews.filter(is_approved=True)
        for review in reviews:
            distribution[review.rating] += 1
        return distribution
    
    # ============================================
    # OFFER RELATED PROPERTIES
    # ============================================
    
    @property
    def _get_offer_data(self):
        """
        Internal method to get offer data for this product.
        Returns: (offer_price, offer_name, offer_discount)
        """
        from decimal import Decimal
        from django.utils import timezone
        from .models import Offer
        
        # Get all active offers
        offers = Offer.objects.filter(
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now()
        ).order_by('-priority')
        
        original_price = Decimal(str(self.price))
        product_discounted_price = self.final_price
        product_discount_amount = original_price - product_discounted_price
        
        best_offer_discount = Decimal('0')
        best_offer_name = None
        
        # Find best offer
        for offer in offers:
            discount_value = Decimal(str(offer.discount_value))
            
            if offer.offer_type == 'product':
                if offer.product and offer.product.id == self.id:
                    if offer.discount_type == 'percentage':
                        discount = (original_price * discount_value) / Decimal('100')
                        if offer.max_discount:
                            max_disc = Decimal(str(offer.max_discount))
                            if discount > max_disc:
                                discount = max_disc
                    else:
                        discount = discount_value
                    
                    if discount > best_offer_discount:
                        best_offer_discount = discount
                        best_offer_name = offer.name
                        
            elif offer.offer_type == 'category':
                if self.category and offer.category and offer.category.id == self.category.id:
                    if offer.discount_type == 'percentage':
                        discount = (original_price * discount_value) / Decimal('100')
                        if offer.max_discount:
                            max_disc = Decimal(str(offer.max_discount))
                            if discount > max_disc:
                                discount = max_disc
                    else:
                        discount = discount_value
                    
                    if discount > best_offer_discount:
                        best_offer_discount = discount
                        best_offer_name = offer.name
        
        # Determine final price with best discount
        has_product_discount = product_discount_amount > 0
        has_offer = best_offer_discount > 0
        
        if has_product_discount and has_offer:
            # Both exist - apply the better one
            product_final_price = original_price - product_discount_amount
            offer_final_price = original_price - best_offer_discount
            
            if offer_final_price < product_final_price:
                # Offer gives better discount
                return offer_final_price, best_offer_name, best_offer_discount
            else:
                # Product discount gives better discount
                return product_final_price, "Product Discount", Decimal('0')
        elif has_offer:
            # Only offer exists
            return original_price - best_offer_discount, best_offer_name, best_offer_discount
        elif has_product_discount:
            # Only product discount exists
            return product_discounted_price, "Product Discount", Decimal('0')
        else:
            # No discount
            return original_price, None, Decimal('0')
    
    @property
    def offer_price(self):
        """Get final price after best discount (product discount OR offer)"""
        price, name, discount = self._get_offer_data
        return price
    
    @property
    def offer_name(self):
        """Get the name of the applied offer (or 'Product Discount')"""
        price, name, discount = self._get_offer_data
        return name
    
    @property
    def offer_discount_amount(self):
        """Get the discount amount from the applied offer"""
        price, name, discount = self._get_offer_data
        return discount
    
    @property
    def has_offer_applied(self):
        """Check if an offer is applied to this product"""
        price, name, discount = self._get_offer_data
        return name is not None and name != "Product Discount"
    
    @property
    def has_product_discount(self):
        """Check if product discount is applied"""
        return self.discount_percentage > 0
    
    @property
    def best_discount_type(self):
        """Get the type of best discount applied: 'offer', 'product', or None"""
        price, name, discount = self._get_offer_data
        if name and name != "Product Discount":
            return 'offer'
        elif name == "Product Discount":
            return 'product'
        return None
    
    @property
    def total_savings(self):
        """Get total savings from the best discount"""
        price, name, discount = self._get_offer_data
        if name:
            return Decimal(str(self.price)) - price
        return Decimal('0')
    
    def get_similar_products(self, limit=5):
        """Get similar products based on category and subcategory"""
        similar = Product.objects.filter(
            is_active=True,
            category=self.category
        ).exclude(id=self.id)
        
        # Prioritize same subcategory
        if self.subcategory:
            same_subcat = similar.filter(subcategory=self.subcategory)
            if same_subcat.count() >= limit:
                return same_subcat[:limit]
        
        return similar[:limit]
    
# ========== PRODUCT IMAGE MODEL ==========
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_images'
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['display_order', '-is_primary']
    
    def __str__(self):
        return f"Image for {self.product.name}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    # Variant Information
    name = models.CharField(max_length=200, blank=True, help_text="e.g., Red - Medium, Blue - Large")
    sku = models.CharField(max_length=50)
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    material = models.CharField(max_length=100, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Descriptions (HTML supported)
    description = models.TextField(blank=True, help_text="Variant description (supports HTML formatting)")
    specifications = models.TextField(blank=True, help_text="Variant specifications (supports HTML formatting)")
    features = models.TextField(blank=True, help_text="Variant features (supports HTML formatting)")
    
    # Warranty (in months)
    warranty_months = models.IntegerField(default=0, help_text="Warranty period in months")
    warranty_details = models.TextField(blank=True, help_text="Detailed warranty information")
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Original price")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Discount %")
    
    # Inventory
    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    is_in_stock = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_variants'
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        ordering = ['color', 'size']
        unique_together = ['product', 'sku']
    
    def __str__(self):
        if self.name:
            return f"{self.product.name} - {self.name}"
        variant_info = []
        if self.color:
            variant_info.append(self.color)
        if self.size:
            variant_info.append(self.size)
        return f"{self.product.name} - {' / '.join(variant_info) if variant_info else self.sku}"
    
    def save(self, *args, **kwargs):
        # Fix: Ensure stock_quantity is treated as integer
        if self.stock_quantity is None:
            self.stock_quantity = 0
        try:
            stock_qty = int(self.stock_quantity)
        except (ValueError, TypeError):
            stock_qty = 0
        self.is_in_stock = stock_qty > 0
        
        # Fix: Ensure low_stock_threshold is treated as integer
        if self.low_stock_threshold is None:
            self.low_stock_threshold = 5
        try:
            low_stock = int(self.low_stock_threshold)
        except (ValueError, TypeError):
            low_stock = 5
        self.low_stock_threshold = low_stock
        
        super().save(*args, **kwargs)
    
    @property
    def final_price(self):
        """Calculate final price after product discount"""
        if self.discount_percentage > 0:
            discount_amount = (self.price * self.discount_percentage) / 100
            return self.price - discount_amount
        return self.price
    
    @property
    def discount_amount(self):
        """Calculate product discount amount"""
        if self.discount_percentage > 0:
            return (self.price * self.discount_percentage) / 100
        return 0
    
    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold and self.stock_quantity > 0
    
    @property
    def is_out_of_stock(self):
        return self.stock_quantity <= 0
    
    @property
    def main_image(self):
        first_image = self.images.filter(is_primary=True).first()
        if not first_image:
            first_image = self.images.first()
        if first_image:
            return first_image.image.url
        return None
    
    # ============================================
    # OFFER RELATED PROPERTIES (CALCULATED ON VARIANT'S OWN PRICE)
    # ============================================
    
    @property
    def _get_offer_data(self):
        """
        Internal method to get offer data for this variant.
        Calculates offer discount on the variant's OWN price.
        Returns: (offer_price, offer_name, offer_discount)
        """
        from decimal import Decimal
        from django.utils import timezone
        from .models import Offer
        
        # Get all active offers
        offers = Offer.objects.filter(
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now()
        ).order_by('-priority')
        
        # Use variant's own price
        original_price = Decimal(str(self.price))
        variant_discounted_price = self.final_price
        variant_discount_amount = original_price - variant_discounted_price
        
        best_offer_discount = Decimal('0')
        best_offer_name = None
        
        # Find best offer for this variant's product
        for offer in offers:
            discount_value = Decimal(str(offer.discount_value))
            
            if offer.offer_type == 'product':
                if offer.product and offer.product.id == self.product.id:
                    # Calculate discount on variant's price
                    if offer.discount_type == 'percentage':
                        discount = (original_price * discount_value) / Decimal('100')
                        if offer.max_discount:
                            max_disc = Decimal(str(offer.max_discount))
                            if discount > max_disc:
                                discount = max_disc
                    else:
                        discount = discount_value
                    
                    if discount > best_offer_discount:
                        best_offer_discount = discount
                        best_offer_name = offer.name
                        
            elif offer.offer_type == 'category':
                if self.product.category and offer.category and offer.category.id == self.product.category.id:
                    # Calculate discount on variant's price
                    if offer.discount_type == 'percentage':
                        discount = (original_price * discount_value) / Decimal('100')
                        if offer.max_discount:
                            max_disc = Decimal(str(offer.max_discount))
                            if discount > max_disc:
                                discount = max_disc
                    else:
                        discount = discount_value
                    
                    if discount > best_offer_discount:
                        best_offer_discount = discount
                        best_offer_name = offer.name
        
        # Determine final price with best discount
        has_product_discount = variant_discount_amount > 0
        has_offer = best_offer_discount > 0
        
        if has_product_discount and has_offer:
            # Both exist - apply the better one
            product_final_price = original_price - variant_discount_amount
            offer_final_price = original_price - best_offer_discount
            
            if offer_final_price < product_final_price:
                # Offer gives better discount
                return offer_final_price, best_offer_name, best_offer_discount
            else:
                # Product discount gives better discount
                return product_final_price, "Product Discount", Decimal('0')
        elif has_offer:
            # Only offer exists
            return original_price - best_offer_discount, best_offer_name, best_offer_discount
        elif has_product_discount:
            # Only product discount exists
            return variant_discounted_price, "Product Discount", Decimal('0')
        else:
            # No discount
            return original_price, None, Decimal('0')
    
    @property
    def offer_price(self):
        """Get final price after best discount (calculated on variant's own price)"""
        price, name, discount = self._get_offer_data
        return price
    
    @property
    def offer_name(self):
        """Get the name of the applied offer (or 'Product Discount')"""
        price, name, discount = self._get_offer_data
        return name
    
    @property
    def offer_discount_amount(self):
        """Get the discount amount from the applied offer"""
        price, name, discount = self._get_offer_data
        return discount
    
    @property
    def has_offer_applied(self):
        """Check if an offer is applied to this variant"""
        price, name, discount = self._get_offer_data
        return name is not None and name != "Product Discount"
    
    @property
    def has_product_discount(self):
        """Check if product discount is applied to this variant"""
        return self.discount_percentage > 0
    
    @property
    def best_discount_type(self):
        """Get the type of best discount applied: 'offer', 'product', or None"""
        price, name, discount = self._get_offer_data
        if name and name != "Product Discount":
            return 'offer'
        elif name == "Product Discount":
            return 'product'
        return None
    
    @property
    def total_savings(self):
        """Get total savings from the best discount"""
        price, name, discount = self._get_offer_data
        if name:
            return Decimal(str(self.price)) - price
        return Decimal('0')
    
# ========== VARIANT IMAGE MODEL ==========
class VariantImage(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='variant_images/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'variant_images'
        verbose_name = 'Variant Image'
        verbose_name_plural = 'Variant Images'
        ordering = ['display_order', '-is_primary']
    
    def __str__(self):
        return f"Image for {self.variant.sku}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            VariantImage.objects.filter(variant=self.variant, is_primary=True).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        if self.image:
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)

# ========== PRODUCT REVIEW MODEL ==========
class ProductReview(models.Model):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    review_text = models.TextField()
    
    # Status
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_reviews'
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'
        ordering = ['-created_at']
        unique_together = ['product', 'user']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.product.name} ({self.rating}★)"
    
    @property
    def rating_stars(self):
        return '★' * self.rating + '☆' * (5 - self.rating)

# ========== INVENTORY LOG MODEL ==========
class InventoryLog(models.Model):
    ACTION_CHOICES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('adjustment', 'Adjustment'),
        ('restock', 'Restock'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_logs', null=True, blank=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='inventory_logs', null=True, blank=True)
    quantity_change = models.IntegerField()
    previous_quantity = models.IntegerField(default=0)
    new_quantity = models.IntegerField(default=0)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey('User', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_logs'
        verbose_name = 'Inventory Log'
        verbose_name_plural = 'Inventory Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        target = str(self.product) if self.product else str(self.variant)
        return f"{self.action} - {target} ({self.quantity_change})"

# ========== RECENTLY VIEWED PRODUCT MODEL ==========
class RecentlyViewed(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='recently_viewed')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'recently_viewed'
        verbose_name = 'Recently Viewed'
        verbose_name_plural = 'Recently Viewed'
        ordering = ['-viewed_at']
        unique_together = ['user', 'product']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name}"
    
    @classmethod
    def add_view(cls, user, product):
        """Add a product to recently viewed"""
        # Remove existing entry if any
        cls.objects.filter(user=user, product=product).delete()
        # Create new entry
        cls.objects.create(user=user, product=product)
        # Keep only last 20 items
        to_delete = cls.objects.filter(user=user).order_by('-viewed_at')[20:]
        for item in to_delete:
            item.delete()
    
    @classmethod
    def get_recently_viewed(cls, user, limit=10):
        """Get recently viewed products for a user"""
        return cls.objects.filter(user=user).select_related('product')[:limit]
    
# ============================================
# CART MODELS
# ============================================

class Cart(models.Model):
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='cart', null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts'
    
    def __str__(self):
        if self.user:
            return f"Cart - {self.user.email}"
        return f"Cart - {self.session_id}"
    
    @property
    def subtotal(self):
        total = sum(item.total_price for item in self.items.all())
        return total
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_price(self):
        return self.subtotal - self.discount_amount
    
    def apply_coupon(self, coupon_code):
        try:
            coupon = Coupon.objects.get(
                code__iexact=coupon_code,
                is_active=True,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now()
            )
            if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
                return False, "Coupon usage limit exceeded"
            if self.subtotal < coupon.min_order_amount:
                return False, f"Minimum order amount of ₹{coupon.min_order_amount} required"
            
            if coupon.discount_type == 'percentage':
                discount = (self.subtotal * coupon.discount_value) / 100
                if coupon.max_discount and discount > coupon.max_discount:
                    discount = coupon.max_discount
            else:
                discount = coupon.discount_value
            
            self.coupon = coupon
            self.discount_amount = discount
            self.save()
            return True, f"Coupon applied! You saved ₹{discount:.2f}"
        except Coupon.DoesNotExist:
            return False, "Invalid coupon code"
    
    def remove_coupon(self):
        self.coupon = None
        self.discount_amount = 0
        self.save()
        return True, "Coupon removed"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, null=True, blank=True)
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ['cart', 'product', 'variant']
    
    def __str__(self):
        if self.variant:
            return f"{self.quantity} x {self.variant.product.name} - {self.variant.name or self.variant.sku}"
        if self.product:
            return f"{self.quantity} x {self.product.name}"
        return f"{self.quantity} x Unknown Item"
    
    # ============================================
    # BASIC PROPERTIES
    # ============================================
    
    @property
    def item_name(self):
        """Get the display name of the item"""
        if self.variant:
            # Show variant name with product name
            if self.variant.name:
                return f"{self.variant.product.name} - {self.variant.name}"
            else:
                # Build name from variant attributes
                variant_info = []
                if self.variant.color:
                    variant_info.append(self.variant.color)
                if self.variant.size:
                    variant_info.append(self.variant.size)
                if variant_info:
                    return f"{self.variant.product.name} ({' / '.join(variant_info)})"
                return self.variant.product.name
        if self.product:
            return self.product.name
        return "Unknown Item"
    
    @property
    def item_sku(self):
        """Get the SKU of the item"""
        if self.variant:
            return self.variant.sku
        if self.product:
            return self.product.sku
        return ""
    
    @property
    def item_id(self):
        """Get the ID of the item (product or variant)"""
        if self.variant:
            return self.variant.id
        if self.product:
            return self.product.id
        return None
    
    @property
    def item_type(self):
        """Get the type of item: 'variant' or 'product'"""
        if self.variant:
            return 'variant'
        return 'product'
    
    # ============================================
    # PRICING PROPERTIES
    # ============================================
    
    @property
    def original_price(self):
        """Get the original price (before any discounts)"""
        if self.variant:
            return self.variant.price
        if self.product:
            return self.product.price
        return Decimal('0')
    
    @property
    def product_discounted_price(self):
        """Get the price after product-level discount (before offers)"""
        if self.variant:
            return self.variant.final_price
        if self.product:
            return self.product.final_price
        return Decimal('0')
    
    @property
    def price(self):
        """
        Get the current price after product discount (for cart display)
        This is the price before offer discount
        """
        return self.product_discounted_price
    
    @property
    def has_product_discount(self):
        """Check if the item has a product-level discount"""
        return self.original_price > self.product_discounted_price
    
    @property
    def product_discount_amount(self):
        """Get the product discount amount"""
        return self.original_price - self.product_discounted_price
    
    # ============================================
    # OFFER PROPERTIES (Calculated on Item's Price)
    # ============================================
    
    @property
    def _get_item_for_offer(self):
        """
        Get the appropriate item (product or variant) for offer calculation
        Returns: (item, original_price)
        """
        if self.variant:
            return self.variant, self.variant.price
        return self.product, self.product.price
    
    @property
    def offer_data(self):
        """
        Calculate offer data for this cart item.
        Returns: (offer_price, offer_name, offer_discount)
        """
        from decimal import Decimal
        from django.utils import timezone
        from .models import Offer
        
        if not self.product:
            return None, None, Decimal('0')
        
        # Get the item and its original price
        item, original_price = self._get_item_for_offer
        
        # Get all active offers
        offers = Offer.objects.filter(
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now()
        ).order_by('-priority')
        
        # Get product discounted price
        product_discounted_price = self.product_discounted_price
        product_discount_amount = original_price - product_discounted_price
        
        best_offer_discount = Decimal('0')
        best_offer_name = None
        
        # Find best offer for this item
        for offer in offers:
            discount_value = Decimal(str(offer.discount_value))
            
            if offer.offer_type == 'product':
                # Check if offer is on the product
                if offer.product and offer.product.id == self.product.id:
                    if offer.discount_type == 'percentage':
                        discount = (original_price * discount_value) / Decimal('100')
                        if offer.max_discount:
                            max_disc = Decimal(str(offer.max_discount))
                            if discount > max_disc:
                                discount = max_disc
                    else:
                        discount = discount_value
                    
                    if discount > best_offer_discount:
                        best_offer_discount = discount
                        best_offer_name = offer.name
                        
            elif offer.offer_type == 'category':
                # Check if offer is on the category
                if self.product.category and offer.category and offer.category.id == self.product.category.id:
                    if offer.discount_type == 'percentage':
                        discount = (original_price * discount_value) / Decimal('100')
                        if offer.max_discount:
                            max_disc = Decimal(str(offer.max_discount))
                            if discount > max_disc:
                                discount = max_disc
                    else:
                        discount = discount_value
                    
                    if discount > best_offer_discount:
                        best_offer_discount = discount
                        best_offer_name = offer.name
        
        # Determine final price with best discount
        has_product_discount = product_discount_amount > 0
        has_offer = best_offer_discount > 0
        
        if has_product_discount and has_offer:
            # Both exist - apply the better one
            product_final_price = original_price - product_discount_amount
            offer_final_price = original_price - best_offer_discount
            
            if offer_final_price < product_final_price:
                # Offer gives better discount
                return offer_final_price, best_offer_name, best_offer_discount
            else:
                # Product discount gives better discount
                return product_final_price, "Product Discount", Decimal('0')
        elif has_offer:
            # Only offer exists
            return original_price - best_offer_discount, best_offer_name, best_offer_discount
        elif has_product_discount:
            # Only product discount exists
            return product_discounted_price, "Product Discount", Decimal('0')
        else:
            # No discount
            return original_price, None, Decimal('0')
    
    @property
    def offer_price(self):
        """Get final price after best discount (product discount OR offer)"""
        price, name, discount = self.offer_data
        return price
    
    @property
    def offer_name(self):
        """Get the name of the applied offer (or 'Product Discount')"""
        price, name, discount = self.offer_data
        return name
    
    @property
    def offer_discount(self):
        """Get the discount amount from the applied offer"""
        price, name, discount = self.offer_data
        return discount
    
    @property
    def has_offer_applied(self):
        """Check if an offer is applied to this item"""
        price, name, discount = self.offer_data
        return name is not None and name != "Product Discount"
    
    @property
    def best_discount_type(self):
        """Get the type of best discount applied: 'offer', 'product', or None"""
        price, name, discount = self.offer_data
        if name and name != "Product Discount":
            return 'offer'
        elif name == "Product Discount":
            return 'product'
        return None
    
    @property
    def total_savings(self):
        """Get total savings from the best discount"""
        price, name, discount = self.offer_data
        if name:
            return self.original_price - price
        return Decimal('0')
    
    # ============================================
    # TOTAL CALCULATIONS
    # ============================================
    
    @property
    def total_price(self):
        """Total price after product discount (without offer)"""
        return self.product_discounted_price * self.quantity
    
    @property
    def total_offer_price(self):
        """Total price after offer discount"""
        return self.offer_price * self.quantity
    
    @property
    def total_original_price(self):
        """Total original price"""
        return self.original_price * self.quantity
    
    @property
    def total_product_discount(self):
        """Total product discount amount"""
        return self.product_discount_amount * self.quantity
    
    @property
    def total_offer_discount(self):
        """Total offer discount amount"""
        return self.offer_discount * self.quantity
    
    @property
    def total_savings_amount(self):
        """Total savings from best discount"""
        return self.total_savings * self.quantity
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.original_price > 0:
            return ((self.original_price - self.offer_price) / self.original_price) * 100
        return 0
    
    # ============================================
    # STOCK PROPERTIES
    # ============================================
    
    @property
    def stock_available(self):
        """Get available stock for this item"""
        if self.variant:
            return self.variant.stock_quantity
        if self.product:
            return self.product.stock_quantity
        return 0
    
    @property
    def is_in_stock(self):
        """Check if item is in stock"""
        return self.stock_available > 0
    
    @property
    def is_low_stock(self):
        """Check if item is low on stock"""
        if self.variant:
            return self.variant.is_low_stock
        if self.product:
            return self.product.is_low_stock
        return False
    
    @property
    def is_out_of_stock(self):
        """Check if item is out of stock"""
        return self.stock_available <= 0
    
    # ============================================
    # IMAGE PROPERTIES
    # ============================================
    
    @property
    def main_image(self):
        """Get the main image for this item"""
        if self.variant:
            return self.variant.main_image or self.variant.product.main_image
        if self.product:
            return self.product.main_image
        return None
    
    # ============================================
    # VARIANT INFO
    # ============================================
    
    @property
    def variant_color(self):
        """Get variant color if exists"""
        if self.variant:
            return self.variant.color
        return None
    
    @property
    def variant_size(self):
        """Get variant size if exists"""
        if self.variant:
            return self.variant.size
        return None
    
    @property
    def variant_name_display(self):
        """Get variant display name"""
        if self.variant:
            if self.variant.name:
                return self.variant.name
            variant_info = []
            if self.variant.color:
                variant_info.append(self.variant.color)
            if self.variant.size:
                variant_info.append(self.variant.size)
            if variant_info:
                return ' / '.join(variant_info)
            return self.variant.sku
        return None
    
    @property
    def has_variant(self):
        """Check if this cart item has a variant"""
        return self.variant is not None
    
    @property
    def is_product_only(self):
        """Check if this cart item is product only (no variant)"""
        return self.product is not None and self.variant is None
    
    # ============================================
    # FORMATTED DISPLAY
    # ============================================
    
    def get_price_display(self):
        """Get formatted price display with discount info"""
        if self.has_offer_applied:
            return {
                'current': f"₹{self.offer_price:.2f}",
                'original': f"₹{self.original_price:.2f}",
                'savings': f"₹{self.total_savings:.2f}",
                'tag': self.offer_name,
                'type': 'offer'
            }
        elif self.has_product_discount:
            return {
                'current': f"₹{self.product_discounted_price:.2f}",
                'original': f"₹{self.original_price:.2f}",
                'savings': f"₹{self.product_discount_amount:.2f}",
                'tag': f"{self.discount_percentage:.0f}% OFF",
                'type': 'product'
            }
        else:
            return {
                'current': f"₹{self.original_price:.2f}",
                'original': None,
                'savings': None,
                'tag': None,
                'type': 'none'
            }
    
    def get_stock_status(self):
        """Get stock status with badge class"""
        if self.is_out_of_stock:
            return {'status': 'out-of-stock', 'text': 'Out of Stock', 'icon': 'times-circle'}
        elif self.is_low_stock:
            return {'status': 'low-stock', 'text': f'Only {self.stock_available} left', 'icon': 'exclamation-triangle'}
        else:
            return {'status': 'in-stock', 'text': 'In Stock', 'icon': 'check-circle'}

# ============================================
# WISHLIST MODELS
# ============================================

class Wishlist(models.Model):
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='wishlist')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wishlists'
    
    @property
    def total_items(self):
        return self.items.count()


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wishlist_items'
        unique_together = ['wishlist', 'product', 'variant']
    
    @property
    def price(self):
        if self.variant:
            return self.variant.final_price
        return self.product.final_price
    
    @property
    def main_image(self):
        if self.variant:
            return self.variant.main_image or self.variant.product.main_image
        return self.product.main_image


# ============================================
# COUPON MODELS
# ============================================

class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='coupons/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'coupons'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} ({self.discount_value}{'%' if self.discount_type == 'percentage' else '₹'})"
    
    @property
    def discount_display(self):
        if self.discount_type == 'percentage':
            return f"{self.discount_value}% OFF"
        return f"₹{self.discount_value} OFF"
    
    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if timezone.now() < self.valid_from:
            return False
        if timezone.now() > self.valid_to:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True
    
    def calculate_discount(self, subtotal):
        if self.discount_type == 'percentage':
            discount = (subtotal * self.discount_value) / 100
            if self.max_discount and discount > self.max_discount:
                discount = self.max_discount
        else:
            discount = self.discount_value
        return min(discount, subtotal)
    
    def delete(self, *args, **kwargs):
        if self.image:
            import os
            from django.conf import settings
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)


# ============================================
# OFFER MODELS
# ============================================

class Offer(models.Model):
    OFFER_TYPES = [
        ('product', 'Product Offer'),
        ('category', 'Category Offer'),
        ('cart', 'Cart Offer'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES, default='product')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, null=True, blank=True)
    discount_type = models.CharField(max_length=10, choices=Coupon.DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    banner_image = models.ImageField(upload_to='offers/', null=True, blank=True)
    description = models.TextField(blank=True)
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'offers'
        ordering = ['-priority', '-created_at']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        if not self.is_active:
            return False
        if timezone.now() < self.valid_from:
            return False
        if timezone.now() > self.valid_to:
            return False
        return True


# ============================================
# ORDER MODELS
# ============================================

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # User & Order Identification
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True)
    
    # Payment Gateway Details
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    
    # Pricing Breakdown
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total before any discounts")
    product_discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total discount from product-level discounts")
    offer_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total discount from offers")
    coupon_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Total discount from coupons")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Final amount paid by customer")
    
    # Applied Discounts
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    offer = models.ForeignKey('Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Addresses
    shipping_address = models.TextField()
    billing_address = models.TextField()
    
    # Additional
    notes = models.TextField(blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    tracking_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to track the shipment")
    delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.order_number} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            import random
            import string
            self.order_number = 'ORD' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)
    
    @property
    def total_discount(self):
        """Total discount from all sources"""
        return self.product_discount_total + self.offer_discount + self.coupon_discount
    
    @property
    def total_savings(self):
        """Alias for total_discount"""
        return self.total_discount
    
    @property
    def item_count(self):
        """Total number of items in the order"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def is_paid(self):
        """Check if order is paid"""
        return self.payment_status == 'paid'
    
    @property
    def is_delivered(self):
        """Check if order is delivered"""
        return self.status == 'delivered'
    
    @property
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'processing'] and self.payment_status != 'refunded'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    # Product Information
    product = models.ForeignKey('Product', on_delete=models.CASCADE, null=True, blank=True)
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50)
    
    # Quantity & Pricing
    quantity = models.PositiveIntegerField(default=1)
    
    # Price Breakdown
    original_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Original price before any discount")
    product_discounted_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Price after product-level discount")
    offer_discounted_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Price after offer discount")
    final_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Final price after all discounts")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Final price × quantity")
    
    # Discount Breakdown
    product_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Discount from product level")
    offer_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Discount from offers")
    
    # Applied Offers
    offer = models.ForeignKey('Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    offer_name = models.CharField(max_length=200, blank=True, help_text="Name of offer applied (cached)")
    
    # Status
    is_returned = models.BooleanField(default=False)
    return_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.quantity} x {self.product_name} ({self.order.order_number})"
    
    @property
    def total_discount(self):
        """Total discount for this item"""
        return self.product_discount + self.offer_discount
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.original_price > 0:
            return ((self.original_price - self.final_price) / self.original_price) * 100
        return 0
    
    @property
    def has_offer(self):
        """Check if offer was applied"""
        return self.offer_discount > 0
    
    @property
    def has_product_discount(self):
        """Check if product discount was applied"""
        return self.product_discount > 0
    
# ============================================
# TRANSACTION MODEL - Track all payments & refunds
# ============================================

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
    ]
    
    TRANSACTION_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='payment')
    razorpay_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_refund_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    response_data = models.JSONField(default=dict, blank=True)  # Store full response from Razorpay
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'transactions'
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.order.order_number} - ₹{self.amount}"
    
    @property
    def is_payment(self):
        return self.transaction_type == 'payment'
    
    @property
    def is_refund(self):
        return self.transaction_type == 'refund'

class Banner(models.Model):
    title = models.CharField(max_length=200)
    short_description = models.TextField(max_length=500, blank=True, help_text="Brief description shown on banner")
    image = models.ImageField(upload_to='banners/', help_text="Recommended size: 1920x600")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'banners'
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def delete(self, *args, **kwargs):
        if self.image:
            import os
            from django.conf import settings
            if os.path.isfile(self.image.path):
                os.remove(self.image.path)
        super().delete(*args, **kwargs)