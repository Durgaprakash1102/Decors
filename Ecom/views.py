from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import User, Profile, Address, OTP
from .forms import *
from .utils import create_and_send_otp, verify_otp, delete_file_if_exists, get_user_by_identifier
from decimal import Decimal


from django.db.models import Q, Count, Avg, F, DecimalField
from django.db.models.functions import Coalesce


def home(request):
    """Home page with best sellers, featured, new arrivals, categories, subcategories, and deals of the day"""
    
    # Get active products
    products = Product.objects.filter(is_active=True)
    
    # ============================================
    # BEST SELLERS - products marked as best seller
    # ============================================
    best_sellers = products.filter(is_best_seller=True).order_by('-created_at')[:8]
    
    # ============================================
    # FEATURED PRODUCTS
    # ============================================
    featured_products = products.filter(is_featured=True).order_by('-created_at')[:8]
    
    # ============================================
    # NEW ARRIVALS - products marked as new
    # ============================================
    new_arrivals = products.filter(is_new=True).order_by('-created_at')[:8]
    
    # ============================================
    # ALTERNATIVE: Get newest products regardless of is_new flag
    # ============================================
    newest_products = products.order_by('-created_at')[:8]
    
    # ============================================
    # DEALS OF THE DAY - Products with highest discounts
    # ============================================
    # Get products with discount > 0, sorted by discount percentage (highest first)
    deals_of_the_day = products.filter(
        discount_percentage__gt=0
    ).order_by('-discount_percentage')[:6]
    
    # If less than 6 products with discount, get some without discount to fill
    if deals_of_the_day.count() < 6:
        additional_products = products.exclude(
            id__in=deals_of_the_day.values_list('id', flat=True)
        ).order_by('-created_at')[:6 - deals_of_the_day.count()]
        # Combine querysets
        deals_of_the_day = list(deals_of_the_day) + list(additional_products)
    else:
        deals_of_the_day = list(deals_of_the_day)
    
    # ============================================
    # CATEGORIES with product count
    # ============================================
    categories = Category.objects.filter(
        is_active=True,
        products__is_active=True
    ).distinct().annotate(
        product_count=Count('products')
    ).order_by('name')
    
    # ============================================
    # SUBCATEGORIES with product count
    # ============================================
    subcategories = SubCategory.objects.filter(
        is_active=True,
        products__is_active=True
    ).distinct().annotate(
        product_count=Count('products')
    ).select_related('category').order_by('category__name', 'name')
    
    # ============================================
    # TOP RATED PRODUCTS
    # ============================================
    top_rated = products.annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    ).filter(
        avg_rating__gte=4
    ).order_by('-avg_rating')[:8]
    
    # ============================================
    # RECENTLY VIEWED - if user is authenticated
    # ============================================
    recently_viewed = []
    if request.user.is_authenticated:
        from .models import RecentlyViewed
        recently_viewed_items = RecentlyViewed.objects.filter(
            user=request.user
        ).select_related('product').order_by('-viewed_at')[:8]
        recently_viewed = [item.product for item in recently_viewed_items]
    
    context = {
        'best_sellers': best_sellers,
        'featured_products': featured_products,
        'new_arrivals': new_arrivals,
        'newest_products': newest_products,
        'deals_of_the_day': deals_of_the_day,
        'top_rated': top_rated,
        'categories': categories,
        'subcategories': subcategories,
        'recently_viewed': recently_viewed,
    }
    return render(request, 'home.html', context)

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
    
    # ============================================
    # CHECK IF PRODUCT IS IN CART OR WISHLIST
    # ============================================
    in_cart = False
    in_wishlist = False
    cart_item_id = None
    wishlist_item_id = None
    
    if request.user.is_authenticated:
        # Check if product is in cart
        cart = get_or_create_cart(request)
        cart_item = CartItem.objects.filter(cart=cart, product=product).first()
        if cart_item:
            in_cart = True
            cart_item_id = cart_item.id
        
        # Check if product is in wishlist
        wishlist_item = WishlistItem.objects.filter(
            wishlist__user=request.user, 
            product=product
        ).first()
        if wishlist_item:
            in_wishlist = True
            wishlist_item_id = wishlist_item.id
    
    context = {
        'product': product,
        'reviews': reviews,
        'similar_products': similar_products,
        'variants': variants,
        'in_cart': in_cart,
        'cart_item_id': cart_item_id,
        'in_wishlist': in_wishlist,
        'wishlist_item_id': wishlist_item_id,
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

from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Min, Max, F, Avg, Value, DecimalField
from django.db.models.functions import Coalesce, Upper
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Product, Category, SubCategory, ProductVariant, ProductReview
import re

def normalize_value(value, attr_type='string'):
    """
    Universal normalization using regex patterns
    Handles ANY value entered - no hardcoding!
    """
    if not value:
        return ''
    
    value = str(value).strip()
    
    # Remove extra spaces (multiple spaces -> single space)
    value = re.sub(r'\s+', ' ', value)
    
    # Remove leading/trailing spaces
    value = value.strip()
    
    if attr_type == 'size':
        # ============================================
        # SIZE NORMALIZATION (Universal)
        # ============================================
        
        # Convert to uppercase for consistent comparison
        upper_value = value.upper()
        
        # Pattern 1: Numbers with measurements (1M, 1 M, 1m, 1 meter, 1metre)
        # Captures: number + optional space + (M|METER|METRE)
        measurement_pattern = re.compile(r'^(\d+)\s*[M|METER|METRE]+$', re.IGNORECASE)
        match = measurement_pattern.match(upper_value)
        if match:
            number = match.group(1)
            return f"{number} METER"
        
        # Pattern 2: Number followed by 'FT' or 'FEET' (5FT, 5 FT, 5feet)
        feet_pattern = re.compile(r'^(\d+)\s*[F|FT|FEET]+$', re.IGNORECASE)
        match = feet_pattern.match(upper_value)
        if match:
            number = match.group(1)
            return f"{number} FEET"
        
        # Pattern 3: Number followed by 'IN' or 'INCH' (10IN, 10 IN, 10inch)
        inch_pattern = re.compile(r'^(\d+)\s*[I|IN|INCH]+$', re.IGNORECASE)
        match = inch_pattern.match(upper_value)
        if match:
            number = match.group(1)
            return f"{number} INCH"
        
        # Pattern 4: Number followed by 'CM' (50CM, 50 CM, 50cm)
        cm_pattern = re.compile(r'^(\d+)\s*[C|CM]+$', re.IGNORECASE)
        match = cm_pattern.match(upper_value)
        if match:
            number = match.group(1)
            return f"{number} CM"
        
        # Pattern 5: Number only (e.g., "42", "36", "38")
        number_pattern = re.compile(r'^(\d+)$')
        match = number_pattern.match(upper_value)
        if match:
            return upper_value
        
        # Pattern 6: Single letters with optional X prefix (S, M, L, XL, XXL, XXXL, XS)
        size_letters = re.compile(r'^X*[SML]+$', re.IGNORECASE)
        if size_letters.match(upper_value):
            return upper_value
        
        # Pattern 7: Number with optional + (38+, 40+, XL+)
        plus_pattern = re.compile(r'^(\d+)\+$')
        match = plus_pattern.match(upper_value)
        if match:
            return f"{match.group(1)}+"
        
        # Pattern 8: Range like 38-40, S-M, XL-XXL
        range_pattern = re.compile(r'^(.+)\s*[-–—]\s*(.+)$')
        match = range_pattern.match(value)
        if match:
            left = normalize_value(match.group(1), 'size')
            right = normalize_value(match.group(2), 'size')
            return f"{left} - {right}"
        
        # If no pattern matches, return as-is (but uppercase)
        return upper_value
    
    elif attr_type == 'color':
        # ============================================
        # COLOR NORMALIZATION (Universal)
        # ============================================
        
        # Convert to Title Case (e.g., "red" -> "Red", "dark blue" -> "Dark Blue")
        # But keep special cases like "Off-White", "Navy Blue"
        words = value.split()
        normalized_words = []
        for word in words:
            # Skip articles and prepositions
            if word.lower() in ['of', 'the', 'and', 'or']:
                normalized_words.append(word.lower())
            else:
                # Capitalize first letter
                normalized_words.append(word.capitalize())
        value = ' '.join(normalized_words)
        
        # Handle compound colors with hyphen (Off-White, Jet-Black)
        hyphen_pattern = re.compile(r'^([A-Za-z]+)-([A-Za-z]+)$')
        match = hyphen_pattern.match(value)
        if match:
            return f"{match.group(1).capitalize()}-{match.group(2).capitalize()}"
        
        return value
    
    elif attr_type == 'brand':
        # ============================================
        # BRAND NORMALIZATION (Universal)
        # ============================================
        
        # Remove extra spaces
        value = re.sub(r'\s+', ' ', value).strip()
        
        # Handle special cases like "McDonald's", "O'Reilly"
        # Keep apostrophes and special characters
        value = re.sub(r'\s+', ' ', value)
        
        # Title case for brands, but keep common abbreviations uppercase
        words = value.split()
        normalized_words = []
        for word in words:
            # Keep common abbreviations uppercase
            if word.upper() in ['USA', 'UK', 'EU', 'US', 'NYC', 'LA', 'DIY', 'LED', 'LCD', 'OLED']:
                normalized_words.append(word.upper())
            else:
                normalized_words.append(word.capitalize())
        return ' '.join(normalized_words)
    
    elif attr_type == 'material':
        # ============================================
        # MATERIAL NORMALIZATION (Universal)
        # ============================================
        
        # Title case for materials
        words = value.split()
        normalized_words = []
        for word in words:
            # Keep common materials in lowercase or specific case
            if word.lower() in ['and', 'or', 'with']:
                normalized_words.append(word.lower())
            else:
                normalized_words.append(word.capitalize())
        return ' '.join(normalized_words)
    
    # Default: return as-is with proper formatting
    return value.title()

def get_unique_attribute_values(products, attr_name, attr_type='string'):
    """Get unique normalized values for an attribute from products and variants"""
    values = set()
    
    # Get from products
    for product in products:
        value = getattr(product, attr_name, '')
        if value and value.strip():
            normalized = normalize_value(value, attr_type)
            if normalized:
                values.add(normalized)
    
    # Get from variants
    variant_values = ProductVariant.objects.filter(
        product__in=products,
        is_active=True
    ).exclude(**{f'{attr_name}__isnull': True}).exclude(**{f'{attr_name}': ''}).values_list(attr_name, flat=True).distinct()
    
    for value in variant_values:
        if value and value.strip():
            normalized = normalize_value(value, attr_type)
            if normalized:
                values.add(normalized)
    
    # Also check product color/size fields if they exist
    if attr_name == 'color':
        product_colors = products.exclude(color__isnull=True).exclude(color='').values_list('color', flat=True).distinct()
        for value in product_colors:
            if value and value.strip():
                normalized = normalize_value(value, 'color')
                if normalized:
                    values.add(normalized)
    elif attr_name == 'size':
        product_sizes = products.exclude(size__isnull=True).exclude(size='').values_list('size', flat=True).distinct()
        for value in product_sizes:
            if value and value.strip():
                normalized = normalize_value(value, 'size')
                if normalized:
                    values.add(normalized)
    elif attr_name == 'material':
        product_materials = products.exclude(material__isnull=True).exclude(material='').values_list('material', flat=True).distinct()
        for value in product_materials:
            if value and value.strip():
                normalized = normalize_value(value, 'material')
                if normalized:
                    values.add(normalized)
    
    return sorted(list(values))

def get_unique_brands(products):
    """Get unique normalized brands from products"""
    brands = set()
    for product in products:
        if product.brand and product.brand.strip():
            normalized = normalize_value(product.brand, 'brand')
            if normalized:
                brands.add(normalized)
    return sorted(list(brands))

def get_price_range(products):
    """Get min and max price from products and variants"""
    all_prices = []
    
    # Get product prices with discount applied
    for product in products:
        price = float(product.price)
        discount = float(product.discount_percentage)
        if discount > 0:
            final_price = price - (price * discount / 100)
        else:
            final_price = price
        all_prices.append(final_price)
    
    # Get variant prices with discount applied
    variants = ProductVariant.objects.filter(
        product__in=products,
        is_active=True
    )
    for variant in variants:
        price = float(variant.price)
        discount = float(variant.discount_percentage)
        if discount > 0:
            final_price = price - (price * discount / 100)
        else:
            final_price = price
        all_prices.append(final_price)
    
    if all_prices:
        return {
            'min': min(all_prices),
            'max': max(all_prices)
        }
    return {'min': 0, 'max': 1000}

def get_rating_options(products):
    """Get rating distribution for products"""
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for product in products:
        avg_rating = product.average_rating
        if avg_rating > 0:
            rating_key = int(avg_rating)
            if rating_key in rating_counts:
                rating_counts[rating_key] += 1
    
    return rating_counts

def get_filtered_products(request, products, filters):
    """Apply filters to products queryset"""
    
    # Category filter
    if filters.get('category'):
        products = products.filter(category_id=filters['category'])
    
    # Subcategory filter
    if filters.get('subcategory'):
        products = products.filter(subcategory_id=filters['subcategory'])
    
    # Brand filter - case insensitive
    if filters.get('brands'):
        # Get brands as list (handle both list and string)
        brands = filters['brands']
        if isinstance(brands, str):
            brands = [brands]
        brand_q = Q()
        for brand in brands:
            brand_q |= Q(brand__iexact=brand)
        products = products.filter(brand_q)
    
    # Color filter - case insensitive with normalized values
    if filters.get('colors'):
        colors = filters['colors']
        if isinstance(colors, str):
            colors = [colors]
        color_q = Q()
        for color in colors:
            color_q |= Q(color__iexact=color)
        variant_products = ProductVariant.objects.filter(
            product__in=products,
            color__iexact=color
        ).values_list('product_id', flat=True)
        products = products.filter(color_q | Q(id__in=variant_products))
    
    # Size filter - case insensitive with normalized values
    if filters.get('sizes'):
        sizes = filters['sizes']
        if isinstance(sizes, str):
            sizes = [sizes]
        size_q = Q()
        for size in sizes:
            size_q |= Q(size__iexact=size)
        variant_products = ProductVariant.objects.filter(
            product__in=products,
            size__iexact=size
        ).values_list('product_id', flat=True)
        products = products.filter(size_q | Q(id__in=variant_products))
    
    # Material filter
    if filters.get('materials'):
        materials = filters['materials']
        if isinstance(materials, str):
            materials = [materials]
        material_q = Q()
        for material in materials:
            material_q |= Q(material__iexact=material)
        products = products.filter(material_q)
    
    # Price range filter
    if filters.get('price_min') and filters.get('price_max'):
        price_min = float(filters['price_min'])
        price_max = float(filters['price_max'])
        
        filtered_products = []
        for product in products:
            if price_min <= float(product.final_price) <= price_max:
                filtered_products.append(product.id)
        
        variant_product_ids = ProductVariant.objects.filter(
            product__in=products,
            is_active=True
        )
        for variant in variant_product_ids:
            if price_min <= float(variant.final_price) <= price_max:
                if variant.product_id not in filtered_products:
                    filtered_products.append(variant.product_id)
        
        products = products.filter(id__in=filtered_products)
    
    # Rating filter
    if filters.get('rating'):
        rating = int(filters['rating'])
        products = products.filter(avg_rating__gte=rating)
    
    # Stock status
    if filters.get('in_stock'):
        products = products.filter(is_in_stock=True)
    
    if filters.get('is_new'):
        products = products.filter(is_new=True)
    
    # Best Seller filter
    if filters.get('is_best_seller'):
        products = products.filter(is_best_seller=True)
    
    # Featured filter
    if filters.get('is_featured'):
        products = products.filter(is_featured=True)
    
    # Search
    if filters.get('search'):
        search = filters['search']
        products = products.filter(
            Q(name__icontains=search) |
            Q(sku__icontains=search) |
            Q(brand__icontains=search) |
            Q(description__icontains=search) |
            Q(category__name__icontains=search) |
            Q(subcategory__name__icontains=search) |
            Q(color__icontains=search) |
            Q(size__icontains=search)
        )
    
    return products.distinct()

def shop_view(request):
    """Main shop page with all products and filters"""
    
    # Base queryset - only active products with average rating
    products = Product.objects.filter(is_active=True).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    )
    
    # Get filter parameters from request.GET
    # QueryDict has getlist() method
    filters = {
        'category': request.GET.get('category'),
        'subcategory': request.GET.get('subcategory'),
        'brands': request.GET.getlist('brands'),
        'colors': request.GET.getlist('colors'),
        'sizes': request.GET.getlist('sizes'),
        'materials': request.GET.getlist('materials'),
        'price_min': request.GET.get('price_min'),
        'price_max': request.GET.get('price_max'),
        'rating': request.GET.get('rating'),
        'in_stock': request.GET.get('in_stock'),
        'is_new': request.GET.get('is_new'),
        'is_best_seller': request.GET.get('is_best_seller'),
        'is_featured': request.GET.get('is_featured'),
        'search': request.GET.get('search'),
        'sort': request.GET.get('sort'),
    }
    
    # Apply filters
    products = get_filtered_products(request, products, filters)
    
    # Sorting
    sort_by = filters.get('sort', 'newest')
    
    if sort_by == 'newest':
        products = products.order_by('-created_at')
    elif sort_by == 'oldest':
        products = products.order_by('created_at')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    elif sort_by == 'popular':
        products = products.order_by('-is_best_seller', '-created_at')
    elif sort_by == 'rating_high':
        products = products.order_by(F('avg_rating').desc(nulls_last=True))
    elif sort_by == 'price_low':
        products = list(products)
        products.sort(key=lambda p: float(p.final_price))
    elif sort_by == 'price_high':
        products = list(products)
        products.sort(key=lambda p: float(p.final_price), reverse=True)
    
    # Get filter options
    all_products = Product.objects.filter(is_active=True)
    filter_options = {
        'brands': get_unique_brands(all_products),
        'colors': get_unique_attribute_values(all_products, 'color', 'color'),
        'sizes': get_unique_attribute_values(all_products, 'size', 'size'),
        'materials': get_unique_attribute_values(all_products, 'material', 'material'),
        'categories': Category.objects.filter(is_active=True, products__is_active=True).distinct().annotate(count=Count('products')),
        'subcategories': SubCategory.objects.filter(is_active=True, products__is_active=True).distinct().annotate(count=Count('products')),
        'rating_counts': get_rating_options(all_products),
    }
    
    # Get price range
    price_range = get_price_range(all_products)
    
    # Pagination
    if isinstance(products, list):
        paginator = Paginator(products, 24)
    else:
        paginator = Paginator(products, 24)
    
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    # Get current filter values for template
    current_filters = {
        'category': filters.get('category'),
        'subcategory': filters.get('subcategory'),
        'brands': filters.get('brands'),
        'colors': filters.get('colors'),
        'sizes': filters.get('sizes'),
        'materials': filters.get('materials'),
        'price_min': filters.get('price_min', price_range['min']),
        'price_max': filters.get('price_max', price_range['max']),
        'rating': filters.get('rating'),
        'in_stock': filters.get('in_stock'),
        'is_new': filters.get('is_new'),
        'is_best_seller': filters.get('is_best_seller'),
        'is_featured': filters.get('is_featured'),
        'search': filters.get('search'),
        'sort': sort_by,
    }
    
    context = {
        'products': products_page,
        'filter_options': filter_options,
        'price_range': price_range,
        'current_filters': current_filters,
        'active_filters': filters,
        'total_products': len(products) if isinstance(products, list) else products.count(),
        'sort_by': sort_by,
    }
    return render(request, 'Ecom/shop.html', context)

