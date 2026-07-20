from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from .models import User, Profile, Address, OTP
from .forms import *
from .utils import create_and_send_otp, verify_otp, delete_file_if_exists, get_user_by_identifier
from decimal import Decimal


from django.db.models import Q, Count, Avg, F, DecimalField
from django.db.models.functions import Coalesce

# utils.py or add to views.py

from .models import Coupon, Offer
from django.utils import timezone

def get_active_coupons(limit=4):
    """Get active coupons for homepage display"""
    now = timezone.now()
    return Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(
        usage_limit__isnull=False,
        used_count__gte=models.F('usage_limit')
    ).order_by('-created_at')[:limit]


def get_active_offers(limit=4):
    """Get active offers for homepage display"""
    now = timezone.now()
    return Offer.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).order_by('-priority', '-created_at')[:limit]


def get_featured_offers(limit=2):
    """Get featured offers (highest discount) for homepage"""
    now = timezone.now()
    return Offer.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(
        banner_image__isnull=True
    ).exclude(
        banner_image=''
    ).order_by('-discount_value', '-priority')[:limit]

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
    # BANNERS
    # ============================================
    banners = Banner.objects.filter(is_active=True).order_by('-created_at')[:5]
    
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
    deals_of_the_day_query = products.filter(
        discount_percentage__gt=0
    ).order_by('-discount_percentage')[:6]
    
    # If less than 6 products with discount, get some without discount to fill
    if deals_of_the_day_query.count() < 6:
        # Get the IDs of products already in deals
        existing_ids = list(deals_of_the_day_query.values_list('id', flat=True))
        
        # Get additional products excluding the ones already in deals
        additional_products = products.exclude(
            id__in=existing_ids
        ).order_by('-created_at')[:6 - deals_of_the_day_query.count()]
        
        # Combine querysets
        deals_of_the_day = list(deals_of_the_day_query) + list(additional_products)
    else:
        deals_of_the_day = list(deals_of_the_day_query)
    
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
    # COUPONS
    # ============================================
    now = timezone.now()
    coupons = Coupon.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(
        usage_limit__isnull=False,
        used_count__gte=models.F('usage_limit')
    ).order_by('-created_at')[:6]
    
    # ============================================
    # OFFERS (With Banner Images)
    # ============================================
    offers = Offer.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now
    ).exclude(
        banner_image__isnull=True
    ).exclude(
        banner_image=''
    ).order_by('-priority', '-created_at')[:6]
    
    # ============================================
    # FEATURED OFFERS (with images and high discount)
    # ============================================
    # Get offers with discount > 0
    featured_offers_query = Offer.objects.filter(
        is_active=True,
        valid_from__lte=now,
        valid_to__gte=now,
        discount_value__gt=0
    ).exclude(
        banner_image__isnull=True
    ).exclude(
        banner_image=''
    ).order_by('-discount_value', '-priority')[:5]
    
    featured_offers = list(featured_offers_query)
    
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
        'banners': banners,
        'coupons': coupons,
        'offers': offers,
        'featured_offers': featured_offers,
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
# views.py - Complete admin_dashboard_view with all analytics

from django.db.models import Sum, Count, Avg, Q, F, Max, Min
from django.db.models.functions import TruncMonth, TruncDay, TruncWeek, ExtractHour
from datetime import datetime, timedelta
import calendar
from decimal import Decimal

