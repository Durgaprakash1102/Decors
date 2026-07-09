from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import User, Profile, Address, OTP
from .forms import (
    CustomerSignupForm, AdminSignupForm, LoginForm, OTPVerificationForm,
    ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm,
    ProfileUpdateForm, UserUpdateForm, AddressForm
)
from .utils import create_and_send_otp, verify_otp, delete_file_if_exists, get_user_by_identifier

# ==================== HOME ====================
def home(request):
    return render(request, "home.html")

def about(request):
    return render(request, "about.html")


# ==================== CUSTOMER SIGNUP ====================
def customer_signup_view(request):
    if request.user.is_authenticated:
        return redirect('Ecom:home')
    
    if request.method == 'POST':
        form = CustomerSignupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            
            # Store user data in session
            request.session['pending_user_data'] = {
                'email': email,
                'full_name': full_name,
                'phone': phone,
                'password': password,
                'role': 'customer'
            }
            
            # Send OTP
            create_and_send_otp(email, 'signup', full_name)
            request.session['pending_email'] = email
            request.session['otp_type'] = 'signup'
            
            messages.success(request, 'OTP sent to your email. Please verify to create your account.')
            return redirect('Ecom:verify_otp')
    else:
        form = CustomerSignupForm()
    
    return render(request, 'Ecom/auth/customer_signup.html', {'form': form})

# ==================== ADMIN SIGNUP ====================
def admin_signup_view(request):
    if request.user.is_authenticated:
        return redirect('Ecom:home')
    
    if request.method == 'POST':
        form = AdminSignupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']
            
            # Store user data in session
            request.session['pending_user_data'] = {
                'email': email,
                'full_name': full_name,
                'phone': phone,
                'password': password,
                'role': 'admin',
                'is_staff': True
            }
            
            # Send OTP
            create_and_send_otp(email, 'signup', full_name)
            request.session['pending_email'] = email
            request.session['otp_type'] = 'signup'
            
            messages.success(request, 'OTP sent to your email. Please verify to create your admin account.')
            return redirect('Ecom:verify_otp')
    else:
        form = AdminSignupForm()
    
    return render(request, 'Ecom/auth/admin_signup.html', {'form': form})

def verify_otp_view(request):
    email = request.session.get('pending_email')
    user_data = request.session.get('pending_user_data')
    
    if not email or not user_data:
        messages.error(request, 'Session expired. Please sign up again.')
        return redirect('Ecom:customer_signup')
    
    otp_type = request.session.get('otp_type', 'signup')
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            is_valid, message, otp = verify_otp(email, otp_code, otp_type)
            
            if is_valid:
                # Create the actual user in database
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=user_data['email'],
                        full_name=user_data['full_name'],
                        password=user_data['password'],
                        role=user_data.get('role', 'customer'),
                        is_active=True,
                        is_verified=True
                    )
                    
                    # Set phone if provided
                    if user_data.get('phone'):
                        user.phone = user_data['phone']
                    
                    # If admin, set is_staff
                    if user_data.get('role') == 'admin':
                        user.is_staff = True
                    
                    user.save()
                    
                    # Create profile
                    Profile.objects.create(user=user)
                
                # Login the user
                login(request, user)
                
                # Clean session
                request.session.pop('pending_user_data', None)
                request.session.pop('pending_email', None)
                request.session.pop('otp_type', None)
                
                messages.success(request, f'Account created successfully! Welcome to MyStore, {user.full_name}!')
                
                if user.is_admin:
                    return redirect('Ecom:admin_dashboard')
                else:
                    return redirect('Ecom:home')
            else:
                messages.error(request, message)
    else:
        form = OTPVerificationForm()
    
    return render(request, 'Ecom/auth/verify_otp.html', {
        'form': form,
        'email': email,
        'otp_type': otp_type
    })