def category_shop_view(request, category_slug):
    """Shop page filtered by category"""
    category = get_object_or_404(Category, slug=category_slug, is_active=True)
    
    products = Product.objects.filter(category=category, is_active=True).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    )
    
    # Get filter parameters
    filters = {
        'category': category.id,
        'subcategory': request.GET.get('subcategory'),
        'brands': request.GET.getlist('brands'),
        'colors': request.GET.getlist('colors'),
        'sizes': request.GET.getlist('sizes'),
        'materials': request.GET.getlist('materials'),
        'price_min': request.GET.get('price_min'),
        'price_max': request.GET.get('price_max'),
        'rating': request.GET.get('rating'),
        'in_stock': request.GET.get('in_stock'),
        'is_new': request.GET.get('is_new'),
        'is_best_seller': request.GET.get('is_best_seller'),
        'is_featured': request.GET.get('is_featured'),
        'search': request.GET.get('search'),
        'sort': request.GET.get('sort'),
    }
    
    # Apply filters
    products = get_filtered_products(request, products, filters)
    
    # Sorting
    sort_by = filters.get('sort', 'newest')
    
    if sort_by == 'newest':
        products = products.order_by('-created_at')
    elif sort_by == 'oldest':
        products = products.order_by('created_at')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    elif sort_by == 'popular':
        products = products.order_by('-is_best_seller', '-created_at')
    elif sort_by == 'rating_high':
        products = products.order_by(F('avg_rating').desc(nulls_last=True))
    elif sort_by == 'price_low':
        products = list(products)
        products.sort(key=lambda p: float(p.final_price))
    elif sort_by == 'price_high':
        products = list(products)
        products.sort(key=lambda p: float(p.final_price), reverse=True)
    
    # Get filter options for this category
    category_products = Product.objects.filter(category=category, is_active=True)
    filter_options = {
        'brands': get_unique_brands(category_products),
        'colors': get_unique_attribute_values(category_products, 'color', 'color'),
        'sizes': get_unique_attribute_values(category_products, 'size', 'size'),
        'materials': get_unique_attribute_values(category_products, 'material', 'material'),
        'subcategories': category.subcategories.filter(is_active=True, products__is_active=True).distinct().annotate(count=Count('products')),
        'rating_counts': get_rating_options(category_products),
    }
    
    price_range = get_price_range(category_products)
    
    # Pagination
    if isinstance(products, list):
        paginator = Paginator(products, 24)
    else:
        paginator = Paginator(products, 24)
    
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    current_filters = {
        'category': category.id,
        'subcategory': filters.get('subcategory'),
        'brands': filters.get('brands'),
        'colors': filters.get('colors'),
        'sizes': filters.get('sizes'),
        'materials': filters.get('materials'),
        'price_min': filters.get('price_min', price_range['min']),
        'price_max': filters.get('price_max', price_range['max']),
        'rating': filters.get('rating'),
        'in_stock': filters.get('in_stock'),
        'is_new': filters.get('is_new'),
        'is_best_seller': filters.get('is_best_seller'),
        'is_featured': filters.get('is_featured'),
        'search': filters.get('search'),
        'sort': sort_by,
    }
    
    context = {
        'products': products_page,
        'filter_options': filter_options,
        'price_range': price_range,
        'current_filters': current_filters,
        'active_filters': filters,
        'total_products': len(products) if isinstance(products, list) else products.count(),
        'sort_by': sort_by,
        'category': category,
        'is_category_page': True,
    }
    return render(request, 'Ecom/shop.html', context)