@login_required
def admin_dashboard_view(request):
    if not request.user.is_admin:
        messages.error(request, 'Access denied. Admin only.')
        return redirect('Ecom:home')
    
    # ============================================
    # GET FILTER PARAMETERS
    # ============================================
    filter_type = request.GET.get('filter_type', 'month')
    selected_month = request.GET.get('selected_month', '')
    selected_date = request.GET.get('selected_date', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # ============================================
    # DATE FILTER FUNCTION
    # ============================================
    def get_date_range():
        """Get the date range based on filter parameters"""
        if filter_type == 'month' and selected_month:
            try:
                year, month = selected_month.split('-')
                year, month = int(year), int(month)
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month + 1, 1)
                return start_date, end_date
            except (ValueError, IndexError):
                return None, None
        
        elif filter_type == 'date' and selected_date:
            try:
                date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
                start_date = date_obj
                end_date = date_obj + timedelta(days=1)
                return start_date, end_date
            except ValueError:
                return None, None
        
        elif filter_type == 'custom' and date_from and date_to:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                return from_date, to_date
            except ValueError:
                return None, None
        
        return None, None
    
    def apply_date_filter(queryset, date_field='created_at'):
        """Apply date filters to a queryset"""
        start_date, end_date = get_date_range()
        if start_date and end_date:
            return queryset.filter(**{f'{date_field}__gte': start_date, f'{date_field}__lt': end_date})
        return queryset
    
    # ============================================
    # BASE QUERYSETS WITH FILTERS APPLIED
    # ============================================
    # Online Orders (excluding pending payments)
    online_orders = Order.objects.exclude(payment_status='pending').exclude(status='failed')
    all_online_orders = Order.objects.all()
    
    # Offline Orders
    offline_orders = OfflineOrder.objects.exclude(payment_status='pending').exclude(status='cancelled')
    all_offline_orders = OfflineOrder.objects.all()
    
    # Apply date filters to all querysets
    online_orders = apply_date_filter(online_orders)
    all_online_orders = apply_date_filter(all_online_orders)
    offline_orders = apply_date_filter(offline_orders)
    all_offline_orders = apply_date_filter(all_offline_orders)
    
    # ============================================
    # ONLINE ORDER STATISTICS
    # ============================================
    total_online_orders = online_orders.count()
    total_online_revenue = online_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    avg_online_order_value = online_orders.aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0')
    
    online_status_counts = {
        'pending': all_online_orders.filter(status='pending').count(),
        'processing': online_orders.filter(status='processing').count(),
        'shipped': online_orders.filter(status='shipped').count(),
        'delivered': online_orders.filter(status='delivered').count(),
        'cancelled': online_orders.filter(status='cancelled').count(),
        'failed': all_online_orders.filter(status='failed').count(),
    }
    
    online_payment_counts = {
        'pending': all_online_orders.filter(payment_status='pending').count(),
        'paid': online_orders.filter(payment_status='paid').count(),
        'refunded': online_orders.filter(payment_status='refunded').count(),
        'failed': all_online_orders.filter(payment_status='failed').count(),
    }
    
    # ============================================
    # OFFLINE ORDER STATISTICS
    # ============================================
    total_offline_orders = offline_orders.count()
    total_offline_revenue = offline_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    avg_offline_order_value = offline_orders.aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0')
    
    offline_status_counts = {
        'pending': all_offline_orders.filter(status='pending').count(),
        'processing': all_offline_orders.filter(status='processing').count(),
        'completed': offline_orders.filter(status='completed').count(),
        'cancelled': all_offline_orders.filter(status='cancelled').count(),
    }
    
    offline_payment_counts = {
        'cash': offline_orders.filter(payment_method='cash', payment_status='paid').count(),
        'card': offline_orders.filter(payment_method='card', payment_status='paid').count(),
        'online': offline_orders.filter(payment_method='online', payment_status='paid').count(),
        'upi': offline_orders.filter(payment_method='upi', payment_status='paid').count(),
        'pending': all_offline_orders.filter(payment_status='pending').count(),
        'failed': all_offline_orders.filter(payment_status='failed').count(),
        'refunded': all_offline_orders.filter(payment_status='refunded').count(),
    }
    
    # ============================================
    # COMBINED STATISTICS
    # ============================================
    total_orders = total_online_orders + total_offline_orders
    total_revenue = total_online_revenue + total_offline_revenue
    
    if total_orders > 0:
        avg_order_value = total_revenue / total_orders
    else:
        avg_order_value = Decimal('0')
    
    # ============================================
    # BARCODE STATISTICS
    # ============================================
    total_barcodes = ProductBarcode.objects.count()
    product_barcodes = ProductBarcode.objects.filter(barcode_type='product').count()
    variant_barcodes = ProductBarcode.objects.filter(barcode_type='variant').count()
    
    # ============================================
    # OFFLINE CUSTOMER ANALYTICS
    # ============================================
    total_offline_customers = OfflineCustomer.objects.filter(is_active=True).count()
    inactive_offline_customers = OfflineCustomer.objects.filter(is_active=False).count()
    
    offline_customer_revenue = OfflineCustomer.objects.filter(
        is_active=True
    ).annotate(
        total_spent=Coalesce(
            Sum('orders__total_amount'), 
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        order_count=Count('orders')
    ).order_by('-total_spent')[:10]
    
    offline_customer_order_counts = OfflineCustomer.objects.filter(
        is_active=True
    ).annotate(
        order_count=Count('orders'),
        total_spent=Coalesce(
            Sum('orders__total_amount'), 
            Value(Decimal('0.00'), output_field=DecimalField())
        )
    ).filter(order_count__gt=0).order_by('-order_count')[:10]
    
    # Offline Customer Registration Trend
    offline_customer_trend = OfflineCustomer.objects.filter(
        created_at__gte=datetime.now() - timedelta(days=180)
    )
    offline_customer_trend = apply_date_filter(offline_customer_trend)
    offline_customer_trend = offline_customer_trend.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    # ============================================
    # OFFLINE SALES ANALYTICS
    # ============================================
    offline_revenue_over_time = OfflineOrder.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='cancelled'
    )
    offline_revenue_over_time = apply_date_filter(offline_revenue_over_time)
    offline_revenue_over_time = offline_revenue_over_time.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('month')[:12]
    
    # Combined Revenue Over Time
    combined_revenue_over_time = []
    
    online_monthly = Order.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='failed'
    )
    online_monthly = apply_date_filter(online_monthly)
    online_monthly = online_monthly.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        online_revenue=Sum('total_amount'),
        online_orders=Count('id')
    ).order_by('month')[:12]
    
    offline_monthly = OfflineOrder.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='cancelled'
    )
    offline_monthly = apply_date_filter(offline_monthly)
    offline_monthly = offline_monthly.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        offline_revenue=Sum('total_amount'),
        offline_orders=Count('id')
    ).order_by('month')[:12]
    
    combined_dict = {}
    for item in online_monthly:
        month_key = item['month'].strftime('%Y-%m') if item['month'] else None
        if month_key:
            combined_dict[month_key] = {
                'month': item['month'],
                'online_revenue': item['online_revenue'] or 0,
                'online_orders': item['online_orders'] or 0,
                'offline_revenue': 0,
                'offline_orders': 0
            }
    
    for item in offline_monthly:
        month_key = item['month'].strftime('%Y-%m') if item['month'] else None
        if month_key:
            if month_key in combined_dict:
                combined_dict[month_key]['offline_revenue'] = item['offline_revenue'] or 0
                combined_dict[month_key]['offline_orders'] = item['offline_orders'] or 0
            else:
                combined_dict[month_key] = {
                    'month': item['month'],
                    'online_revenue': 0,
                    'online_orders': 0,
                    'offline_revenue': item['offline_revenue'] or 0,
                    'offline_orders': item['offline_orders'] or 0
                }
    
    combined_revenue_over_time = sorted(combined_dict.values(), key=lambda x: x['month'])[:12]
    
    offline_payment_methods = OfflineOrder.objects.filter(
        payment_status='paid'
    )
    offline_payment_methods = apply_date_filter(offline_payment_methods)
    offline_payment_methods = offline_payment_methods.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('total_amount')
    ).order_by('-total')
    
    offline_daily_revenue = OfflineOrder.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='cancelled'
    ).filter(
        created_at__month=datetime.now().month,
        created_at__year=datetime.now().year
    )
    offline_daily_revenue = apply_date_filter(offline_daily_revenue)
    offline_daily_revenue = offline_daily_revenue.annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('day')
    
    # ============================================
    # STORE SETTINGS
    # ============================================
    try:
        store_settings = StoreSettings.objects.first()
    except:
        store_settings = None
    
    # ============================================
    # ANALYTICS DASHBOARD - Online
    # ============================================
    online_revenue_over_time = Order.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='failed'
    )
    online_revenue_over_time = apply_date_filter(online_revenue_over_time)
    online_revenue_over_time = online_revenue_over_time.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('month')[:12]
    
    online_daily_revenue = Order.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='failed'
    ).filter(
        created_at__month=datetime.now().month,
        created_at__year=datetime.now().year
    )
    online_daily_revenue = apply_date_filter(online_daily_revenue)
    online_daily_revenue = online_daily_revenue.annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        total=Sum('total_amount'),
        count=Count('id')
    ).order_by('day')
    
    # Hourly Sales Distribution - Online
    online_hourly_sales = []
    try:
        today_orders = Order.objects.exclude(
            payment_status='pending'
        ).exclude(
            status='failed'
        ).filter(
            created_at__date=datetime.now().date()
        )
        today_orders = apply_date_filter(today_orders)
        
        hourly_counts = {}
        hourly_revenues = {}
        for order in today_orders:
            hour = order.created_at.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            hourly_revenues[hour] = hourly_revenues.get(hour, 0) + float(order.total_amount)
        
        for hour in range(24):
            online_hourly_sales.append({
                'hour': hour,
                'count': hourly_counts.get(hour, 0),
                'total': hourly_revenues.get(hour, 0)
            })
    except Exception:
        online_hourly_sales = []
    
    # Top Selling Products - Online
    online_top_products = OrderItem.objects.filter(
        order__in=online_orders
    ).values(
        'product_id', 'product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total')
    ).order_by('-total_quantity')[:10]
    
    online_top_products_by_revenue = OrderItem.objects.filter(
        order__in=online_orders
    ).values(
        'product_id', 'product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total')
    ).order_by('-total_revenue')[:10]
    
    online_category_performance = OrderItem.objects.filter(
        order__in=online_orders,
        product__category__isnull=False
    ).values(
        'product__category__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total'),
        order_count=Count('order', distinct=True)
    ).order_by('-total_revenue')[:10]
    
    # ============================================
    # OFFLINE TOP PRODUCTS
    # ============================================
    offline_top_products = OfflineOrderItem.objects.filter(
        order__in=offline_orders
    ).values(
        'product_id', 'product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total')
    ).order_by('-total_quantity')[:10]
    
    offline_top_products_by_revenue = OfflineOrderItem.objects.filter(
        order__in=offline_orders
    ).values(
        'product_id', 'product_name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total')
    ).order_by('-total_revenue')[:10]
    
    # ============================================
    # USER ANALYTICS - Only Customer and Superuser
    # ============================================
    total_customers = User.objects.filter(Q(role='customer') | Q(is_superuser=True)).count()
    total_admins = User.objects.filter(is_staff=True, is_superuser=False).count()
    total_superusers = User.objects.filter(is_superuser=True).count()
    total_users = User.objects.filter(Q(role='customer') | Q(is_superuser=True)).count()
    
    new_users_queryset = User.objects.filter(Q(role='customer') | Q(is_superuser=True))
    new_users_queryset = apply_date_filter(new_users_queryset)
    new_users_last_30_days = new_users_queryset.count()
    
    most_active_users = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True),
        orders__in=online_orders
    ).annotate(
        order_count=Count('orders'),
        total_spent=Sum('orders__total_amount'),
        last_order=Max('orders__created_at')
    ).filter(
        order_count__gt=0
    ).order_by('-order_count')[:10]
    
    top_users_by_orders = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True)
    ).annotate(
        order_count=Count('orders'),
        total_spent=Sum('orders__total_amount'),
        avg_spent=Avg('orders__total_amount')
    ).filter(
        order_count__gt=0
    ).order_by('-order_count')[:10]
    
    top_users_by_revenue = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True)
    ).annotate(
        order_count=Count('orders'),
        total_spent=Sum('orders__total_amount')
    ).filter(
        total_spent__gt=0
    ).order_by('-total_spent')[:10]
    
    user_registration_trend = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True),
        created_at__gte=datetime.now() - timedelta(days=180)
    )
    user_registration_trend = apply_date_filter(user_registration_trend)
    user_registration_trend = user_registration_trend.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    user_roles = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True)
    ).values('role').annotate(
        count=Count('id')
    )
    
    active_users_queryset = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True),
        last_login__gte=datetime.now() - timedelta(days=30)
    )
    active_users_last_30_days = active_users_queryset.count()
    
    inactive_users = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True),
        Q(last_login__lt=datetime.now() - timedelta(days=90)) | 
        Q(last_login__isnull=True)
    ).count()
    
    # ============================================
    # REVIEW ANALYTICS - FIXED
    # ============================================
    # Get filtered product IDs from online orders
    filtered_product_ids = OrderItem.objects.filter(
        order__in=online_orders
    ).values_list('product_id', flat=True).distinct()
    
    # Use filtered product IDs if available, otherwise use all
    if filtered_product_ids:
        total_reviews = ProductReview.objects.filter(product_id__in=filtered_product_ids).count()
        approved_reviews = ProductReview.objects.filter(
            product_id__in=filtered_product_ids, 
            is_approved=True
        ).count()
        pending_reviews = ProductReview.objects.filter(
            product_id__in=filtered_product_ids, 
            is_approved=False
        ).count()
        verified_reviews = ProductReview.objects.filter(
            product_id__in=filtered_product_ids, 
            is_verified_purchase=True
        ).count()
        
        avg_rating = ProductReview.objects.filter(
            product_id__in=filtered_product_ids,
            is_approved=True
        ).aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        
        rating_distribution = {
            1: ProductReview.objects.filter(product_id__in=filtered_product_ids, rating=1, is_approved=True).count(),
            2: ProductReview.objects.filter(product_id__in=filtered_product_ids, rating=2, is_approved=True).count(),
            3: ProductReview.objects.filter(product_id__in=filtered_product_ids, rating=3, is_approved=True).count(),
            4: ProductReview.objects.filter(product_id__in=filtered_product_ids, rating=4, is_approved=True).count(),
            5: ProductReview.objects.filter(product_id__in=filtered_product_ids, rating=5, is_approved=True).count(),
        }
        
        most_reviewed_products = Product.objects.filter(
            id__in=filtered_product_ids,
            reviews__is_approved=True
        ).annotate(
            review_count=Count('reviews', filter=Q(reviews__is_approved=True)),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
        ).filter(
            review_count__gt=0
        ).order_by('-review_count')[:10]
        
        highest_rated_products = Product.objects.filter(
            id__in=filtered_product_ids,
            reviews__is_approved=True
        ).annotate(
            review_count=Count('reviews', filter=Q(reviews__is_approved=True)),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
        ).filter(
            review_count__gt=2
        ).order_by('-avg_rating')[:10]
        
        review_trend = ProductReview.objects.filter(
            product_id__in=filtered_product_ids,
            created_at__gte=datetime.now() - timedelta(days=180)
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            avg_rating=Avg('rating')
        ).order_by('month')
        
        recent_reviews = ProductReview.objects.filter(
            product_id__in=filtered_product_ids
        ).select_related(
            'product', 'user'
        ).order_by('-created_at')[:10]
    else:
        # Fallback to all reviews
        total_reviews = ProductReview.objects.count()
        approved_reviews = ProductReview.objects.filter(is_approved=True).count()
        pending_reviews = ProductReview.objects.filter(is_approved=False).count()
        verified_reviews = ProductReview.objects.filter(is_verified_purchase=True).count()
        
        avg_rating = ProductReview.objects.filter(is_approved=True).aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        
        rating_distribution = {
            1: ProductReview.objects.filter(rating=1, is_approved=True).count(),
            2: ProductReview.objects.filter(rating=2, is_approved=True).count(),
            3: ProductReview.objects.filter(rating=3, is_approved=True).count(),
            4: ProductReview.objects.filter(rating=4, is_approved=True).count(),
            5: ProductReview.objects.filter(rating=5, is_approved=True).count(),
        }
        
        most_reviewed_products = Product.objects.annotate(
            review_count=Count('reviews', filter=Q(reviews__is_approved=True)),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
        ).filter(
            review_count__gt=0
        ).order_by('-review_count')[:10]
        
        highest_rated_products = Product.objects.annotate(
            review_count=Count('reviews', filter=Q(reviews__is_approved=True)),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
        ).filter(
            review_count__gt=2
        ).order_by('-avg_rating')[:10]
        
        review_trend = ProductReview.objects.filter(
            created_at__gte=datetime.now() - timedelta(days=180)
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            avg_rating=Avg('rating')
        ).order_by('month')
        
        recent_reviews = ProductReview.objects.select_related(
            'product', 'user'
        ).order_by('-created_at')[:10]
    
    if total_reviews > 0:
        approval_rate = (approved_reviews / total_reviews) * 100
    else:
        approval_rate = 0
    
    if total_reviews > 0:
        satisfaction_score = (avg_rating / 5) * 100
    else:
        satisfaction_score = 0
    
    # ============================================
    # PRODUCT STATISTICS
    # ============================================
    total_products = Product.objects.filter(is_active=True).count()
    total_products_inactive = Product.objects.filter(is_active=False).count()
    featured_products = Product.objects.filter(is_active=True, is_featured=True).count()
    best_seller_products = Product.objects.filter(is_active=True, is_best_seller=True).count()
    new_products = Product.objects.filter(is_active=True, is_new=True).count()
    
    low_stock_products = Product.objects.filter(
        is_active=True,
        stock_quantity__lte=F('low_stock_threshold')
    ).order_by('stock_quantity')[:10]
    
    low_stock_count = low_stock_products.count()
    out_of_stock_count = Product.objects.filter(
        is_active=True,
        stock_quantity=0
    ).count()
    
    category_counts = Category.objects.annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    ).order_by('-product_count')[:10]
    
    # ============================================
    # ORDER ANALYTICS
    # ============================================
    order_value_ranges = {
        '0_500': online_orders.filter(total_amount__lt=500).count(),
        '501_1000': online_orders.filter(total_amount__gte=500, total_amount__lt=1000).count(),
        '1001_5000': online_orders.filter(total_amount__gte=1000, total_amount__lt=5000).count(),
        '5001_10000': online_orders.filter(total_amount__gte=5000, total_amount__lt=10000).count(),
        '10000_plus': online_orders.filter(total_amount__gte=10000).count(),
    }
    
    offline_order_value_ranges = {
        '0_500': offline_orders.filter(total_amount__lt=500).count(),
        '501_1000': offline_orders.filter(total_amount__gte=500, total_amount__lt=1000).count(),
        '1001_5000': offline_orders.filter(total_amount__gte=1000, total_amount__lt=5000).count(),
        '5001_10000': offline_orders.filter(total_amount__gte=5000, total_amount__lt=10000).count(),
        '10000_plus': offline_orders.filter(total_amount__gte=10000).count(),
    }
    
    repeat_customers = User.objects.filter(
        orders__in=online_orders
    ).annotate(
        order_count=Count('orders')
    ).filter(
        order_count__gt=1
    ).count()
    
    one_time_customers = User.objects.filter(
        orders__in=online_orders
    ).annotate(
        order_count=Count('orders')
    ).filter(
        order_count=1
    ).count()
    
    offline_repeat_customers = OfflineCustomer.objects.filter(
        orders__in=offline_orders
    ).annotate(
        order_count=Count('orders')
    ).filter(
        order_count__gt=1
    ).count()
    
    offline_one_time_customers = OfflineCustomer.objects.filter(
        orders__in=offline_orders
    ).annotate(
        order_count=Count('orders')
    ).filter(
        order_count=1
    ).count()
    
    # ============================================
    # CUSTOMER LIFETIME VALUE
    # ============================================
    customer_ltv = User.objects.filter(
        Q(role='customer') | Q(is_superuser=True),
        orders__in=online_orders,
        orders__payment_status='paid'
    ).distinct().annotate(
        total_spent=Sum('orders__total_amount'),
        order_count=Count('orders'),
        avg_order_value=Avg('orders__total_amount')
    ).order_by('-total_spent')[:10]
    
    offline_customer_ltv = OfflineCustomer.objects.filter(
        orders__in=offline_orders,
        orders__payment_status='paid'
    ).distinct().annotate(
        total_spent=Coalesce(
            Sum('orders__total_amount'), 
            Value(Decimal('0.00'), output_field=DecimalField())
        ),
        order_count=Count('orders'),
        avg_order_value=Avg('orders__total_amount')
    ).order_by('-total_spent')[:10]
    
    # ============================================
    # RECENT ORDERS
    # ============================================
    recent_online_orders = online_orders.order_by('-created_at')[:10]
    recent_offline_orders = offline_orders.order_by('-created_at')[:10]
    
    # ============================================
    # MONTH OPTIONS FOR FILTER
    # ============================================
    month_options = []
    for i in range(12):
        month_date = datetime.now() - timedelta(days=30 * i)
        month_options.append({
            'value': month_date.strftime('%Y-%m'),
            'label': month_date.strftime('%B %Y'),
            'selected': selected_month == month_date.strftime('%Y-%m')
        })
    
    # ============================================
    # COMBINED ORDER SUMMARY
    # ============================================
    combined_monthly_summary = []
    
    online_monthly_summary = Order.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='failed'
    )
    online_monthly_summary = apply_date_filter(online_monthly_summary)
    online_monthly_summary = online_monthly_summary.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        online_orders=Count('id'),
        online_revenue=Sum('total_amount')
    ).order_by('-month')[:12]
    
    offline_monthly_summary = OfflineOrder.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='cancelled'
    )
    offline_monthly_summary = apply_date_filter(offline_monthly_summary)
    offline_monthly_summary = offline_monthly_summary.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        offline_orders=Count('id'),
        offline_revenue=Sum('total_amount')
    ).order_by('-month')[:12]
    
    combined_dict_month = {}
    for item in online_monthly_summary:
        month_key = item['month'].strftime('%Y-%m') if item['month'] else None
        if month_key:
            combined_dict_month[month_key] = {
                'month': item['month'],
                'online_orders': item['online_orders'] or 0,
                'online_revenue': item['online_revenue'] or 0,
                'offline_orders': 0,
                'offline_revenue': 0
            }
    
    for item in offline_monthly_summary:
        month_key = item['month'].strftime('%Y-%m') if item['month'] else None
        if month_key:
            if month_key in combined_dict_month:
                combined_dict_month[month_key]['offline_orders'] = item['offline_orders'] or 0
                combined_dict_month[month_key]['offline_revenue'] = item['offline_revenue'] or 0
            else:
                combined_dict_month[month_key] = {
                    'month': item['month'],
                    'online_orders': 0,
                    'online_revenue': 0,
                    'offline_orders': item['offline_orders'] or 0,
                    'offline_revenue': item['offline_revenue'] or 0
                }
    
    combined_monthly_summary = sorted(combined_dict_month.values(), key=lambda x: x['month'], reverse=True)[:12]
    
    # ============================================
    # CONTEXT
    # ============================================
    context = {
        # Combined Stats
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'avg_order_value': avg_order_value,
        
        # Online Order Stats
        'total_online_orders': total_online_orders,
        'total_online_revenue': total_online_revenue,
        'avg_online_order_value': avg_online_order_value,
        'online_status_counts': online_status_counts,
        'online_payment_counts': online_payment_counts,
        'order_value_ranges': order_value_ranges,
        'repeat_customers': repeat_customers,
        'one_time_customers': one_time_customers,
        'online_hourly_sales': online_hourly_sales,
        'online_top_products': online_top_products,
        'online_top_products_by_revenue': online_top_products_by_revenue,
        'online_category_performance': online_category_performance,
        'online_revenue_over_time': online_revenue_over_time,
        'online_daily_revenue': online_daily_revenue,
        'recent_online_orders': recent_online_orders,
        
        # Offline Order Stats
        'total_offline_orders': total_offline_orders,
        'total_offline_revenue': total_offline_revenue,
        'avg_offline_order_value': avg_offline_order_value,
        'offline_status_counts': offline_status_counts,
        'offline_payment_counts': offline_payment_counts,
        'offline_order_value_ranges': offline_order_value_ranges,
        'offline_repeat_customers': offline_repeat_customers,
        'offline_one_time_customers': offline_one_time_customers,
        'offline_top_products': offline_top_products,
        'offline_top_products_by_revenue': offline_top_products_by_revenue,
        'offline_revenue_over_time': offline_revenue_over_time,
        'offline_daily_revenue': offline_daily_revenue,
        'offline_payment_methods': offline_payment_methods,
        'recent_offline_orders': recent_offline_orders,
        
        # Combined Analytics
        'combined_revenue_over_time': combined_revenue_over_time,
        'combined_monthly_summary': combined_monthly_summary,
        
        # Barcode Stats
        'total_barcodes': total_barcodes,
        'product_barcodes': product_barcodes,
        'variant_barcodes': variant_barcodes,
        
        # Offline Customer Analytics
        'total_offline_customers': total_offline_customers,
        'inactive_offline_customers': inactive_offline_customers,
        'offline_customer_revenue': offline_customer_revenue,
        'offline_customer_order_counts': offline_customer_order_counts,
        'offline_customer_trend': offline_customer_trend,
        'offline_customer_ltv': offline_customer_ltv,
        
        # Store Settings
        'store_settings': store_settings,
        
        # User Analytics
        'total_users': total_users,
        'total_customers': total_customers,
        'total_admins': total_admins,
        'total_superusers': total_superusers,
        'new_users_last_30_days': new_users_last_30_days,
        'active_users_last_30_days': active_users_last_30_days,
        'inactive_users': inactive_users,
        'most_active_users': most_active_users,
        'top_users_by_orders': top_users_by_orders,
        'top_users_by_revenue': top_users_by_revenue,
        'user_registration_trend': user_registration_trend,
        'user_roles': user_roles,
        'customer_ltv': customer_ltv,
        
        # Review Analytics
        'total_reviews': total_reviews,
        'approved_reviews': approved_reviews,
        'pending_reviews': pending_reviews,
        'verified_reviews': verified_reviews,
        'avg_rating': avg_rating,
        'rating_distribution': rating_distribution,
        'most_reviewed_products': most_reviewed_products,
        'highest_rated_products': highest_rated_products,
        'review_trend': review_trend,
        'recent_reviews': recent_reviews,
        'approval_rate': approval_rate,
        'satisfaction_score': satisfaction_score,
        
        # Product Stats
        'total_products': total_products,
        'total_products_inactive': total_products_inactive,
        'featured_products': featured_products,
        'best_seller_products': best_seller_products,
        'new_products': new_products,
        'low_stock_products': low_stock_products,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'category_counts': category_counts,
        
        # Filter values
        'filter_type': filter_type,
        'selected_month': selected_month,
        'selected_date': selected_date,
        'date_from': date_from,
        'date_to': date_to,
        'month_options': month_options,
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
    """Product list with search and filter capabilities"""
    
    # Base queryset
    products = Product.objects.select_related('category', 'subcategory')
    
    # ============================================
    # GET FILTER PARAMETERS
    # ============================================
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    subcategory_filter = request.GET.get('subcategory', '')
    brand_filter = request.GET.get('brand', '')
    status_filter = request.GET.get('status', '')
    stock_filter = request.GET.get('stock', '')
    offer_filter = request.GET.get('offer', '')
    sort_by = request.GET.get('sort', 'created_desc')
    
    # ============================================
    # APPLY SEARCH
    # ============================================
    if search_query:
        products = products.filter(
            models.Q(name__icontains=search_query) |
            models.Q(sku__icontains=search_query) |
            models.Q(brand__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(short_description__icontains=search_query) |
            models.Q(category__name__icontains=search_query) |
            models.Q(subcategory__name__icontains=search_query)
        )
    
    # ============================================
    # APPLY FILTERS
    # ============================================
    # Category filter
    if category_filter:
        products = products.filter(category_id=category_filter)
    
    # Subcategory filter
    if subcategory_filter:
        products = products.filter(subcategory_id=subcategory_filter)
    
    # Brand filter
    if brand_filter:
        products = products.filter(brand__icontains=brand_filter)
    
    # Status filter (active/inactive)
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    
    # Stock filter
    if stock_filter == 'in_stock':
        products = products.filter(stock_quantity__gt=0)
    elif stock_filter == 'out_of_stock':
        products = products.filter(stock_quantity=0)
    elif stock_filter == 'low_stock':
        products = products.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=models.F('low_stock_threshold')
        )
    
    # Offer filter
    if offer_filter == 'has_offer':
        products = products.filter(
            models.Q(discount_percentage__gt=0) | 
            models.Q(id__in=Offer.objects.filter(
                is_active=True,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now()
            ).values_list('product_id', flat=True))
        )
    elif offer_filter == 'no_offer':
        products = products.exclude(
            models.Q(discount_percentage__gt=0) | 
            models.Q(id__in=Offer.objects.filter(
                is_active=True,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now()
            ).values_list('product_id', flat=True))
        )
    
    # ============================================
    # APPLY SORTING
    # ============================================
    if sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    elif sort_by == 'price':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'stock':
        products = products.order_by('stock_quantity')
    elif sort_by == 'stock_desc':
        products = products.order_by('-stock_quantity')
    elif sort_by == 'created':
        products = products.order_by('created_at')
    elif sort_by == 'created_desc':
        products = products.order_by('-created_at')
    elif sort_by == 'updated':
        products = products.order_by('updated_at')
    elif sort_by == 'updated_desc':
        products = products.order_by('-updated_at')
    else:
        products = products.order_by('-created_at')
    
    # ============================================
    # GET FILTER OPTIONS
    # ============================================
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    # Get subcategories based on selected category
    if category_filter:
        subcategories = SubCategory.objects.filter(
            is_active=True,
            category_id=category_filter
        ).order_by('name')
    else:
        subcategories = SubCategory.objects.filter(is_active=True).order_by('name')
    
    brands = Product.objects.exclude(brand__isnull=True).exclude(brand='').values_list('brand', flat=True).distinct().order_by('brand')
    
    # ============================================
    # PAGINATION
    # ============================================
    paginator = Paginator(products, 20)
    page = request.GET.get('page')
    products_page = paginator.get_page(page)
    
    context = {
        'products': products_page,
        'categories': categories,
        'subcategories': subcategories,
        'brands': brands,
        # Current filter values
        'search_query': search_query,
        'category_filter': category_filter,
        'subcategory_filter': subcategory_filter,
        'brand_filter': brand_filter,
        'status_filter': status_filter,
        'stock_filter': stock_filter,
        'offer_filter': offer_filter,
        'sort_by': sort_by,
        # Counts
        'total_products': products.count(),
    }
    return render(request, 'Ecom/admin/product_list.html', context)

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
    # GET RECENTLY VIEWED PRODUCTS (excluding current)
    # ============================================
    recently_viewed_products = []
    if request.user.is_authenticated:
        # Use the class method to get recently viewed
        recently_viewed_items = RecentlyViewed.get_recently_viewed(request.user, limit=10)
        
        # Exclude current product and get product objects
        recently_viewed_products = [
            item.product for item in recently_viewed_items 
            if item.product.id != product.id
        ]
    
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
        'recently_viewed_products': recently_viewed_products,  # ✅ Make sure this is here
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
    # Get all reviews with related data
    reviews = ProductReview.objects.select_related('product', 'user').all()
    
    # Calculate counts properly
    total_count = reviews.count()
    pending_count = reviews.filter(is_approved=False).count()
    approved_count = reviews.filter(is_approved=True).count()
    rejected_count = 0  # You can add a rejected status if needed
    
    context = {
        'reviews': reviews,
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    
    return render(request, 'Ecom/admin/review_list.html', context)

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

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

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
                
                # ============================================
                # SEND EMAIL NOTIFICATIONS
                # ============================================
                send_order_confirmation_emails(order, request)
                
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


def send_order_confirmation_emails(order, request):
    """
    Send order confirmation emails to customer and superuser
    """
    try:
        # ============================================
        # PREPARE ORDER DATA FOR EMAIL
        # ============================================
        order_items = []
        subtotal = Decimal('0')
        
        for item in order.items.all():
            item_total = item.final_price * item.quantity
            order_items.append({
                'name': item.product_name,
                'sku': item.sku,
                'quantity': item.quantity,
                'price': item.final_price,
                'total': item_total,
                'original_price': item.original_price,
                'discount': item.product_discount + item.offer_discount,
                'offer_name': item.offer_name if item.offer_name else None,
            })
            subtotal += item_total
        
        # Prepare context for email templates
        context = {
            'order': order,
            'order_items': order_items,
            'subtotal': subtotal,
            'total': order.total_amount,
            'user': order.user,
            'site_name': 'MyStore',
            'site_url': request.build_absolute_uri('/'),
            'order_url': request.build_absolute_uri(
                reverse('Ecom:order_detail', args=[order.id])
            ),
            'order_success_url': request.build_absolute_uri(
                reverse('Ecom:order_success', args=[order.id])
            ),
            'support_email': settings.DEFAULT_FROM_EMAIL or 'support@mystore.com',
            'payment_id': order.razorpay_payment_id,
            'shipping_address': order.shipping_address,
            'billing_address': order.billing_address,
            'order_date': order.created_at.strftime('%B %d, %Y at %I:%M %p'),
            'coupon_code': order.coupon.code if order.coupon else None,
            'coupon_discount': order.coupon_discount,
            'product_discount_total': order.product_discount_total,
            'offer_discount': order.offer_discount,
        }
        
        # ============================================
        # 1. SEND EMAIL TO CUSTOMER
        # ============================================
        customer_subject = f'Order Confirmation - Order #{order.order_number}'
        
        customer_html = render_to_string('emails/order_confirmation_customer.html', context)
        customer_plain = strip_tags(customer_html)
        
        customer_email = EmailMultiAlternatives(
            subject=customer_subject,
            body=customer_plain,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email],
            reply_to=[settings.DEFAULT_FROM_EMAIL],
        )
        customer_email.attach_alternative(customer_html, "text/html")
        customer_email.send(fail_silently=False)
        
        # ============================================
        # 2. SEND EMAIL TO SUPERUSERS (Admin Notification)
        # ============================================
        superusers = User.objects.filter(
            is_superuser=True, 
            is_active=True
        ).exclude(email__isnull=True).exclude(email='')
        
        superuser_emails = list(superusers.values_list('email', flat=True))
        
        if superuser_emails:
            admin_subject = f'🔔 New Order Received - Order #{order.order_number}'
            
            admin_html = render_to_string('emails/admin_order_notification.html', context)
            admin_plain = strip_tags(admin_html)
            
            try:
                admin_email = EmailMultiAlternatives(
                    subject=admin_subject,
                    body=admin_plain,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=superuser_emails,
                    reply_to=[order.user.email],
                )
                admin_email.attach_alternative(admin_html, "text/html")
                admin_email.send(fail_silently=False)
            except Exception:
                # Try sending individually if batch fails
                for email in superuser_emails:
                    try:
                        single_admin_email = EmailMultiAlternatives(
                            subject=admin_subject,
                            body=admin_plain,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            to=[email],
                            reply_to=[order.user.email],
                        )
                        single_admin_email.attach_alternative(admin_html, "text/html")
                        single_admin_email.send(fail_silently=False)
                    except Exception:
                        pass
        else:
            # Fallback: Check for admin email in settings
            if hasattr(settings, 'ADMIN_EMAILS') and settings.ADMIN_EMAILS:
                admin_subject = f'🔔 New Order Received - Order #{order.order_number}'
                admin_html = render_to_string('emails/admin_order_notification.html', context)
                admin_plain = strip_tags(admin_html)
                
                admin_email = EmailMultiAlternatives(
                    subject=admin_subject,
                    body=admin_plain,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=settings.ADMIN_EMAILS,
                    reply_to=[order.user.email],
                )
                admin_email.attach_alternative(admin_html, "text/html")
                admin_email.send(fail_silently=False)
        
    except Exception as e:
        # Log email error but don't fail the order
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending order confirmation emails for Order #{order.order_number}: {str(e)}")


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'Ecom/order_success.html', {'order': order})

