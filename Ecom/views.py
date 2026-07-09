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