def subcategory_shop_view(request, subcategory_slug):
    """Shop page filtered by subcategory"""
    subcategory = get_object_or_404(SubCategory, slug=subcategory_slug, is_active=True)
    
    products = Product.objects.filter(subcategory=subcategory, is_active=True).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    )
    
    # Get filter parameters
    filters = {
        'category': subcategory.category.id,
        'subcategory': subcategory.id,
        'brands': request.GET.getlist('brands'),
        'colors': request.GET.getlist('colors'),
        'sizes': request.GET.getlist('sizes'),
        'materials': request.GET.getlist('materials'),
        'price_min': request.GET.get('price_min'),
        'price_max': request.GET.get('price_max'),
        'rating': request.GET.get('rating'),
        'in_stock': request.GET.get('in_stock'),
        'is_new': request.GET.get('is_new'),
        'is_best_seller': request.GET.get('is_best_seller'),
        'is_featured': request.GET.get('is_featured'),
        'search': request.GET.get('search'),
        'sort': request.GET.get('sort'),
    }
    
    # Apply filters
    products = get_filtered_products(request, products, filters)
    
    # Sorting
    sort_by = filters.get('sort', 'newest')
    
    if sort_by == 'newest':
        products = products.order_by('-created_at')
    elif sort_by == 'oldest':
        products = products.order_by('created_at')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    elif sort_by == 'popular':
        products = products.order_by('-is_best_seller', '-created_at')
    elif sort_by == 'rating_high':
        products = products.order_by(F('avg_rating').desc(nulls_last=True))
    elif sort_by == 'price_low':
        products = list(products)
        products.sort(key=lambda p: float(p.final_price))
    elif sort_by == 'price_high':
        products = list(products)
        products.sort(key=lambda p: float(p.final_price), reverse=True)
    
    # Get filter options for this subcategory
    subcategory_products = Product.objects.filter(subcategory=subcategory, is_active=True)
    filter_options = {
        'brands': get_unique_brands(subcategory_products),
        'colors': get_unique_attribute_values(subcategory_products, 'color', 'color'),
        'sizes': get_unique_attribute_values(subcategory_products, 'size', 'size'),
        'materials': get_unique_attribute_values(subcategory_products, 'material', 'material'),
        'rating_counts': get_rating_options(subcategory_products),
    }
    
    price_range = get_price_range(subcategory_products)
    
    # Pagination
    if isinstance(products, list):
        paginator = Paginator(products, 24)
    else:
        paginator = Paginator(products, 24)
    
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    current_filters = {
        'category': subcategory.category.id,
        'subcategory': subcategory.id,
        'brands': filters.get('brands'),
        'colors': filters.get('colors'),
        'sizes': filters.get('sizes'),
        'materials': filters.get('materials'),
        'price_min': filters.get('price_min', price_range['min']),
        'price_max': filters.get('price_max', price_range['max']),
        'rating': filters.get('rating'),
        'in_stock': filters.get('in_stock'),
        'is_new': filters.get('is_new'),
        'is_best_seller': filters.get('is_best_seller'),
        'is_featured': filters.get('is_featured'),
        'search': filters.get('search'),
        'sort': sort_by,
    }
    
    context = {
        'products': products_page,
        'filter_options': filter_options,
        'price_range': price_range,
        'current_filters': current_filters,
        'active_filters': filters,
        'total_products': len(products) if isinstance(products, list) else products.count(),
        'sort_by': sort_by,
        'subcategory': subcategory,
        'category': subcategory.category,
        'is_subcategory_page': True,
    }
    return render(request, 'Ecom/shop.html', context)