# views.py - Updated orders_view
from offline_sales.models import *
@login_required
def orders_view(request):
    """
    View orders - Shows both Online and Offline orders
    - Admin/Superuser: Sees all orders (online + offline)
    - Customer: Sees their own orders (online + offline)
    """
    if request.user.is_admin or request.user.is_superuser:
        # Get online orders
        online_orders = Order.objects.all().order_by('-created_at')
        
        # Get offline orders
        offline_orders = OfflineOrder.objects.all().order_by('-created_at')
    else:
        # Customer - get their online orders
        online_orders = Order.objects.filter(user=request.user).order_by('-created_at')
        
        # Customer - get their offline orders (where customer is the online user or offline customer matches)
        # Check if user has offline orders linked to their online account
        offline_orders = OfflineOrder.objects.filter(
            customer=request.user
        ).order_by('-created_at')
        
        # Also check if user has offline orders linked via offline_customer
        # This handles the case where a customer was created as offline first
        offline_customer = OfflineCustomer.objects.filter(
            email=request.user.email,
            is_active=True
        ).first()
        
        if offline_customer:
            offline_orders = offline_orders | OfflineOrder.objects.filter(
                offline_customer=offline_customer
            ).order_by('-created_at')
        
        # Remove duplicates
        offline_orders = offline_orders.distinct()
    
    # Combine orders with type indicator
    combined_orders = []
    
    # Add online orders
    for order in online_orders:
        combined_orders.append({
            'order': order,
            'type': 'online',
            'order_number': order.order_number,
            'created_at': order.created_at,
            'total_amount': order.total_amount,
            'status': order.status,
            'payment_status': order.payment_status,
            'items': order.items.all(),
            'type_display': 'Online'
        })
    
    # Add offline orders
    for order in offline_orders:
        # Check if order already exists (avoid duplicates)
        existing = False
        for existing_order in combined_orders:
            if existing_order['order_number'] == order.order_number:
                existing = True
                break
        
        if not existing:
            combined_orders.append({
                'order': order,
                'type': 'offline',
                'order_number': order.order_number,
                'created_at': order.created_at,
                'total_amount': order.total_amount,
                'status': order.status,
                'payment_status': order.payment_status,
                'items': order.items.all(),
                'type_display': 'Offline',
                'invoice_number': order.invoice_number,
            })
    
    # Sort combined orders by created_at (newest first)
    combined_orders.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Get counts
    total_orders = len(combined_orders)
    online_count = sum(1 for o in combined_orders if o['type'] == 'online')
    offline_count = sum(1 for o in combined_orders if o['type'] == 'offline')
    
    context = {
        'orders': combined_orders,
        'total_orders': total_orders,
        'online_count': online_count,
        'offline_count': offline_count,
        'is_admin': request.user.is_admin or request.user.is_superuser,
    }
    return render(request, 'Ecom/orders.html', context)


