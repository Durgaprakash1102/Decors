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
        """Calculate final price after discount"""
        if self.discount_percentage > 0:
            discount_amount = (self.price * self.discount_percentage) / 100
            return self.price - discount_amount
        return self.price
    
    @property
    def discount_amount(self):
        """Calculate discount amount"""
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

# ========== PRODUCT VARIANT MODEL ==========
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
        # Store the threshold value
        self.low_stock_threshold = low_stock
        
        super().save(*args, **kwargs)
    
    @property
    def final_price(self):
        if self.discount_percentage > 0:
            discount_amount = (self.price * self.discount_percentage) / 100
            return self.price - discount_amount
        return self.price
    
    @property
    def discount_amount(self):
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