def global_search_view(request):
    """Global search across categories, subcategories, products, and variants"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': [], 'count': 0})
    
    results = []
    
    # Search Categories
    categories = Category.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query),
        is_active=True
    )[:5]
    for cat in categories:
        results.append({
            'type': 'category',
            'id': cat.id,
            'name': cat.name,
            'url': f'/shop/category/{cat.slug}/',
            'description': cat.description[:100] if cat.description else '',
        })
    
    # Search Subcategories
    subcategories = SubCategory.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query),
        is_active=True
    )[:5]
    for sub in subcategories:
        results.append({
            'type': 'subcategory',
            'id': sub.id,
            'name': sub.name,
            'category': sub.category.name,
            'url': f'/shop/subcategory/{sub.slug}/',
            'description': sub.description[:100] if sub.description else '',
        })
    
    # Search Products
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(sku__icontains=query) |
        Q(brand__icontains=query) |
        Q(description__icontains=query) |
        Q(short_description__icontains=query),
        is_active=True
    )[:10]
    for product in products:
        results.append({
            'type': 'product',
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': str(product.final_price),
            'image': product.main_image,
            'url': f'/product/{product.id}/',
        })
    
    # Search Variants
    variants = ProductVariant.objects.filter(
        Q(sku__icontains=query) |
        Q(color__icontains=query) |
        Q(size__icontains=query) |
        Q(name__icontains=query),
        is_active=True
    ).select_related('product')[:10]
    for variant in variants:
        if variant.product.is_active:
            results.append({
                'type': 'variant',
                'id': variant.id,
                'name': variant.name or f"{variant.color} {variant.size}".strip(),
                'sku': variant.sku,
                'product_name': variant.product.name,
                'price': str(variant.final_price),
                'image': variant.main_image or variant.product.main_image,
                'url': f'/product/{variant.product.id}/',
            })
    
    return JsonResponse({
        'results': results,
        'count': len(results),
        'query': query,
    })

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction as db_transaction
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .models import (
    Cart, CartItem, Wishlist, WishlistItem, 
    Coupon, Offer, Order, OrderItem, Product, ProductVariant, Transaction
)
from .forms import CouponApplyForm, CheckoutForm
import json
import razorpay
import uuid

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


def get_or_create_cart(request):
    """Get or create cart for user or session"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        # Merge session cart if exists
        if request.session.get('cart_session_id'):
            session_cart = Cart.objects.filter(session_id=request.session['cart_session_id']).first()
            if session_cart and session_cart != cart:
                for item in session_cart.items.all():
                    # Make sure to preserve product and variant
                    cart_item, _ = CartItem.objects.get_or_create(
                        cart=cart,
                        product=item.product,
                        variant=item.variant,
                        defaults={'quantity': item.quantity}
                    )
                    if not _ and cart_item:
                        cart_item.quantity += item.quantity
                        cart_item.save()
                session_cart.delete()
            request.session.pop('cart_session_id', None)
        return cart
    else:
        session_id = request.session.get('cart_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session['cart_session_id'] = session_id
        cart, created = Cart.objects.get_or_create(session_id=session_id)
        return cart


@login_required
def cart_view(request):
    """View cart page with offers applied - Best discount only (product OR offer, not both)"""
    cart = get_or_create_cart(request)
    cart_items = cart.items.select_related('product', 'variant')
    
    offers = Offer.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_to__gte=timezone.now()
    ).order_by('-priority')
    
    coupon_form = CouponApplyForm()
    
    subtotal_without_offers = Decimal('0')
    subtotal_with_offers = Decimal('0')
    total_offer_savings = Decimal('0')
    total_product_discount_savings = Decimal('0')
    items_data = []
    
    for item in cart_items:
        product = item.product
        if not product:
            continue
        
        # Get the item's price
        original_price = Decimal(str(item.original_price))
        product_discounted_price = Decimal(str(item.price))
        quantity = Decimal(str(item.quantity))
        
        # ============================================
        # PASS THE VARIANT TO calculate_offer_discount
        # ============================================
        final_price, offer_name, offer_discount = calculate_offer_discount(
            product, 
            product_discounted_price,
            variant=item.variant  # Pass the variant if it exists
        )
        
        # Calculate product discount amount
        product_discount_amount = original_price - product_discounted_price
        
        # Debug print
        print(f"Item: {item.item_name}")
        print(f"Original Price: {original_price}")
        print(f"Product Discounted Price: {product_discounted_price}")
        print(f"Final Price: {final_price}")
        print(f"Offer Name: {offer_name}")
        print(f"Offer Discount: {offer_discount}")
        print(f"Product Discount Amount: {product_discount_amount}")
        print("---")
        
        # Determine which discount is applied
        has_product_discount = product_discount_amount > 0
        has_offer = offer_name is not None and offer_name != "Product Discount"
        
        # Calculate actual savings
        actual_savings = original_price - final_price
        
        items_data.append({
            'item': item,
            'original_price': original_price,
            'product_discounted_price': product_discounted_price,
            'final_price': final_price,
            'offer_name': offer_name,
            'offer_discount': offer_discount,
            'product_discount_amount': product_discount_amount,
            'has_product_discount': has_product_discount,
            'has_offer': has_offer,
            'actual_savings': actual_savings,
            'item_total': final_price * quantity,
        })
        
        subtotal_without_offers += original_price * quantity
        subtotal_with_offers += final_price * quantity
        
        if has_offer:
            total_offer_savings += offer_discount * quantity
        elif has_product_discount:
            total_product_discount_savings += product_discount_amount * quantity
    
    # Apply coupon
    coupon_discount = Decimal(str(cart.discount_amount)) if cart.discount_amount else Decimal('0')
    total_after_coupon = subtotal_with_offers - coupon_discount
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'items_data': items_data,
        'offers': offers,
        'coupon_form': coupon_form,
        'subtotal_without_offers': subtotal_without_offers,
        'subtotal_with_offers': subtotal_with_offers,
        'total_offer_savings': total_offer_savings,
        'total_product_discount_savings': total_product_discount_savings,
        'coupon_discount': coupon_discount,
        'total': total_after_coupon,
        'total_items': cart.total_items,
    }
    return render(request, 'Ecom/cart.html', context)