# views.py - Updated order_detail_view

@login_required
def order_detail_view(request, order_id):
    """
    Order detail view with cancellation/return/replacement actions
    Handles both Online and Offline orders
    """
    # Try to find online order first
    online_order = None
    offline_order = None
    order = None
    is_admin = request.user.is_admin or request.user.is_superuser
    is_offline = False
    
    # Check if it's an offline order (starts with OFF)
    try:
        offline_order = get_object_or_404(OfflineOrder, id=order_id)
        if not is_admin:
            # Check if user owns this offline order
            if offline_order.customer and offline_order.customer.id != request.user.id:
                # Check if offline customer matches user's email
                offline_customer = OfflineCustomer.objects.filter(
                    email=request.user.email,
                    id=offline_order.offline_customer.id
                ).exists()
                if not offline_customer:
                    messages.error(request, 'You do not have permission to view this order.')
                    return redirect('Ecom:orders')
        order = offline_order
        is_offline = True
    except (OfflineOrder.DoesNotExist, ValueError):
        pass
    
    # If not offline, try online order
    if not order:
        try:
            if is_admin:
                online_order = get_object_or_404(Order, id=order_id)
            else:
                online_order = get_object_or_404(Order, id=order_id, user=request.user)
            order = online_order
            is_offline = False
        except (Order.DoesNotExist, ValueError):
            messages.error(request, 'Order not found.')
            return redirect('Ecom:orders')
    
    # Get items and transactions based on order type
    if is_offline:
        items = order.items.all() if hasattr(order, 'items') else []
        transactions = order.transactions.all() if hasattr(order, 'transactions') else []
    else:
        items = order.items.all()
        transactions = order.transactions.all()
    
    # Check actions availability (only for online orders)
    can_cancel = False
    can_request_return = False
    can_request_replacement = False
    cancellation_requested = False
    return_requested = False
    replacement_requested = False
    return_window_days = 0
    return_status_display = 'N/A'
    replacement_status_display = 'N/A'
    refund_status_display = 'N/A'
    
    if not is_offline:
        can_cancel = order.can_cancel
        can_request_return = order.can_request_return
        can_request_replacement = order.can_request_replacement
        cancellation_requested = order.cancellation_requested
        return_requested = order.return_requested
        replacement_requested = order.replacement_requested
        return_window_days = order.return_window_remaining
        return_status_display = order.return_status_display
        replacement_status_display = order.replacement_status_display
        refund_status_display = order.refund_status_display
    
    context = {
        'order': order,
        'items': items,
        'transactions': transactions,
        'is_admin_view': is_admin,
        'is_offline': is_offline,
        'can_cancel': can_cancel,
        'can_request_return': can_request_return,
        'can_request_replacement': can_request_replacement,
        'cancellation_requested': cancellation_requested,
        'return_requested': return_requested,
        'replacement_requested': replacement_requested,
        'return_window_days': return_window_days,
        'return_status_display': return_status_display,
        'replacement_status_display': replacement_status_display,
        'refund_status_display': refund_status_display,
        'order_type_display': 'Offline Order' if is_offline else 'Online Order',
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
    
    # Get original price - Use variant's price if variant exists
    original_price = Decimal(str(product.price))
    if variant:
        original_price = Decimal(str(variant.price))
    
    # Convert price to Decimal
    if not isinstance(price, Decimal):
        price = Decimal(str(price))
    
    # Calculate product discount amount on the correct price
    product_discount_amount = original_price - price
    
    # ============================================
    # 1. FIND THE BEST OFFER DISCOUNT
    # ============================================
    for offer in offers:
        discount_value = Decimal(str(offer.discount_value))
        
        if offer.offer_type == 'product':
            if offer.product and offer.product.id == product.id:
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
            if product.category and offer.category and offer.category.id == product.category.id:
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
    
    # ============================================
    # 2. APPLY THE BEST DISCOUNT
    # ============================================
    
    # Case 1: No product discount, no offer
    if product_discount_amount == 0 and best_offer_discount == 0:
        return price, None, Decimal('0')
    
    # Case 2: Only product discount exists
    if product_discount_amount > 0 and best_offer_discount == 0:
        return price, "Product Discount", Decimal('0')
    
    # Case 3: Only offer exists
    if product_discount_amount == 0 and best_offer_discount > 0:
        final_price = original_price - best_offer_discount
        return final_price, best_offer_name, best_offer_discount
    
    # Case 4: Both exist - apply the better one
    if product_discount_amount > 0 and best_offer_discount > 0:
        product_final_price = original_price - product_discount_amount
        offer_final_price = original_price - best_offer_discount
        
        if offer_final_price < product_final_price:
            return offer_final_price, best_offer_name, best_offer_discount
        else:
            return product_final_price, "Product Discount", Decimal('0')
    
    # Fallback
    return price, None, Decimal('0')

from django.http import JsonResponse
from .models import SubCategory

def get_subcategories_ajax(request):
    """Get subcategories based on category selection"""
    category_id = request.GET.get('category_id')
    if category_id:
        subcategories = SubCategory.objects.filter(
            category_id=category_id, 
            is_active=True
        ).values('id', 'name').order_by('name')
        return JsonResponse(list(subcategories), safe=False)
    return JsonResponse([], safe=False)

def get_all_subcategories_ajax(request):
    """Get all subcategories (fallback)"""
    subcategories = SubCategory.objects.filter(
        is_active=True
    ).values('id', 'name').order_by('name')
    return JsonResponse(list(subcategories), safe=False)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import Order, OrderItem, Transaction
import logging

logger = logging.getLogger(__name__)

# ============================================
# ORDER MANAGEMENT VIEWS (Admin/Superuser)
# ============================================

# views.py - Updated admin_order_list_view and admin_order_detail_view

@staff_member_required
def admin_order_list_view(request):
    """
    Admin view to list all orders with filters
    Excludes:
    - Pending payment orders
    - Failed orders
    - Orders with cancellation/return/replacement requests (they have their own sections)
    """
    # ============================================
    # EXCLUDE ORDERS WITH SPECIAL REQUESTS
    # ============================================
    # Base queryset - exclude pending payments and failed orders
    orders = Order.objects.select_related('user', 'coupon', 'offer').exclude(
        payment_status='pending'
    ).exclude(
        status='failed'
    )
    
    # ============================================
    # EXCLUDE ORDERS WITH CANCELLATION REQUESTS
    # ============================================
    orders = orders.exclude(
        cancellation_requested=True
    )
    
    # ============================================
    # EXCLUDE ORDERS WITH RETURN REQUESTS
    # ============================================
    orders = orders.exclude(
        return_requested=True
    )
    
    # ============================================
    # EXCLUDE ORDERS WITH REPLACEMENT REQUESTS
    # ============================================
    orders = orders.exclude(
        replacement_requested=True
    )
    
    # ============================================
    # FILTERS
    # ============================================
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_status', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Apply status filter
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Apply payment status filter
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)
    
    # Apply search
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(user__full_name__icontains=search_query) |
            Q(shipping_address__icontains=search_query)
        )
    
    # Apply date filters
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__date__gte=date_from_obj.date())
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            orders = orders.filter(created_at__date__lte=date_to_obj.date())
        except ValueError:
            pass
    
    # ============================================
    # ORDER STATISTICS (Only show active orders)
    # ============================================
    # Get all orders for count (excluding pending, failed, and special requests)
    active_orders = Order.objects.exclude(
        payment_status='pending'
    ).exclude(
        status='failed'
    ).exclude(
        cancellation_requested=True
    ).exclude(
        return_requested=True
    ).exclude(
        replacement_requested=True
    )
    
    # Get counts for special requests (to show in stats)
    cancellation_count = Order.objects.filter(
        cancellation_requested=True,
        status__in=['pending', 'processing']
    ).count()
    
    return_count = Order.objects.filter(
        return_requested=True,
        return_completed=False
    ).exclude(
        status='cancelled'
    ).count()
    
    replacement_count = Order.objects.filter(
        replacement_requested=True,
        replacement_completed=False
    ).exclude(
        status='cancelled'
    ).count()
    
    stats = {
        'total': active_orders.count(),
        'processing': active_orders.filter(status='processing').count(),
        'shipped': active_orders.filter(status='shipped').count(),
        'delivered': active_orders.filter(status='delivered').count(),
        'cancelled': active_orders.filter(status='cancelled').count(),
        'paid': active_orders.filter(payment_status='paid').count(),
        'refunded': active_orders.filter(payment_status='refunded').count(),
        # Add special request counts
        'cancellation_requests': cancellation_count,
        'return_requests': return_count,
        'replacement_requests': replacement_count,
    }
    
    # ============================================
    # SORTING
    # ============================================
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['created_at', '-created_at', 'order_number', '-order_number', 
                   'total_amount', '-total_amount', 'status', '-status']
    if sort_by in valid_sorts:
        orders = orders.order_by(sort_by)
    else:
        orders = orders.order_by('-created_at')
    
    # ============================================
    # PAGINATION
    # ============================================
    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    context = {
        'orders': orders_page,
        'stats': stats,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'total_count': orders.count(),
        'status_choices': Order.STATUS_CHOICES,
        'payment_status_choices': Order.PAYMENT_STATUS_CHOICES,
    }
    return render(request, 'Ecom/admin/order_list.html', context)