# ==================== LOGIN ====================
def login_view(request):
    if request.user.is_authenticated:
        return redirect('Ecom:home')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            login_identifier = form.cleaned_data['login_identifier']
            password = form.cleaned_data['password']
            
            # Get user by email or phone
            user = get_user_by_identifier(login_identifier)
            
            if user:
                # Check password
                if user.check_password(password):
                    if not user.is_active:
                        messages.error(request, 'Account is not verified. Please check your email for OTP.')
                        return redirect('Ecom:login')
                    
                    # Send OTP for 2FA login
                    create_and_send_otp(user, 'login')
                    request.session['login_user_id'] = user.id
                    messages.success(request, f'OTP sent to your email. Please verify to login.')
                    return redirect('Ecom:verify_otp_login')
                else:
                    messages.error(request, 'Invalid password.')
            else:
                messages.error(request, 'No account found with this email or phone number.')
    else:
        form = LoginForm()
    
    return render(request, 'Ecom/auth/login.html', {'form': form})

# ==================== VERIFY OTP (Login 2FA) ====================
def verify_otp_login_view(request):
    user_id = request.session.get('login_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please login again.')
        return redirect('Ecom:login')
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            is_valid, message, otp = verify_otp(user.email, otp_code, 'login')
            
            if is_valid:
                login(request, user)
                request.session.pop('login_user_id', None)
                messages.success(request, f'Welcome back, {user.full_name}!')
                
                if user.is_admin:
                    return redirect('Ecom:admin_dashboard')
                else:
                    return redirect('Ecom:home')
            else:
                messages.error(request, message)
    else:
        form = OTPVerificationForm()
    
    return render(request, 'Ecom/auth/verify_otp_login.html', {
        'form': form,
        'email': user.email
    })
# ==================== RESEND OTP ====================
def resend_otp_view(request, otp_type):
    if otp_type == 'signup':
        email = request.session.get('pending_email')
        user_data = request.session.get('pending_user_data')
        if not email or not user_data:
            messages.error(request, 'Session expired.')
            return redirect('Ecom:customer_signup')
        
        create_and_send_otp(email, 'signup', user_data.get('full_name', 'User'))
        messages.success(request, 'New OTP sent to your email.')
        return redirect('Ecom:verify_otp')
    
    elif otp_type == 'login':
        user_id = request.session.get('login_user_id')
        if not user_id:
            messages.error(request, 'Session expired.')
            return redirect('Ecom:login')
        user = get_object_or_404(User, id=user_id)
        create_and_send_otp(user, 'login')
        messages.success(request, 'New OTP sent to your email.')
        return redirect('Ecom:verify_otp_login')
    
    return redirect('Ecom:home')

# ==================== FORGOT PASSWORD ====================
def forgot_password_view(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            login_identifier = form.cleaned_data['login_identifier']
            user = get_user_by_identifier(login_identifier)
            
            if user:
                create_and_send_otp(user, 'forgot_password')
                request.session['reset_user_id'] = user.id
                messages.success(request, 'OTP sent to your email. Please verify to reset your password.')
                return redirect('Ecom:verify_forgot_password')
            else:
                messages.error(request, 'No account found with this email or phone number.')
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'Ecom/auth/forgot_password.html', {'form': form})

# ==================== VERIFY FORGOT PASSWORD OTP ====================
def verify_forgot_password_view(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('Ecom:forgot_password')
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'Ecom/auth/verify_forgot_password.html', {'email': user.email})
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'Ecom/auth/verify_forgot_password.html', {'email': user.email})
        
        is_valid, message, otp = verify_otp(user.email, otp_code, 'forgot_password')
        
        if is_valid:
            user.set_password(new_password)
            user.save()
            request.session.pop('reset_user_id', None)
            messages.success(request, 'Password reset successful! Please login with your new password.')
            return redirect('Ecom:login')
        else:
            messages.error(request, message)
    
    return render(request, 'Ecom/auth/verify_forgot_password.html', {'email': user.email})

# ==================== LOGOUT ====================
def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('Ecom:home')

# ==================== PROFILE VIEW ====================
@login_required
def profile_view(request):
    user = request.user
    profile = user.profile
    addresses = user.addresses.all()
    
    context = {
        'user': user,
        'profile': profile,
        'addresses': addresses,
    }
    return render(request, 'Ecom/profile/profile.html', context)