def add_to_cart(request):
    """Add product or variant to cart"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            variant_id = data.get('variant_id')
            quantity = int(data.get('quantity', 1))
            
            product = None
            variant = None
            
            # IMPORTANT: Check variant FIRST
            if variant_id:
                variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
                product = variant.product  # Get the product from variant
            elif product_id:
                product = get_object_or_404(Product, id=product_id, is_active=True)
            else:
                return JsonResponse({'success': False, 'error': 'Product ID required'})
            
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False, 
                    'requires_login': True,
                    'message': 'Please login to add items to cart'
                })
            
            # Check stock - use variant stock if variant exists, else product stock
            stock = variant.stock_quantity if variant else product.stock_quantity
            if stock < quantity:
                return JsonResponse({'success': False, 'error': f'Only {stock} items available'})
            
            cart = get_or_create_cart(request)
            
            # Create cart item with BOTH product and variant
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,  # Always set product
                variant=variant,  # Set variant if exists, else None
                defaults={'quantity': quantity}
            )
            
            if not created:
                if cart_item.quantity + quantity > stock:
                    return JsonResponse({'success': False, 'error': f'Only {stock} items available'})
                cart_item.quantity += quantity
                cart_item.save()
            
            if cart.coupon:
                cart.remove_coupon()
            
            # Get the item name for response
            item_name = variant.name if variant and variant.name else product.name
            
            return JsonResponse({
                'success': True,
                'message': f'"{item_name}" added to cart successfully!',
                'cart_count': cart.total_items,
                'item_name': item_name,
                'is_variant': bool(variant)
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def update_cart_item(request):
    """Update cart item quantity"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            quantity = int(data.get('quantity', 1))
            
            cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
            
            if quantity > cart_item.stock_available:
                return JsonResponse({
                    'success': False, 
                    'error': f'Only {cart_item.stock_available} items available'
                })
            
            if quantity <= 0:
                cart_item.delete()
            else:
                cart_item.quantity = quantity
                cart_item.save()
            
            if cart_item.cart.coupon:
                cart_item.cart.remove_coupon()
            
            cart = cart_item.cart
            return JsonResponse({
                'success': True,
                'subtotal': float(cart.subtotal),
                'total': float(cart.total_price),
                'discount': float(cart.discount_amount),
                'cart_count': cart.total_items,
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    if request.method == 'POST':
        try:
            cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
            cart = cart_item.cart
            if cart.coupon:
                cart.remove_coupon()
            cart_item.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Item removed from cart',
                'subtotal': float(cart.subtotal),
                'total': float(cart.total_price),
                'discount': float(cart.discount_amount),
                'cart_count': cart.total_items
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def apply_coupon(request):
    """Apply coupon to cart"""
    if request.method == 'POST':
        form = CouponApplyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            cart = get_or_create_cart(request)
            success, message = cart.apply_coupon(code)
            if success:
                messages.success(request, message)
            else:
                messages.error(request, message)
            return redirect('Ecom:cart')
    return redirect('Ecom:cart')


@login_required
def remove_coupon(request):
    """Remove coupon from cart"""
    if request.method == 'POST':
        cart = get_or_create_cart(request)
        success, message = cart.remove_coupon()
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('Ecom:cart')
    return redirect('Ecom:cart')


@login_required
def get_cart_count(request):
    cart = get_or_create_cart(request)
    return JsonResponse({'count': cart.total_items})


# ============================================
# WISHLIST VIEWS
# ============================================

@login_required
def wishlist_view(request):
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    items = wishlist.items.select_related('product', 'variant')
    context = {
        'wishlist': wishlist,
        'items': items,
        'total_items': wishlist.total_items
    }
    return render(request, 'Ecom/wishlist.html', context)


@login_required
def add_to_wishlist(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            variant_id = data.get('variant_id')
            
            product = get_object_or_404(Product, id=product_id, is_active=True)
            variant = None
            if variant_id:
                variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
            
            wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
            wishlist_item, created = WishlistItem.objects.get_or_create(
                wishlist=wishlist,
                product=product,
                variant=variant
            )
            
            if created:
                message = 'Added to wishlist!'
            else:
                wishlist_item.delete()
                message = 'Removed from wishlist!'
            
            return JsonResponse({
                'success': True,
                'message': message,
                'in_wishlist': created,
                'count': wishlist.total_items
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def remove_from_wishlist(request, item_id):
    if request.method == 'POST':
        try:
            item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
            item.delete()
            return JsonResponse({'success': True, 'message': 'Item removed from wishlist'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def move_to_cart(request, item_id):
    try:
        wishlist_item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
        cart = get_or_create_cart(request)
        
        stock = wishlist_item.variant.stock_quantity if wishlist_item.variant else wishlist_item.product.stock_quantity
        if stock <= 0:
            messages.error(request, 'Item is out of stock')
            return redirect('Ecom:wishlist')
        
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=wishlist_item.product,
            variant=wishlist_item.variant,
            defaults={'quantity': 1}
        )
        
        if not created:
            if cart_item.quantity + 1 <= stock:
                cart_item.quantity += 1
                cart_item.save()
            else:
                messages.error(request, 'Not enough stock available')
                return redirect('Ecom:wishlist')
        
        wishlist_item.delete()
        messages.success(request, f'"{wishlist_item.product.name}" moved to cart!')
        return redirect('Ecom:wishlist')
        
    except Exception as e:
        messages.error(request, str(e))
        return redirect('Ecom:wishlist')


# ============================================
# CHECKOUT & PAYMENT VIEWS WITH TRANSACTIONS
# ============================================

@login_required
def checkout_view(request):
    cart = get_or_create_cart(request)
    
    if cart.total_items == 0:
        messages.warning(request, 'Your cart is empty!')
        return redirect('Ecom:cart')
    
    # Calculate totals with offers
    subtotal_without_offers = Decimal('0')
    subtotal_with_offers = Decimal('0')
    total_offer_savings = Decimal('0')
    total_product_discount = Decimal('0')
    items_data = []
    applied_offer = None
    applied_offer_name = None
    best_offer_discount = Decimal('0')
    
    for item in cart.items.all():
        if item.product:
            original_price = Decimal(str(item.original_price))
            product_discounted_price = Decimal(str(item.price))
            product_discount_amount = original_price - product_discounted_price
            
            # ============================================
            # PASS THE VARIANT TO calculate_offer_discount
            # ============================================
            final_price, offer_name, offer_discount = calculate_offer_discount(
                item.product, 
                product_discounted_price,
                variant=item.variant  # Pass the variant if it exists
            )
            
            # Track the best offer applied
            if offer_discount > 0 and offer_name and offer_name != "Product Discount":
                try:
                    offer_obj = Offer.objects.filter(
                        name=offer_name,
                        is_active=True,
                        valid_from__lte=timezone.now(),
                        valid_to__gte=timezone.now()
                    ).first()
                    if offer_obj:
                        applied_offer = offer_obj
                        applied_offer_name = offer_name
                        if offer_discount > best_offer_discount:
                            best_offer_discount = offer_discount
                except Offer.DoesNotExist:
                    pass
            
            # Determine which discount is applied
            has_product_discount = product_discount_amount > 0
            has_offer = offer_name is not None and offer_name != "Product Discount"
            
            # ============================================
            # FIX: Ensure offer discount is correctly applied
            # ============================================
            if has_offer and has_product_discount:
                # Both exist - verify which one is actually applied
                product_final_price = original_price - product_discount_amount
                offer_final_price = original_price - offer_discount
                
                if offer_final_price < product_final_price:
                    # Offer is better - it should be applied
                    final_price = offer_final_price
                    has_product_discount = False
                else:
                    # Product discount is better - it should be applied
                    final_price = product_final_price
                    has_offer = False
            
            # Calculate actual savings
            actual_savings = original_price - final_price
            
            items_data.append({
                'item': item,
                'original_price': original_price,
                'product_discounted_price': product_discounted_price,
                'final_price': final_price,
                'offer_name': offer_name if has_offer else None,
                'offer_discount': offer_discount if has_offer else Decimal('0'),
                'product_discount_amount': product_discount_amount if has_product_discount else Decimal('0'),
                'has_product_discount': has_product_discount,
                'has_offer': has_offer,
                'actual_savings': actual_savings,
                'item_total': final_price * Decimal(str(item.quantity)),
            })
            
            subtotal_without_offers += original_price * Decimal(str(item.quantity))
            subtotal_with_offers += final_price * Decimal(str(item.quantity))
            
            if has_offer:
                total_offer_savings += offer_discount * Decimal(str(item.quantity))
            elif has_product_discount:
                total_product_discount += product_discount_amount * Decimal(str(item.quantity))
        else:
            # Fallback for items without product
            items_data.append({
                'item': item,
                'original_price': Decimal(str(item.price)),
                'product_discounted_price': Decimal(str(item.price)),
                'final_price': Decimal(str(item.price)),
                'offer_name': None,
                'offer_discount': Decimal('0'),
                'product_discount_amount': Decimal('0'),
                'has_product_discount': False,
                'has_offer': False,
                'actual_savings': Decimal('0'),
                'item_total': Decimal(str(item.price)) * Decimal(str(item.quantity)),
            })
            subtotal_without_offers += Decimal(str(item.price)) * Decimal(str(item.quantity))
            subtotal_with_offers += Decimal(str(item.price)) * Decimal(str(item.quantity))
    
    total_after_coupon = subtotal_with_offers - Decimal(str(cart.discount_amount))
    
    # Get user's addresses
    addresses = request.user.addresses.filter(is_active=True) if hasattr(request.user, 'addresses') else []
    
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        new_address = request.POST.get('new_address')
        
        # Determine shipping address
        if address_id:
            try:
                address = Address.objects.get(id=address_id, user=request.user)
                shipping_address = f"{address.full_name}\n{address.address_line1}\n{address.address_line2}\n{address.city}, {address.state} - {address.pincode}\n{address.country}\nPhone: {address.phone}"
            except Address.DoesNotExist:
                messages.error(request, 'Selected address not found!')
                return redirect('Ecom:checkout')
        elif new_address:
            shipping_address = new_address
        else:
            messages.error(request, 'Please select or enter an address.')
            return redirect('Ecom:checkout')
        
        billing_address = request.POST.get('billing_address', shipping_address)
        notes = request.POST.get('notes', '')
        
        with db_transaction.atomic():
            razorpay_order = razorpay_client.order.create({
                'amount': int(total_after_coupon * 100),
                'currency': 'INR',
                'payment_capture': '1',
                'notes': {
                    'user_email': request.user.email,
                    'order_type': 'ecommerce'
                }
            })
            
            # Create order with complete discount breakdown
            order = Order.objects.create(
                user=request.user,
                razorpay_order_id=razorpay_order['id'],
                subtotal=subtotal_without_offers,
                product_discount_total=total_product_discount,
                offer_discount=total_offer_savings,
                coupon_discount=Decimal(str(cart.discount_amount)),
                coupon=cart.coupon,
                offer=applied_offer,
                total_amount=total_after_coupon,
                shipping_address=shipping_address,
                billing_address=billing_address or shipping_address,
                notes=notes,
                status='pending',
                payment_status='pending'
            )
            
            # Create order items with complete discount breakdown
            for item_data in items_data:
                item = item_data['item']
                
                # Find the offer object for this item
                offer_obj = None
                if item_data['offer_name'] and item_data['offer_name'] != "Product Discount":
                    try:
                        offer_obj = Offer.objects.filter(
                            name=item_data['offer_name'],
                            is_active=True,
                            valid_from__lte=timezone.now(),
                            valid_to__gte=timezone.now()
                        ).first()
                    except Offer.DoesNotExist:
                        pass
                
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    product_name=item.item_name,
                    sku=item.item_sku,
                    quantity=item.quantity,
                    original_price=item_data['original_price'],
                    product_discounted_price=item_data['product_discounted_price'],
                    offer_discounted_price=item_data['final_price'],
                    final_price=item_data['final_price'],
                    total=item_data['item_total'],
                    product_discount=item_data['product_discount_amount'],
                    offer_discount=item_data['offer_discount'],
                    offer=offer_obj,
                    offer_name=item_data['offer_name'] or '',
                )
            
            Transaction.objects.create(
                order=order,
                transaction_type='payment',
                razorpay_transaction_id=razorpay_order['id'],
                amount=total_after_coupon,
                status='pending',
                response_data=razorpay_order,
                notes='Payment initiated'
            )
            
            context = {
                'order': order,
                'razorpay_key': settings.RAZORPAY_KEY_ID,
                'amount': int(total_after_coupon * 100),
                'currency': 'INR',
            }
            return render(request, 'Ecom/payment.html', context)
    else:
        form = CheckoutForm()
    
    context = {
        'cart': cart,
        'cart_items': cart.items.all(),
        'items_data': items_data,
        'subtotal': cart.subtotal,
        'subtotal_without_offers': subtotal_without_offers,
        'subtotal_with_offers': subtotal_with_offers,
        'product_discount_savings': total_product_discount,
        'offer_savings': total_offer_savings,
        'coupon_discount': Decimal(str(cart.discount_amount)),
        'total': total_after_coupon,
        'addresses': addresses,
        'total_items': cart.total_items,
        'form': form,
    }
    return render(request, 'Ecom/checkout.html', context)

@login_required
@csrf_exempt
def payment_success(request):
    """Handle successful payment with transaction tracking and refund on order failure"""
    if request.method == 'POST':
        razorpay_order_id = request.POST.get('razorpay_order_id')
        razorpay_payment_id = request.POST.get('razorpay_payment_id')
        razorpay_signature = request.POST.get('razorpay_signature')
        
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            messages.error(request, f'Payment verification failed: {str(e)}')
            return redirect('Ecom:cart')
        
        try:
            order = Order.objects.get(razorpay_order_id=razorpay_order_id, user=request.user)
        except Order.DoesNotExist:
            messages.error(request, 'Order not found! Please contact support.')
            return redirect('Ecom:cart')
        
        # Get the transaction record
        transaction_record = Transaction.objects.filter(
            order=order,
            razorpay_transaction_id=razorpay_order_id,
            transaction_type='payment'
        ).first()
        
        # Check if already processed
        if order.payment_status == 'paid':
            messages.success(request, f'Order #{order.order_number} already confirmed!')
            return redirect('Ecom:order_success', order_id=order.id)
        
        # ============================================
        # TRY TO PLACE ORDER
        # ============================================
        try:
            with db_transaction.atomic():
                # Update order
                order.razorpay_payment_id = razorpay_payment_id
                order.razorpay_signature = razorpay_signature
                order.payment_status = 'paid'
                order.status = 'processing'
                order.save()
                
                # Update transaction
                if transaction_record:
                    transaction_record.razorpay_payment_id = razorpay_payment_id
                    transaction_record.status = 'success'
                    transaction_record.response_data = {
                        'payment_id': razorpay_payment_id,
                        'signature': razorpay_signature,
                        'status': 'success'
                    }
                    transaction_record.save()
                
                # ============================================
                # UPDATE STOCK FOR PRODUCTS AND VARIANTS
                # ============================================
                for item in order.items.all():
                    if item.variant:
                        # Update variant stock
                        variant = ProductVariant.objects.get(id=item.variant.id)
                        variant.stock_quantity -= item.quantity
                        variant.save()
                        
                        # Also update parent product stock
                        if variant.product:
                            variant.product.stock_quantity -= item.quantity
                            variant.product.save()
                    elif item.product:
                        # Update product stock
                        product = Product.objects.get(id=item.product.id)
                        product.stock_quantity -= item.quantity
                        product.save()
                
                # Clear cart
                cart = get_or_create_cart(request)
                cart.items.all().delete()
                if cart.coupon:
                    cart.coupon = None
                cart.discount_amount = 0
                cart.save()
                
                # Update coupon usage
                if order.coupon:
                    order.coupon.used_count += 1
                    order.coupon.save()
                
                messages.success(request, f'Payment successful! Order #{order.order_number} confirmed.')
                return redirect('Ecom:order_success', order_id=order.id)
                
        except Exception as e:
            # ============================================
            # ORDER PLACEMENT FAILED - INITIATE REFUND
            # ============================================
            try:
                # Initiate refund with Razorpay
                refund = razorpay_client.payment.refund(razorpay_payment_id, {
                    'amount': int(order.total_amount * 100),
                    'speed': 'normal',
                    'notes': {
                        'reason': 'Order placement failed after successful payment',
                        'order_id': order.order_number,
                        'user_email': request.user.email
                    }
                })
                
                # Update order
                order.payment_status = 'refunded'
                order.status = 'failed'
                order.save()
                
                # Update transaction
                if transaction_record:
                    transaction_record.status = 'refunded'
                    transaction_record.razorpay_refund_id = refund['id']
                    transaction_record.response_data = {
                        'refund_id': refund['id'],
                        'refund_status': refund['status'],
                        'reason': 'Order placement failed'
                    }
                    transaction_record.save()
                
                # Create Refund Transaction Record
                Transaction.objects.create(
                    order=order,
                    transaction_type='refund',
                    razorpay_transaction_id=refund['id'],
                    razorpay_payment_id=razorpay_payment_id,
                    razorpay_refund_id=refund['id'],
                    amount=order.total_amount,
                    status='success',
                    response_data=refund,
                    notes=f'Refund initiated due to order placement failure. Payment ID: {razorpay_payment_id}'
                )
                
                messages.error(request, 
                    f'Order placement failed! Your payment of ₹{order.total_amount} has been refunded. '
                    'Please try again or contact support.'
                )
                return redirect('Ecom:cart')
                
            except Exception as refund_error:
                # ============================================
                # REFUND ALSO FAILED - CRITICAL ERROR
                # ============================================
                order.status = 'failed'
                order.save()
                
                if transaction_record:
                    transaction_record.status = 'failed'
                    transaction_record.response_data = {
                        'error': str(refund_error),
                        'payment_id': razorpay_payment_id,
                        'refund_failed': True
                    }
                    transaction_record.save()
                
                Transaction.objects.create(
                    order=order,
                    transaction_type='refund',
                    razorpay_payment_id=razorpay_payment_id,
                    amount=order.total_amount,
                    status='failed',
                    response_data={'error': str(refund_error)},
                    notes=f'Refund FAILED! Payment captured but order failed. Payment ID: {razorpay_payment_id}'
                )
                
                messages.error(request, 
                    'Order placement failed AND refund failed! Please contact support immediately. '
                    'Your payment has been captured but we could not process your order.'
                )
                return redirect('Ecom:cart')
    
    # If GET request, redirect to orders
    return redirect('Ecom:orders')


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'Ecom/order_success.html', {'order': order})


@login_required
def orders_view(request):
    """View orders - Admin sees all, Customers see only their orders"""
    if request.user.is_admin or request.user.is_superuser:
        orders = Order.objects.all().order_by('-created_at')
    else:
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'Ecom/orders.html', {'orders': orders})


@login_required
def order_detail_view(request, order_id):
    """View order details - Admin can view any, Customers only their own"""
    if request.user.is_admin or request.user.is_superuser:
        order = get_object_or_404(Order, id=order_id)
    else:
        order = get_object_or_404(Order, id=order_id, user=request.user)
    
    transactions = order.transactions.all()
    context = {
        'order': order,
        'transactions': transactions,
        'is_admin_view': request.user.is_admin or request.user.is_superuser,
    }
    return render(request, 'Ecom/order_detail.html', context)

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Address

@login_required
def add_address_ajax(request):
    """Add new address via AJAX"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        
        try:
            address = Address.objects.create(
                user=request.user,
                full_name=data.get('full_name'),
                phone=data.get('phone'),
                address_line1=data.get('address_line1'),
                address_line2=data.get('address_line2', ''),
                landmark=data.get('landmark', ''),
                city=data.get('city'),
                state=data.get('state'),
                pincode=data.get('pincode'),
                country=data.get('country', 'India'),
                address_type=data.get('address_type', 'shipping'),
                is_default=data.get('is_default', False)
            )
            
            return JsonResponse({
                'success': True,
                'address_id': address.id,
                'message': 'Address added successfully'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# ============================================
# COUPON MANAGEMENT VIEWS
# ============================================

@login_required
def coupon_list_view(request):
    """List all coupons - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    coupons = Coupon.objects.all().order_by('-created_at')
    
    # Calculate stats
    active_count = coupons.filter(is_active=True).count()
    inactive_count = coupons.filter(is_active=False).count()
    expired_count = coupons.filter(valid_to__lt=timezone.now()).count()
    
    context = {
        'coupons': coupons,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'expired_count': expired_count,
        'total_count': coupons.count(),
    }
    return render(request, 'Ecom/admin/coupon_list.html', context)


@login_required
def coupon_create_view(request):
    """Create a new coupon - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    if request.method == 'POST':
        form = CouponForm(request.POST, request.FILES)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.code = coupon.code.upper().strip()
            coupon.save()
            messages.success(request, f'Coupon "{coupon.code}" created successfully!')
            return redirect('Ecom:coupon_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CouponForm()
    
    return render(request, 'Ecom/admin/coupon_form.html', {
        'form': form,
        'action': 'Create',
        'coupon': None
    })


@login_required
def coupon_edit_view(request, coupon_id):
    """Edit an existing coupon - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        form = CouponForm(request.POST, request.FILES, instance=coupon)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.code = coupon.code.upper().strip()
            coupon.save()
            messages.success(request, f'Coupon "{coupon.code}" updated successfully!')
            return redirect('Ecom:coupon_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CouponForm(instance=coupon)
    
    return render(request, 'Ecom/admin/coupon_form.html', {
        'form': form,
        'action': 'Edit',
        'coupon': coupon
    })


@login_required
def coupon_delete_view(request, coupon_id):
    """Delete a coupon - Admin only (with modal confirmation)"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    coupon = get_object_or_404(Coupon, id=coupon_id)
    
    if request.method == 'POST':
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Coupon "{code}" deleted successfully!')
        return redirect('Ecom:coupon_list')
    
    # GET request - redirect to list (modal handles confirmation)
    return redirect('Ecom:coupon_list')


@login_required
def coupon_toggle_status_view(request, coupon_id):
    """Toggle coupon active status - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    coupon = get_object_or_404(Coupon, id=coupon_id)
    coupon.is_active = not coupon.is_active
    coupon.save()
    
    status = 'activated' if coupon.is_active else 'deactivated'
    messages.success(request, f'Coupon "{coupon.code}" {status} successfully!')
    return redirect('Ecom:coupon_list')


# ============================================
# OFFER MANAGEMENT VIEWS
# ============================================

@login_required
def offer_list_view(request):
    """List all offers - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    offers = Offer.objects.all().order_by('-priority', '-created_at')
    
    active_count = offers.filter(is_active=True).count()
    inactive_count = offers.filter(is_active=False).count()
    
    context = {
        'offers': offers,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_count': offers.count(),
    }
    return render(request, 'Ecom/admin/offer_list.html', context)


@login_required
def offer_create_view(request):
    """Create a new offer - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    if request.method == 'POST':
        form = OfferForm(request.POST, request.FILES)
        if form.is_valid():
            offer = form.save()
            messages.success(request, f'Offer "{offer.name}" created successfully!')
            return redirect('Ecom:offer_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = OfferForm()
    
    return render(request, 'Ecom/admin/offer_form.html', {
        'form': form,
        'action': 'Create',
        'offer': None
    })


@login_required
def offer_edit_view(request, offer_id):
    """Edit an existing offer - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    offer = get_object_or_404(Offer, id=offer_id)
    
    if request.method == 'POST':
        form = OfferForm(request.POST, request.FILES, instance=offer)
        if form.is_valid():
            offer = form.save()
            messages.success(request, f'Offer "{offer.name}" updated successfully!')
            return redirect('Ecom:offer_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = OfferForm(instance=offer)
    
    return render(request, 'Ecom/admin/offer_form.html', {
        'form': form,
        'action': 'Edit',
        'offer': offer
    })


@login_required
def offer_delete_view(request, offer_id):
    """Delete an offer - Admin only (with modal confirmation)"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    offer = get_object_or_404(Offer, id=offer_id)
    
    if request.method == 'POST':
        name = offer.name
        offer.delete()
        messages.success(request, f'Offer "{name}" deleted successfully!')
        return redirect('Ecom:offer_list')
    
    return redirect('Ecom:offer_list')


@login_required
def offer_toggle_status_view(request, offer_id):
    """Toggle offer active status - Admin only"""
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    offer = get_object_or_404(Offer, id=offer_id)
    offer.is_active = not offer.is_active
    offer.save()
    
    status = 'activated' if offer.is_active else 'deactivated'
    messages.success(request, f'Offer "{offer.name}" {status} successfully!')
    return redirect('Ecom:offer_list')

from decimal import Decimal
from django.utils import timezone
from .models import Offer

def calculate_offer_discount(product, price, variant=None):
    """
    Calculate if any offer applies to this product or variant
    Rules:
    1. Compare product discount vs offer discount on the ORIGINAL price
    2. Apply the BEST discount (higher discount amount)
    3. Do NOT stack discounts
    
    Returns: (final_price, offer_name, discount_amount)
    """
    # Get all active offers
    offers = Offer.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_to__gte=timezone.now()
    ).order_by('-priority')
    
    best_offer_discount = Decimal('0')
    best_offer_name = None
    
    # Get original price - THIS SHOULD BE THE VARIANT'S PRICE IF VARIANT EXISTS
    original_price = Decimal(str(product.price))
    
    # If variant exists, use variant's original price
    if variant:
        original_price = Decimal(str(variant.price))
    
    # Convert price to Decimal (this is already product-discounted price from CartItem)
    if not isinstance(price, Decimal):
        price = Decimal(str(price))
    
    # Calculate product discount amount on the correct price
    product_discount_amount = original_price - price
    
    # ============================================
    # 1. FIND THE BEST OFFER DISCOUNT
    #    Calculate offer on the ITEM's price
    # ============================================
    for offer in offers:
        discount_value = Decimal(str(offer.discount_value))
        
        if offer.offer_type == 'product':
            # Check if offer is on the product
            if offer.product and offer.product.id == product.id:
                if offer.discount_type == 'percentage':
                    # Calculate on the item's price
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
            if product.category and offer.category and offer.category.id == product.category.id:
                if offer.discount_type == 'percentage':
                    # Calculate on the item's price
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
    
    # ============================================
    # 2. APPLY THE BEST DISCOUNT ON ORIGINAL PRICE
    # ============================================
    
    # Debug prints
    print(f"Product: {product.name}")
    if variant:
        print(f"Variant: {variant.name or variant.sku}")
    print(f"Original Price (item): {original_price}")
    print(f"Product Discount Amount: {product_discount_amount}")
    print(f"Best Offer Discount: {best_offer_discount}")
    print(f"Best Offer Name: {best_offer_name}")
    
    # Case 1: No product discount, no offer
    if product_discount_amount == 0 and best_offer_discount == 0:
        return price, None, Decimal('0')
    
    # Case 2: Only product discount exists (no offer)
    if product_discount_amount > 0 and best_offer_discount == 0:
        return price, "Product Discount", Decimal('0')
    
    # Case 3: Only offer exists (no product discount)
    if product_discount_amount == 0 and best_offer_discount > 0:
        final_price = original_price - best_offer_discount
        print(f"Only Offer: Final Price = {final_price}")
        return final_price, best_offer_name, best_offer_discount
    
    # Case 4: Both exist - apply the better one on ORIGINAL price
    if product_discount_amount > 0 and best_offer_discount > 0:
        product_final_price = original_price - product_discount_amount
        offer_final_price = original_price - best_offer_discount
        
        print(f"Both Exist - Product Final: {product_final_price}, Offer Final: {offer_final_price}")
        
        if offer_final_price < product_final_price:
            # Offer gives better discount
            print(f"Offer is better: {best_offer_name}")
            return offer_final_price, best_offer_name, best_offer_discount
        else:
            # Product discount gives better discount
            print("Product discount is better")
            return product_final_price, "Product Discount", Decimal('0')
    
    # Fallback
    return price, None, Decimal('0')