@staff_member_required
def admin_order_detail_view(request, order_id):
    """
    Admin view to see order details
    Shows all orders regardless of status (for admin to view complete details)
    """
    order = get_object_or_404(Order, id=order_id)
    transactions = order.transactions.all()
    items = order.items.all()
    
    # Check if order has any special requests
    has_cancellation_request = order.cancellation_requested
    has_return_request = order.return_requested
    has_replacement_request = order.replacement_requested
    
    # Get related special request URLs
    special_request_urls = {}
    if has_cancellation_request:
        special_request_urls['cancellation'] = reverse('Ecom:admin_cancellation_detail', args=[order.id])
    if has_return_request:
        special_request_urls['return'] = reverse('Ecom:admin_return_detail', args=[order.id])
    if has_replacement_request:
        special_request_urls['replacement'] = reverse('Ecom:admin_replacement_detail', args=[order.id])
    
    context = {
        'order': order,
        'items': items,
        'transactions': transactions,
        'has_cancellation_request': has_cancellation_request,
        'has_return_request': has_return_request,
        'has_replacement_request': has_replacement_request,
        'special_request_urls': special_request_urls,
    }
    return render(request, 'Ecom/admin/order_detail.html', context)

def send_order_status_update_email(order, old_status, request):
    """
    Send email notification to customer when order status is updated
    """
    try:
        # Get status display names
        old_status_display = dict(Order.STATUS_CHOICES).get(old_status, old_status)
        new_status_display = order.get_status_display()
        
        # Prepare context for email
        context = {
            'order': order,
            'user': order.user,
            'old_status': old_status_display,
            'new_status': new_status_display,
            'site_name': 'MyStore',
            'site_url': request.build_absolute_uri('/'),
            'order_url': request.build_absolute_uri(
                reverse('Ecom:order_detail', args=[order.id])
            ),
            'support_email': settings.DEFAULT_FROM_EMAIL or 'support@mystore.com',
            'order_date': order.created_at.strftime('%B %d, %Y at %I:%M %p'),
            'total_amount': order.total_amount,
        }
        
        # Add tracking info if available
        if order.tracking_number:
            context['tracking_number'] = order.tracking_number
        if order.tracking_url:
            context['tracking_url'] = order.tracking_url
        if order.delivery_date:
            context['delivery_date'] = order.delivery_date.strftime('%B %d, %Y')
        
        # Render HTML email
        subject = f'Order #{order.order_number} Status Update - {new_status_display}'
        html_content = render_to_string('emails/order_status_update.html', context)
        text_content = strip_tags(html_content)
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.user.email],
            reply_to=[settings.DEFAULT_FROM_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        
        logger.info(f"Status update email sent to {order.user.email} for Order #{order.order_number}")
        
    except Exception as e:
        logger.error(f"Failed to send status update email for Order #{order.order_number}: {str(e)}")


@staff_member_required
def admin_order_update_view(request, order_id):
    """
    Admin view to update order status, tracking info, and delivery date
    """
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        # Get form data
        status = request.POST.get('status')
        tracking_number = request.POST.get('tracking_number', '').strip()
        tracking_url = request.POST.get('tracking_url', '').strip()
        delivery_date = request.POST.get('delivery_date')
        notes = request.POST.get('notes', '').strip()
        send_email = request.POST.get('send_email', 'on')  # Checkbox to send email
        
        old_status = order.status
        
        # Update order
        if status and status in dict(Order.STATUS_CHOICES):
            order.status = status
        
        if tracking_number:
            order.tracking_number = tracking_number
        
        if tracking_url:
            order.tracking_url = tracking_url
        
        if delivery_date:
            try:
                from datetime import datetime
                order.delivery_date = datetime.strptime(delivery_date, '%Y-%m-%dT%H:%M')
            except ValueError:
                try:
                    order.delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d')
                except ValueError:
                    pass
        
        if notes:
            order.notes = notes
        
        order.save()
        
        # Send email notification if status changed and send_email is checked
        if old_status != order.status and send_email == 'on':
            send_order_status_update_email(order, old_status, request)
            messages.success(request, f'Order #{order.order_number} updated and email sent to customer!')
        else:
            messages.success(request, f'Order #{order.order_number} updated successfully!')
        
        return redirect('Ecom:admin_order_detail', order_id=order.id)
    
    # GET request - redirect to detail
    return redirect('Ecom:admin_order_detail', order_id=order.id)


@staff_member_required
def admin_order_bulk_update_view(request):
    """
    Bulk update orders (status, tracking, etc.) with email notifications
    """
    if request.method == 'POST':
        order_ids = request.POST.getlist('order_ids')
        action = request.POST.get('action')
        send_email = request.POST.get('send_email', 'on')
        
        if not order_ids:
            messages.error(request, 'No orders selected.')
            return redirect('Ecom:admin_order_list')
        
        # Get orders to update (exclude pending payment orders)
        orders_to_update = Order.objects.filter(id__in=order_ids).exclude(payment_status='pending')
        skipped_count = len(order_ids) - orders_to_update.count()
        
        if skipped_count > 0:
            messages.warning(request, f'Skipped {skipped_count} pending orders.')
        
        updated_count = 0
        email_count = 0
        
        for order in orders_to_update:
            old_status = order.status
            
            if action == 'mark_processing':
                order.status = 'processing'
            elif action == 'mark_shipped':
                order.status = 'shipped'
            elif action == 'mark_delivered':
                order.status = 'delivered'
                order.delivery_date = timezone.now()
            elif action == 'mark_cancelled':
                order.status = 'cancelled'
            else:
                messages.error(request, 'Invalid action selected.')
                return redirect('Ecom:admin_order_list')
            
            order.save()
            updated_count += 1
            
            # Send email notification if status changed and send_email is checked
            if old_status != order.status and send_email == 'on':
                # Use a dummy request for email
                from django.test import RequestFactory
                factory = RequestFactory()
                dummy_request = factory.get('/')
                dummy_request.build_absolute_uri = request.build_absolute_uri
                
                send_order_status_update_email(order, old_status, dummy_request)
                email_count += 1
        
        if email_count > 0:
            messages.success(request, f'{updated_count} orders updated. {email_count} email notifications sent.')
        else:
            messages.success(request, f'{updated_count} orders updated successfully.')
        
        return redirect('Ecom:admin_order_list')
    
    return redirect('Ecom:admin_order_list')


@staff_member_required
def admin_order_status_update_ajax(request):
    """
    AJAX endpoint to update order status and send email notification
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('order_id')
        status = data.get('status')
        send_email = data.get('send_email', True)
        
        try:
            order = Order.objects.get(id=order_id)
            if status in dict(Order.STATUS_CHOICES):
                old_status = order.status
                order.status = status
                order.save()
                
                # Send email notification if status changed
                if old_status != order.status and send_email:
                    # Create a dummy request for email
                    from django.test import RequestFactory
                    factory = RequestFactory()
                    dummy_request = factory.get('/')
                    dummy_request.build_absolute_uri = request.build_absolute_uri
                    
                    send_order_status_update_email(order, old_status, dummy_request)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Order #{order.order_number} status updated to {dict(Order.STATUS_CHOICES)[status]}',
                    'email_sent': old_status != order.status and send_email
                })
            else:
                return JsonResponse({'success': False, 'error': 'Invalid status'})
        except Order.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Order not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Banner
from .forms import BannerForm

# ============================================
# PUBLIC VIEWS
# ============================================

def get_active_banners(limit=None):
    """Get active banners for homepage"""
    queryset = Banner.objects.filter(is_active=True).order_by('-created_at')
    if limit:
        queryset = queryset[:limit]
    return queryset


# ============================================
# ADMIN VIEWS (CRUD)
# ============================================

@staff_member_required
def banner_list_view(request):
    """List all banners"""
    banners = Banner.objects.all().order_by('-created_at')
    
    total_banners = banners.count()
    active_banners = banners.filter(is_active=True).count()
    inactive_banners = banners.filter(is_active=False).count()
    
    context = {
        'banners': banners,
        'total_banners': total_banners,
        'active_banners': active_banners,
        'inactive_banners': inactive_banners,
    }
    return render(request, 'Ecom/admin/banner_list.html', context)


@staff_member_required
def banner_create_view(request):
    """Create a new banner"""
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = form.save()
            messages.success(request, f'Banner "{banner.title}" created successfully!')
            return redirect('Ecom:banner_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = BannerForm()
    
    return render(request, 'Ecom/admin/banner_form.html', {
        'form': form,
        'action': 'Create',
    })


@staff_member_required
def banner_edit_view(request, banner_id):
    """Edit an existing banner"""
    banner = get_object_or_404(Banner, id=banner_id)
    
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, f'Banner "{banner.title}" updated successfully!')
            return redirect('Ecom:banner_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = BannerForm(instance=banner)
    
    return render(request, 'Ecom/admin/banner_form.html', {
        'form': form,
        'action': 'Edit',
        'banner': banner
    })


@staff_member_required
def banner_delete_view(request, banner_id):
    """Delete a banner"""
    banner = get_object_or_404(Banner, id=banner_id)
    
    if request.method == 'POST':
        title = banner.title
        banner.delete()
        messages.success(request, f'Banner "{title}" deleted successfully!')
        return redirect('Ecom:banner_list')
    
    # GET request - redirect back
    messages.error(request, 'Invalid request method.')
    return redirect('Ecom:banner_list')


@staff_member_required
def banner_toggle_status_view(request, banner_id):
    """Toggle banner active status"""
    banner = get_object_or_404(Banner, id=banner_id)
    
    banner.is_active = not banner.is_active
    banner.save()
    
    status = 'activated' if banner.is_active else 'deactivated'
    messages.success(request, f'Banner "{banner.title}" {status} successfully!')
    return redirect('Ecom:banner_list')

# views.py - Add these views

from .forms import CancellationForm, ReturnForm, ReplacementForm
from .utils import (
    process_cancellation, approve_cancellation, reject_cancellation,
    process_return_request, approve_return, reject_return, 
    mark_return_items_received, complete_return,
    process_replacement_request, approve_replacement, reject_replacement,
    complete_replacement, initiate_refund, mark_refund_completed
)

# ============================================
# CANCELLATION VIEWS
# ============================================

@login_required
def cancel_order_view(request, order_id):
    """Customer view to request order cancellation"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if not order.can_cancel:
        messages.error(request, 'This order cannot be cancelled. Orders can only be cancelled when status is Pending or Processing.')
        return redirect('Ecom:order_detail', order_id=order.id)
    
    if request.method == 'POST':
        form = CancellationForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            process_cancellation(order, reason, request)
            messages.success(request, f'Cancellation request submitted for Order #{order.order_number}')
            return redirect('Ecom:order_detail', order_id=order.id)
    else:
        form = CancellationForm()
    
    context = {
        'order': order,
        'form': form,
    }
    return render(request, 'Ecom/orders/cancel_order.html', context)


# ============================================
# RETURN VIEWS (Full Order)
# ============================================
# views.py - Update these views

# views.py - Updated request_return_view

@login_required
def request_return_view(request, order_id):
    """Customer view to request return for full order"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if not order.can_request_return:
        messages.error(request, 'Return cannot be requested for this order. Order must be delivered within 7 days.')
        return redirect('Ecom:order_detail', order_id=order.id)
    
    if request.method == 'POST':
        form = ReturnForm(request.POST, request.FILES)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            description = form.cleaned_data['description']
            bank_details = form.cleaned_data['bank_details']
            images = request.FILES.getlist('images')
            
            # Debug - check if bank_details is received
            print(f"Bank Details Received: {bank_details}")
            
            # Process return request with bank details
            process_return_request(order, reason, description, bank_details, images, request)
            
            messages.success(request, f'Return request submitted for Order #{order.order_number}')
            return redirect('Ecom:order_detail', order_id=order.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = ReturnForm()
    
    context = {
        'order': order,
        'form': form,
        'return_window_days': order.return_window_remaining,
        'order_items': order.items.all(),
    }
    return render(request, 'Ecom/orders/request_return.html', context)

@login_required
def request_replacement_view(request, order_id):
    """Customer view to request replacement for full order"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if not order.can_request_replacement:
        messages.error(request, 'Replacement cannot be requested for this order. Order must be delivered within 7 days.')
        return redirect('Ecom:order_detail', order_id=order.id)
    
    if request.method == 'POST':
        form = ReplacementForm(request.POST, request.FILES)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            description = form.cleaned_data['description']
            images = form.cleaned_data.get('images', [])  # This will be a list of files
            
            process_replacement_request(order, reason, description, images, request)
            messages.success(request, f'Replacement request submitted for Order #{order.order_number}')
            return redirect('Ecom:order_detail', order_id=order.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = ReplacementForm()
    
    context = {
        'order': order,
        'form': form,
        'replacement_window_days': order.return_window_remaining,
        'order_items': order.items.all(),
    }
    return render(request, 'Ecom/orders/request_replacement.html', context)

from .forms import AdminCancellationActionForm, AdminReturnActionForm, AdminReplacementActionForm

# ============================================
# ADMIN - CANCELLATION REQUESTS
# ============================================

# views.py - Updated admin_cancellation_requests_view

@staff_member_required
def admin_cancellation_requests_view(request):
    """Admin view to manage cancellation requests"""
    # Only show pending cancellations that are not completed
    cancellations = Order.objects.filter(
        cancellation_requested=True,
        status__in=['pending', 'processing'],  # Only pending/processing
        cancelled_at__isnull=True,  # Not already cancelled
        refund_completed=False,  # Not fully refunded
    ).select_related('user').order_by('-cancellation_requested_at')
    
    # Also include cancelled orders that need refund
    cancelled_pending_refund = Order.objects.filter(
        status='cancelled',
        payment_status='paid',
        refund_requested=False,
        refund_completed=False,
    ).select_related('user').order_by('-cancelled_at')
    
    stats = {
        'pending': cancellations.count(),
        'pending_refund': cancelled_pending_refund.count(),
        'total': Order.objects.filter(cancellation_requested=True).count(),
    }
    
    context = {
        'cancellations': cancellations,
        'cancelled_pending_refund': cancelled_pending_refund,
        'stats': stats,
    }
    return render(request, 'Ecom/admin/cancellation_requests.html', context)


# views.py - Fixed admin_cancellation_detail_view

@staff_member_required
def admin_cancellation_detail_view(request, order_id):
    """Admin view to handle individual cancellation request"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        form = AdminCancellationActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('notes', '')
            
            try:
                if action == 'approve':
                    # Check if payment is paid
                    if order.payment_status == 'paid':
                        refund_method = form.cleaned_data.get('refund_method')
                        bank_details = form.cleaned_data.get('bank_details', '')
                        
                        # Validate refund method
                        if not refund_method:
                            messages.error(request, 'Please select a refund method.')
                            return redirect('Ecom:admin_cancellation_detail', order_id=order.id)
                        
                        if refund_method == 'manual' and not bank_details:
                            messages.error(request, 'Please enter bank details for manual transfer.')
                            return redirect('Ecom:admin_cancellation_detail', order_id=order.id)
                    else:
                        refund_method = None
                        bank_details = None
                    
                    # Approve cancellation with refund
                    approve_cancellation(order, refund_method, bank_details, notes, request)
                    
                    if refund_method == 'razorpay':
                        messages.success(request, f'Order #{order.order_number} cancelled and refund initiated via Razorpay.')
                    elif refund_method == 'manual':
                        messages.success(request, f'Order #{order.order_number} cancelled. Manual refund instructions sent.')
                    else:
                        messages.success(request, f'Order #{order.order_number} cancelled.')
                    
                elif action == 'reject':
                    reject_cancellation(order, notes or 'No reason provided', request)
                    messages.success(request, f'Cancellation request for Order #{order.order_number} rejected')
                
                return redirect('Ecom:admin_cancellation_detail', order_id=order.id)
                
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    
    else:
        form = AdminCancellationActionForm()
    
    context = {
        'order': order,
        'form': form,
        'items': order.items.all(),
        'transactions': order.transactions.all(),
    }
    return render(request, 'Ecom/admin/cancellation_detail.html', context)
# ============================================
# ADMIN - RETURN REQUESTS
# ============================================

# views.py - Updated admin_return_requests_view

@staff_member_required
def admin_return_requests_view(request):
    """Admin view to manage return requests"""
    # Exclude completed returns
    returns = Order.objects.filter(
        return_requested=True,
        return_completed=False,  # Not completed
    ).select_related('user').order_by('-return_requested_at')
    
    # Also exclude if order is cancelled
    returns = returns.exclude(status='cancelled')
    
    stats = {
        'pending': returns.filter(return_approved=False, return_rejected=False).count(),
        'approved': returns.filter(return_approved=True, return_items_received=False).count(),
        'items_received': returns.filter(return_items_received=True, refund_requested=False).count(),
        'rejected': returns.filter(return_rejected=True).count(),
        'completed': Order.objects.filter(return_requested=True, return_completed=True).count(),
        'total': returns.count(),
    }
    
    status_filter = request.GET.get('status', '')
    if status_filter == 'pending':
        returns = returns.filter(return_approved=False, return_rejected=False)
    elif status_filter == 'approved':
        returns = returns.filter(return_approved=True, return_items_received=False)
    elif status_filter == 'rejected':
        returns = returns.filter(return_rejected=True)
    elif status_filter == 'received':
        returns = returns.filter(return_items_received=True, refund_requested=False)
    elif status_filter == 'completed':
        # For completed, show all completed returns
        returns = Order.objects.filter(return_requested=True, return_completed=True)
    else:
        # Default: show all active returns
        returns = Order.objects.filter(
            return_requested=True,
            return_completed=False,
        ).exclude(status='cancelled')
    
    context = {
        'returns': returns,
        'stats': stats,
        'status_filter': status_filter,
    }
    return render(request, 'Ecom/admin/return_requests.html', context)

# views.py - admin_return_detail_view

# views.py - Updated admin_return_detail_view
# views.py - Fixed admin_return_detail_view

@staff_member_required
def admin_return_detail_view(request, order_id):
    """Admin view to handle individual return request"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        form = AdminReturnActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('notes', '')
            
            try:
                with transaction.atomic():
                    if action == 'approve':
                        approve_return(order, request)
                        messages.success(request, f'Return approved for Order #{order.order_number}')
                    
                    elif action == 'reject':
                        reject_return(order, notes or 'No reason provided', request)
                        messages.success(request, f'Return rejected for Order #{order.order_number}')
                    
                    elif action == 'mark_received':
                        mark_return_items_received(order, request)
                        messages.success(request, f'Return items marked as received for Order #{order.order_number}')
                    
                    elif action == 'initiate_refund':
                        refund_method = form.cleaned_data.get('refund_method')
                        
                        # CRITICAL FIX: Use order.total_amount as default if not provided
                        refund_amount = form.cleaned_data.get('refund_amount')
                        if refund_amount is None or refund_amount <= 0:
                            refund_amount = order.total_amount
                            messages.info(request, f'Using order total amount ₹{refund_amount} for refund.')
                        
                        # Ensure refund_amount is Decimal
                        try:
                            refund_amount = Decimal(str(refund_amount))
                        except (ValueError, TypeError):
                            refund_amount = order.total_amount
                            messages.warning(request, f'Invalid refund amount. Using order total ₹{refund_amount}.')
                        
                        # Get bank details - use customer's if available
                        if order.return_bank_details:
                            bank_details = order.return_bank_details
                        else:
                            bank_details = form.cleaned_data.get('bank_details', '')
                        
                        # Validate
                        if not refund_method:
                            messages.error(request, 'Please select a refund method.')
                            return redirect('Ecom:admin_return_detail', order_id=order.id)
                        
                        if refund_method == 'manual' and not bank_details:
                            messages.error(request, 'Please enter bank details for manual transfer.')
                            return redirect('Ecom:admin_return_detail', order_id=order.id)
                        
                        # Initiate refund
                        success, message = initiate_refund(
                            order, 
                            refund_amount, 
                            refund_method, 
                            bank_details, 
                            f'Return refund. {notes}' if notes else 'Return refund',
                            request
                        )
                        
                        if success:
                            messages.success(request, message)
                        else:
                            messages.error(request, message)
                            return redirect('Ecom:admin_return_detail', order_id=order.id)
                    
                    elif action == 'mark_refund_completed':
                        mark_refund_completed(order, request)
                        messages.success(request, f'Refund marked as completed for Order #{order.order_number}')
                    
                    elif action == 'complete_return':
                        complete_return(order, request)
                        messages.success(request, f'Return completed for Order #{order.order_number}')
                    
                    return redirect('Ecom:admin_return_detail', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
                logger.error(f"Return action error for Order #{order.order_number}: {str(e)}")
    
    else:
        # Pre-fill bank details from customer if available
        initial_data = {}
        if order.return_bank_details:
            initial_data['bank_details'] = order.return_bank_details
        form = AdminReturnActionForm(initial=initial_data)
    
    context = {
        'order': order,
        'form': form,
        'items': order.items.all(),
        'transactions': order.transactions.all(),
        'return_images': order.return_images,
    }
    return render(request, 'Ecom/admin/return_detail.html', context)

# ============================================
# ADMIN - REPLACEMENT REQUESTS
# ============================================
# views.py - Updated admin_replacement_requests_view

@staff_member_required
def admin_replacement_requests_view(request):
    """Admin view to manage replacement requests"""
    # Exclude completed replacements
    replacements = Order.objects.filter(
        replacement_requested=True,
        replacement_completed=False,  # Not completed
    ).select_related('user').order_by('-replacement_requested_at')
    
    # Also exclude if order is cancelled
    replacements = replacements.exclude(status='cancelled')
    
    stats = {
        'pending': replacements.filter(replacement_approved=False, replacement_rejected=False).count(),
        'approved': replacements.filter(replacement_approved=True, replacement_completed=False).count(),
        'rejected': replacements.filter(replacement_rejected=True).count(),
        'completed': Order.objects.filter(replacement_requested=True, replacement_completed=True).count(),
        'total': replacements.count(),
    }
    
    status_filter = request.GET.get('status', '')
    if status_filter == 'pending':
        replacements = replacements.filter(replacement_approved=False, replacement_rejected=False)
    elif status_filter == 'approved':
        replacements = replacements.filter(replacement_approved=True, replacement_completed=False)
    elif status_filter == 'rejected':
        replacements = replacements.filter(replacement_rejected=True)
    elif status_filter == 'completed':
        # For completed, show all completed replacements
        replacements = Order.objects.filter(replacement_requested=True, replacement_completed=True)
    else:
        # Default: show all active replacements
        replacements = Order.objects.filter(
            replacement_requested=True,
            replacement_completed=False,
        ).exclude(status='cancelled')
    
    context = {
        'replacements': replacements,
        'stats': stats,
        'status_filter': status_filter,
    }
    return render(request, 'Ecom/admin/replacement_requests.html', context)

@staff_member_required
def admin_replacement_detail_view(request, order_id):
    """Admin view to handle individual replacement request"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        form = AdminReplacementActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('notes', '')
            
            try:
                with transaction.atomic():
                    if action == 'approve':
                        replacement_order = approve_replacement(order, request)
                        messages.success(request, f'Replacement approved for Order #{order.order_number}. New order: #{replacement_order.order_number}')
                    
                    elif action == 'reject':
                        reject_replacement(order, notes or 'No reason provided', request)
                        messages.success(request, f'Replacement rejected for Order #{order.order_number}')
                    
                    elif action == 'mark_shipped':
                        if order.replacement_order:
                            order.replacement_order.status = 'shipped'
                            order.replacement_order.save()
                            messages.success(request, f'Replacement order #{order.replacement_order.order_number} marked as shipped')
                        else:
                            messages.error(request, 'No replacement order found')
                    
                    elif action == 'mark_delivered':
                        if order.replacement_order:
                            order.replacement_order.status = 'delivered'
                            order.replacement_order.delivery_date = timezone.now()
                            order.replacement_order.save()
                            messages.success(request, f'Replacement order #{order.replacement_order.order_number} marked as delivered')
                        else:
                            messages.error(request, 'No replacement order found')
                    
                    elif action == 'complete_replacement':
                        complete_replacement(order, request)
                        messages.success(request, f'Replacement completed for Order #{order.order_number}')
                    
                    return redirect('Ecom:admin_replacement_detail', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    
    else:
        form = AdminReplacementActionForm()
    
    context = {
        'order': order,
        'form': form,
        'items': order.items.all(),
        'replacement_order': order.replacement_order,
        'replacement_images': order.replacement_images,
    }
    return render(request, 'Ecom/admin/replacement_detail.html', context)

