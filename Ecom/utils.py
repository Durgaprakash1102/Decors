import random
import os
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import OTP, User

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def send_otp_email(user_or_email, otp_code, otp_type, full_name='User'):
    """Send OTP via email with proper template"""
    
    # Handle both User object and email string
    if isinstance(user_or_email, User):
        email = user_or_email.email
        name = user_or_email.full_name
    else:
        email = user_or_email
        name = full_name
    
    # Get the appropriate message based on OTP type
    messages = {
        'signup': {
            'subject': 'Welcome! Verify Your Email',
            'heading': 'Email Verification',
            'body': f"Hi {name},<br><br>Thank you for signing up! Please verify your email address to activate your account."
        },
        'login': {
            'subject': 'Login Verification Code',
            'heading': 'Login Verification',
            'body': f"Hi {name},<br><br>You've requested to log in. Please use the OTP below to complete your login."
        },
        'forgot_password': {
            'subject': 'Reset Your Password',
            'heading': 'Password Reset',
            'body': f"Hi {name},<br><br>You've requested to reset your password. Please use the OTP below to set a new password."
        },
        'change_password': {
            'subject': 'Change Password Verification',
            'heading': 'Change Password',
            'body': f"Hi {name},<br><br>You've requested to change your password. Please use the OTP below to confirm."
        },
    }
    
    data = messages.get(otp_type, messages['signup'])
    
    # HTML Email Template
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; padding-bottom: 20px; border-bottom: 2px solid #4CAF50; }}
            .header h1 {{ color: #4CAF50; margin: 0; }}
            .content {{ padding: 20px 0; }}
            .otp-box {{ background-color: #f8f9fa; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #4CAF50; letter-spacing: 5px; }}
            .expiry {{ color: #dc3545; font-size: 14px; text-align: center; margin-top: 10px; }}
            .footer {{ text-align: center; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛍️ MyStore</h1>
            </div>
            <div class="content">
                <h2>{data['heading']}</h2>
                <p>{data['body']}</p>
                <div class="otp-box">
                    <div class="otp-code">{otp_code}</div>
                </div>
                <p style="text-align: center;">This OTP is valid for 5 minutes.</p>
                <p style="text-align: center; color: #666; font-size: 14px;">
                    If you didn't request this, please ignore this email.
                </p>
            </div>
            <div class="footer">
                <p>&copy; 2024 MyStore. All rights reserved.</p>
                <p>This is an automated email, please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text fallback
    text_message = f"""
    {data['heading']}
    
    {data['body']}
    
    Your OTP is: {otp_code}
    
    This OTP is valid for 5 minutes.
    
    If you didn't request this, please ignore this email.
    
    Thanks,
    MyStore Team
    """
    
    send_mail(
        subject=data['subject'],
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=False,
    )

def create_and_send_otp(user_or_email, otp_type, full_name='User'):
    """
    Create an OTP and send it via email.
    Works for both saved users and pending signups.
    """
    if isinstance(user_or_email, User):
        # For existing users
        user = user_or_email
        # Delete existing unused OTPs for this user and type
        OTP.objects.filter(user=user, otp_type=otp_type, is_used=False).delete()
        
        otp_code = generate_otp()
        otp = OTP.objects.create(
            user=user,
            email=user.email,
            otp_code=otp_code,
            otp_type=otp_type,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        send_otp_email(user, otp_code, otp_type)
        return otp
    else:
        # For pending signups (email string)
        email = user_or_email
        # Delete any existing OTPs for this email and type
        OTP.objects.filter(email=email, otp_type=otp_type, is_used=False).delete()
        
        otp_code = generate_otp()
        otp = OTP.objects.create(
            user=None,
            email=email,
            otp_code=otp_code,
            otp_type=otp_type,
            expires_at=timezone.now() + timedelta(minutes=5)
        )
        send_otp_email(email, otp_code, otp_type, full_name)
        return otp

def verify_otp(email, otp_code, otp_type):
    """
    Verify the OTP for a user.
    Returns (is_valid, message, otp_object)
    """
    try:
        otp = OTP.objects.get(
            email=email,
            otp_code=otp_code,
            otp_type=otp_type,
            is_used=False
        )
        
        if otp.is_valid():
            otp.is_used = True
            otp.save()
            return True, "OTP verified successfully", otp
        else:
            return False, "OTP has expired. Please request a new one.", None
            
    except OTP.DoesNotExist:
        return False, "Invalid OTP. Please check and try again.", None

def delete_file_if_exists(file_path):
    """Delete a file from the filesystem if it exists"""
    if file_path:
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                return True
            except OSError:
                return False
    return False

def get_user_by_identifier(identifier):
    """Get user by email or phone number"""
    user = None
    
    # Try as email
    try:
        user = User.objects.get(email=identifier)
        return user
    except User.DoesNotExist:
        pass
    
    # Try as phone
    try:
        user = User.objects.get(phone=identifier)
        return user
    except User.DoesNotExist:
        pass
    
    return None