# ==================== UPDATE PROFILE ====================
@login_required
def update_profile_view(request):
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            if 'profile_picture' in request.FILES and profile.profile_picture:
                delete_file_if_exists(profile.profile_picture.name)
            
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('Ecom:profile')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'Ecom/profile/update_profile.html', context)

# ==================== CHANGE PASSWORD ====================
@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            old_password = form.cleaned_data['old_password']
            new_password = form.cleaned_data['new_password']
            
            if not request.user.check_password(old_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('Ecom:change_password')
            
            create_and_send_otp(request.user, 'change_password')
            request.session['change_password'] = True
            request.session['new_password'] = new_password
            messages.success(request, 'OTP sent to your email. Please verify to change password.')
            return redirect('Ecom:verify_change_password')
    else:
        form = ChangePasswordForm()
    
    return render(request, 'Ecom/profile/change_password.html', {'form': form})

# ==================== VERIFY CHANGE PASSWORD OTP ====================
@login_required
def verify_change_password_view(request):
    if not request.session.get('change_password'):
        messages.error(request, 'Session expired. Please try again.')
        return redirect('Ecom:change_password')
    
    new_password = request.session.get('new_password')
    
    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        is_valid, message, otp = verify_otp(request.user.email, otp_code, 'change_password')
        
        if is_valid:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            request.session.pop('change_password', None)
            request.session.pop('new_password', None)
            messages.success(request, 'Password changed successfully!')
            return redirect('Ecom:profile')
        else:
            messages.error(request, message)
    
    return render(request, 'Ecom/auth/verify_change_password.html', {'email': request.user.email})

# ==================== ADDRESS MANAGEMENT ====================
@login_required
def add_address_view(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            
            if request.user.addresses.count() == 0:
                address.is_default = True
            
            address.save()
            messages.success(request, 'Address added successfully!')
            return redirect('Ecom:profile')
    else:
        form = AddressForm()
    
    return render(request, 'Ecom/profile/address_form.html', {
        'form': form,
        'address': None
    })

@login_required
def edit_address_view(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('Ecom:profile')
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'Ecom/profile/address_form.html', {
        'form': form,
        'address': address
    })

@login_required
def delete_address_view(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.user.addresses.count() == 1:
        messages.error(request, 'You cannot delete your only address. Please add another address first.')
        return redirect('Ecom:profile')
    
    address.delete()
    messages.success(request, 'Address deleted successfully!')
    return redirect('Ecom:profile')

@login_required
def set_default_address_view(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.is_default = True
    address.save()
    messages.success(request, 'Default address updated successfully!')
    return redirect('Ecom:profile')

# ==================== ADMIN DASHBOARD ====================
@login_required
def admin_dashboard_view(request):
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    context = {
        'total_users': User.objects.filter(role='customer').count(),
        'total_admins': User.objects.filter(role='admin').count(),
        'total_addresses': Address.objects.count(),
    }
    return render(request, 'Ecom/admin/dashboard.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Count, Avg
from .models import (
    Category, SubCategory, Product, ProductImage, 
    ProductVariant, VariantImage, ProductReview, 
    InventoryLog, RecentlyViewed
)
from .forms import CategoryForm, SubCategoryForm, ProductForm, ProductReviewForm
import json

# ==================== AJAX VIEWS ====================

def get_subcategories_ajax(request):
    """Get subcategories based on category selection"""
    category_id = request.GET.get('category_id')
    if category_id:
        subcategories = SubCategory.objects.filter(category_id=category_id, is_active=True).values('id', 'name')
        return JsonResponse(list(subcategories), safe=False)
    return JsonResponse([], safe=False)

# ==================== CATEGORY VIEWS ====================

@login_required
def category_list_view(request):
    categories = Category.objects.all()
    return render(request, 'Ecom/admin/category_list.html', {'categories': categories})

@login_required
def category_create_view(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('Ecom:category_list')
    else:
        form = CategoryForm()
    return render(request, 'Ecom/admin/category_form.html', {'form': form, 'action': 'Create'})

@login_required
def category_edit_view(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('Ecom:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'Ecom/admin/category_form.html', {'form': form, 'action': 'Edit'})

@login_required
def category_delete_view(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if category.subcategories.exists():
        messages.error(request, 'Cannot delete category with subcategories.')
        return redirect('Ecom:category_list')
    category.delete()
    messages.success(request, 'Category deleted successfully!')
    return redirect('Ecom:category_list')

# ==================== SUBCATEGORY VIEWS ====================

@login_required
def subcategory_list_view(request):
    subcategories = SubCategory.objects.select_related('category').all()
    return render(request, 'Ecom/admin/subcategory_list.html', {'subcategories': subcategories})

@login_required
def subcategory_create_view(request):
    if request.method == 'POST':
        form = SubCategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'SubCategory created successfully!')
            return redirect('Ecom:subcategory_list')
    else:
        form = SubCategoryForm()
    return render(request, 'Ecom/admin/subcategory_form.html', {'form': form, 'action': 'Create'})

@login_required
def subcategory_edit_view(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    if request.method == 'POST':
        form = SubCategoryForm(request.POST, request.FILES, instance=subcategory)
        if form.is_valid():
            form.save()
            messages.success(request, 'SubCategory updated successfully!')
            return redirect('Ecom:subcategory_list')
    else:
        form = SubCategoryForm(instance=subcategory)
    return render(request, 'Ecom/admin/subcategory_form.html', {'form': form, 'action': 'Edit'})

@login_required
def subcategory_delete_view(request, subcategory_id):
    subcategory = get_object_or_404(SubCategory, id=subcategory_id)
    subcategory.delete()
    messages.success(request, 'SubCategory deleted successfully!')
    return redirect('Ecom:subcategory_list')

# ==================== PRODUCT LIST VIEW ====================

@login_required
def product_list_view(request):
    products = Product.objects.select_related('category', 'subcategory').all()
    paginator = Paginator(products, 20)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    return render(request, 'Ecom/admin/product_list.html', {'products': products_page})

# ==================== PRODUCT DETAIL VIEW (Public) ====================

def product_detail_view(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    
    # Add to recently viewed
    if request.user.is_authenticated:
        RecentlyViewed.add_view(request.user, product)
    
    # Get reviews
    reviews = product.reviews.filter(is_approved=True)
    
    # Get similar products
    similar_products = product.get_similar_products(limit=6)
    
    # Get product variants
    variants = product.variants.filter(is_active=True)
    
    context = {
        'product': product,
        'reviews': reviews,
        'similar_products': similar_products,
        'variants': variants,
    }
    return render(request, 'Ecom/product_detail.html', context)

# ==================== PRODUCT DETAIL VIEW (Admin) ====================

@login_required
def product_admin_detail_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'Ecom/admin/product_detail.html', {'product': product})

# ==================== PRODUCT DELETE ====================

@login_required
def product_delete_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    messages.success(request, 'Product deleted successfully!')
    return redirect('Ecom:product_list')

# ==================== LOW STOCK ALERTS ====================

@login_required
def low_stock_alert_view(request):
    """View all products with low stock"""
    low_stock_products = Product.objects.filter(
        is_active=True,
        stock_quantity__lte=models.F('low_stock_threshold'),
        stock_quantity__gt=0
    ).order_by('stock_quantity')
    
    out_of_stock_products = Product.objects.filter(
        is_active=True,
        stock_quantity=0
    ).order_by('name')
    
    low_stock_variants = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity__lte=models.F('low_stock_threshold'),
        stock_quantity__gt=0
    ).select_related('product')
    
    out_of_stock_variants = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity=0
    ).select_related('product')
    
    context = {
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'low_stock_variants': low_stock_variants,
        'out_of_stock_variants': out_of_stock_variants,
    }
    return render(request, 'Ecom/admin/low_stock_alerts.html', context)

# ==================== RECENTLY VIEWED ====================

@login_required
def recently_viewed_view(request):
    """View recently viewed products"""
    recent_items = RecentlyViewed.get_recently_viewed(request.user, limit=20)
    return render(request, 'Ecom/recently_viewed.html', {'recent_items': recent_items})

# ==================== SMART PRODUCT CREATE/EDIT ====================

@login_required
def product_smart_create_view(request):
    """UNIFIED: Smart create with product, images, variants, variant images all in ONE form"""
    
    if request.method == 'POST':
        with transaction.atomic():
            product_form = ProductForm(request.POST)
            if product_form.is_valid():
                product = product_form.save()
                
                # Handle Product Images
                product_images = request.FILES.getlist('product_images')
                for index, image in enumerate(product_images):
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                        is_primary=(index == 0),
                        display_order=index
                    )
                
                # Handle Variants with proper type conversion
                variant_names = request.POST.getlist('variant_name[]')
                variant_skus = request.POST.getlist('variant_sku[]')
                variant_colors = request.POST.getlist('variant_color[]')
                variant_sizes = request.POST.getlist('variant_size[]')
                variant_materials = request.POST.getlist('variant_material[]')
                variant_weights = request.POST.getlist('variant_weight[]')
                variant_prices = request.POST.getlist('variant_price[]')
                variant_discounts = request.POST.getlist('variant_discount[]')
                variant_stocks = request.POST.getlist('variant_stock[]')
                variant_low_stock = request.POST.getlist('variant_low_stock[]')
                variant_descriptions = request.POST.getlist('variant_description[]')
                variant_specs = request.POST.getlist('variant_specifications[]')
                variant_features = request.POST.getlist('variant_features[]')
                variant_warranty_months = request.POST.getlist('variant_warranty_months[]')
                variant_warranty_details = request.POST.getlist('variant_warranty_details[]')
                
                for i in range(len(variant_skus)):
                    sku = variant_skus[i].strip() if i < len(variant_skus) else ''
                    price = variant_prices[i] if i < len(variant_prices) else '0'
                    
                    if sku and price:
                        # Convert values to proper types
                        try:
                            variant_price = float(price)
                        except (ValueError, TypeError):
                            variant_price = 0.0
                        
                        try:
                            variant_discount = float(variant_discounts[i]) if i < len(variant_discounts) and variant_discounts[i] else 0
                        except (ValueError, TypeError):
                            variant_discount = 0
                        
                        try:
                            variant_stock = int(variant_stocks[i]) if i < len(variant_stocks) and variant_stocks[i] else 0
                        except (ValueError, TypeError):
                            variant_stock = 0
                        
                        try:
                            variant_low_stock_threshold = int(variant_low_stock[i]) if i < len(variant_low_stock) and variant_low_stock[i] else 5
                        except (ValueError, TypeError):
                            variant_low_stock_threshold = 5
                        
                        try:
                            variant_weight = float(variant_weights[i]) if i < len(variant_weights) and variant_weights[i] else None
                        except (ValueError, TypeError):
                            variant_weight = None
                        
                        try:
                            variant_warranty = int(variant_warranty_months[i]) if i < len(variant_warranty_months) and variant_warranty_months[i] else 0
                        except (ValueError, TypeError):
                            variant_warranty = 0
                        
                        variant_name = variant_names[i] if i < len(variant_names) else ''
                        variant_color = variant_colors[i] if i < len(variant_colors) else ''
                        variant_size = variant_sizes[i] if i < len(variant_sizes) else ''
                        variant_material = variant_materials[i] if i < len(variant_materials) else ''
                        variant_description = variant_descriptions[i] if i < len(variant_descriptions) else ''
                        variant_spec = variant_specs[i] if i < len(variant_specs) else ''
                        variant_feature = variant_features[i] if i < len(variant_features) else ''
                        variant_warranty_detail = variant_warranty_details[i] if i < len(variant_warranty_details) else ''
                        
                        variant = ProductVariant.objects.create(
                            product=product,
                            name=variant_name,
                            sku=sku,
                            color=variant_color,
                            size=variant_size,
                            material=variant_material,
                            weight=variant_weight,
                            price=variant_price,
                            discount_percentage=variant_discount,
                            stock_quantity=variant_stock,
                            low_stock_threshold=variant_low_stock_threshold,
                            description=variant_description,
                            specifications=variant_spec,
                            features=variant_feature,
                            warranty_months=variant_warranty,
                            warranty_details=variant_warranty_detail,
                            is_active=True
                        )
                        
                        # Handle Variant Images
                        variant_images_key = f'variant_images_{i}'
                        if variant_images_key in request.FILES:
                            variant_images = request.FILES.getlist(variant_images_key)
                            for img_index, img in enumerate(variant_images):
                                VariantImage.objects.create(
                                    variant=variant,
                                    image=img,
                                    is_primary=(img_index == 0),
                                    display_order=img_index
                                )
                        
                        # Create Inventory Log
                        if variant.stock_quantity > 0:
                            InventoryLog.objects.create(
                                variant=variant,
                                quantity_change=variant.stock_quantity,
                                previous_quantity=0,
                                new_quantity=variant.stock_quantity,
                                action='purchase',
                                note='Initial stock added',
                                created_by=request.user
                            )
                
                messages.success(request, 'Product created successfully with all variants and images!')
                return redirect('Ecom:product_admin_detail', product_id=product.id)
            else:
                messages.error(request, 'Please fix the errors below.')
    else:
        product_form = ProductForm()
    
    categories = Category.objects.filter(is_active=True)
    return render(request, 'Ecom/admin/product_smart_form.html', {
        'product_form': product_form,
        'categories': categories,
        'is_edit': False,
        'product': None
    })

# ==================== PRODUCT SMART EDIT VIEW ====================

@login_required
def product_smart_edit_view(request, product_id):
    """UNIFIED: Smart edit with product, images, variants, variant images all in ONE form"""
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        with transaction.atomic():
            product_form = ProductForm(request.POST, instance=product)
            if product_form.is_valid():
                product = product_form.save()
                
                # Handle New Product Images
                product_images = request.FILES.getlist('product_images')
                existing_image_count = product.images.count()
                for index, image in enumerate(product_images):
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                        is_primary=(index == 0 and existing_image_count == 0),
                        display_order=existing_image_count + index
                    )
                
                # Handle Variants with proper type conversion
                variant_ids = request.POST.getlist('variant_id[]')
                variant_names = request.POST.getlist('variant_name[]')
                variant_skus = request.POST.getlist('variant_sku[]')
                variant_colors = request.POST.getlist('variant_color[]')
                variant_sizes = request.POST.getlist('variant_size[]')
                variant_materials = request.POST.getlist('variant_material[]')
                variant_weights = request.POST.getlist('variant_weight[]')
                variant_prices = request.POST.getlist('variant_price[]')
                variant_discounts = request.POST.getlist('variant_discount[]')
                variant_stocks = request.POST.getlist('variant_stock[]')
                variant_low_stock = request.POST.getlist('variant_low_stock[]')
                variant_descriptions = request.POST.getlist('variant_description[]')
                variant_specs = request.POST.getlist('variant_specifications[]')
                variant_features = request.POST.getlist('variant_features[]')
                variant_warranty_months = request.POST.getlist('variant_warranty_months[]')
                variant_warranty_details = request.POST.getlist('variant_warranty_details[]')
                variant_is_active = request.POST.getlist('variant_is_active[]')
                variant_delete = request.POST.getlist('variant_delete[]')
                
                kept_variant_ids = []
                
                for i in range(len(variant_skus)):
                    # Skip if marked for deletion
                    if i < len(variant_delete) and variant_delete[i] == 'on':
                        continue
                    
                    sku = variant_skus[i].strip() if i < len(variant_skus) else ''
                    price = variant_prices[i] if i < len(variant_prices) else '0'
                    
                    if sku and price:
                        variant_id = variant_ids[i] if i < len(variant_ids) and variant_ids[i] else None
                        
                        # Convert values to proper types
                        try:
                            variant_price = float(price)
                        except (ValueError, TypeError):
                            variant_price = 0.0
                        
                        try:
                            variant_discount = float(variant_discounts[i]) if i < len(variant_discounts) and variant_discounts[i] else 0
                        except (ValueError, TypeError):
                            variant_discount = 0
                        
                        try:
                            variant_stock = int(variant_stocks[i]) if i < len(variant_stocks) and variant_stocks[i] else 0
                        except (ValueError, TypeError):
                            variant_stock = 0
                        
                        try:
                            variant_low_stock_threshold = int(variant_low_stock[i]) if i < len(variant_low_stock) and variant_low_stock[i] else 5
                        except (ValueError, TypeError):
                            variant_low_stock_threshold = 5
                        
                        try:
                            variant_weight = float(variant_weights[i]) if i < len(variant_weights) and variant_weights[i] else None
                        except (ValueError, TypeError):
                            variant_weight = None
                        
                        try:
                            variant_warranty = int(variant_warranty_months[i]) if i < len(variant_warranty_months) and variant_warranty_months[i] else 0
                        except (ValueError, TypeError):
                            variant_warranty = 0
                        
                        variant_name = variant_names[i] if i < len(variant_names) else ''
                        variant_color = variant_colors[i] if i < len(variant_colors) else ''
                        variant_size = variant_sizes[i] if i < len(variant_sizes) else ''
                        variant_material = variant_materials[i] if i < len(variant_materials) else ''
                        variant_description = variant_descriptions[i] if i < len(variant_descriptions) else ''
                        variant_spec = variant_specs[i] if i < len(variant_specs) else ''
                        variant_feature = variant_features[i] if i < len(variant_features) else ''
                        variant_warranty_detail = variant_warranty_details[i] if i < len(variant_warranty_details) else ''
                        variant_active = variant_is_active[i] == 'on' if i < len(variant_is_active) else True
                        
                        # Get variant images for this index
                        variant_images_key = f'variant_images_{i}'
                        variant_images = request.FILES.getlist(variant_images_key) if variant_images_key in request.FILES else []
                        
                        if variant_id and variant_id != '':
                            # UPDATE EXISTING VARIANT
                            try:
                                variant = get_object_or_404(ProductVariant, id=int(variant_id), product=product)
                            except (ValueError, TypeError):
                                continue
                                
                            old_stock = variant.stock_quantity
                            
                            variant.name = variant_name
                            variant.sku = sku
                            variant.color = variant_color
                            variant.size = variant_size
                            variant.material = variant_material
                            variant.weight = variant_weight
                            variant.price = variant_price
                            variant.discount_percentage = variant_discount
                            variant.stock_quantity = variant_stock
                            variant.low_stock_threshold = variant_low_stock_threshold
                            variant.description = variant_description
                            variant.specifications = variant_spec
                            variant.features = variant_feature
                            variant.warranty_months = variant_warranty
                            variant.warranty_details = variant_warranty_detail
                            variant.is_active = variant_active
                            variant.save()
                            kept_variant_ids.append(variant.id)
                            
                            # Log inventory change if stock changed
                            if variant.stock_quantity != old_stock:
                                InventoryLog.objects.create(
                                    variant=variant,
                                    quantity_change=variant.stock_quantity - old_stock,
                                    previous_quantity=old_stock,
                                    new_quantity=variant.stock_quantity,
                                    action='adjustment',
                                    note='Stock updated via product edit',
                                    created_by=request.user
                                )
                            
                            # Handle new variant images for existing variant
                            if variant_images:
                                existing_variant_images = variant.images.count()
                                for img_index, img in enumerate(variant_images):
                                    VariantImage.objects.create(
                                        variant=variant,
                                        image=img,
                                        is_primary=(img_index == 0 and existing_variant_images == 0),
                                        display_order=existing_variant_images + img_index
                                    )
                        
                        else:
                            # CREATE NEW VARIANT
                            variant = ProductVariant.objects.create(
                                product=product,
                                name=variant_name,
                                sku=sku,
                                color=variant_color,
                                size=variant_size,
                                material=variant_material,
                                weight=variant_weight,
                                price=variant_price,
                                discount_percentage=variant_discount,
                                stock_quantity=variant_stock,
                                low_stock_threshold=variant_low_stock_threshold,
                                description=variant_description,
                                specifications=variant_spec,
                                features=variant_feature,
                                warranty_months=variant_warranty,
                                warranty_details=variant_warranty_detail,
                                is_active=variant_active
                            )
                            kept_variant_ids.append(variant.id)
                            
                            # Create inventory log for new variant
                            if variant.stock_quantity > 0:
                                InventoryLog.objects.create(
                                    variant=variant,
                                    quantity_change=variant.stock_quantity,
                                    previous_quantity=0,
                                    new_quantity=variant.stock_quantity,
                                    action='purchase',
                                    note='New variant added via product edit',
                                    created_by=request.user
                                )
                            
                            # Handle variant images for new variant
                            if variant_images:
                                for img_index, img in enumerate(variant_images):
                                    VariantImage.objects.create(
                                        variant=variant,
                                        image=img,
                                        is_primary=(img_index == 0),
                                        display_order=img_index
                                    )
                
                # Delete variants that were removed
                deleted_variants = ProductVariant.objects.filter(product=product).exclude(id__in=kept_variant_ids)
                for variant in deleted_variants:
                    InventoryLog.objects.create(
                        variant=variant,
                        quantity_change=0,
                        previous_quantity=variant.stock_quantity,
                        new_quantity=0,
                        action='adjustment',
                        note='Variant deleted',
                        created_by=request.user
                    )
                deleted_variants.delete()
                
                messages.success(request, 'Product updated successfully!')
                return redirect('Ecom:product_admin_detail', product_id=product.id)
            else:
                messages.error(request, 'Please fix the errors below.')
    else:
        product_form = ProductForm(instance=product)
    
    categories = Category.objects.filter(is_active=True)
    return render(request, 'Ecom/admin/product_smart_form.html', {
        'product_form': product_form,
        'categories': categories,
        'is_edit': True,
        'product': product
    })
    
# ==================== REVIEW VIEWS ====================

@login_required
def review_list_view(request):
    reviews = ProductReview.objects.select_related('product', 'user').all()
    return render(request, 'Ecom/admin/review_list.html', {'reviews': reviews})

@login_required
def review_approve_view(request, review_id):
    review = get_object_or_404(ProductReview, id=review_id)
    review.is_approved = True
    review.save()
    messages.success(request, 'Review approved successfully!')
    return redirect('Ecom:review_list')

@login_required
def review_delete_view(request, review_id):
    review = get_object_or_404(ProductReview, id=review_id)
    review.delete()
    messages.success(request, 'Review deleted successfully!')
    return redirect('Ecom:review_list')

# ==================== INVENTORY LOG VIEW ====================

@login_required
def inventory_log_view(request):
    logs = InventoryLog.objects.select_related('product', 'variant', 'created_by').all()
    paginator = Paginator(logs, 50)
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)
    return render(request, 'Ecom/admin/inventory_log.html', {'logs': logs_page})

# ==================== ADD REVIEW (Public) ====================

@login_required
def add_review_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # Check if user already reviewed
    if ProductReview.objects.filter(product=product, user=request.user).exists():
        messages.error(request, 'You have already reviewed this product.')
        return redirect('Ecom:product_detail', product_id=product.id)
    
    if request.method == 'POST':
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            # Check if user purchased this product (you can implement order check)
            review.is_verified_purchase = False  # Set to True if order exists
            review.save()
            messages.success(request, 'Review submitted successfully! It will be visible after approval.')
            return redirect('Ecom:product_detail', product_id=product.id)
    else:
        form = ProductReviewForm()
    
    return render(request, 'Ecom/add_review.html', {
        'form': form,
        'product': product
    })

@login_required
def delete_product_image_ajax(request, image_id):
    """Delete product image via AJAX"""
    if request.method == 'POST':
        image = get_object_or_404(ProductImage, id=image_id)
        # Check if user has permission (admin only)
        if not request.user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        image.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@login_required
def delete_variant_image_ajax(request, image_id):
    """Delete variant image via AJAX"""
    if request.method == 'POST':
        image = get_object_or_404(VariantImage, id=image_id)
        if not request.user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        image.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

