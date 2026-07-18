import random
import os
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import OTP, Order, OrderItem, Transaction, User

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

# utils.py - Add these functions

import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import razorpay
import os
import uuid
from PIL import Image

logger = logging.getLogger(__name__)

# ============================================
# IMAGE HANDLING
# ============================================

def save_return_images(images, order_number):
    """Save return/replacement images and return URLs"""
    image_urls = []
    
    # Create directory if it doesn't exist
    folder_path = f"returns/{order_number}/"
    
    for image in images:
        # Generate unique filename
        ext = os.path.splitext(image.name)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(folder_path, filename)
        
        # Save image using default storage
        saved_path = default_storage.save(file_path, ContentFile(image.read()))
        url = default_storage.url(saved_path)
        image_urls.append(url)
    
    return image_urls

# ============================================
# CANCELLATION LOGIC
# ============================================

def process_cancellation(order, reason, request):
    """Process cancellation request"""
    with transaction.atomic():
        order.cancellation_requested = True
        order.cancellation_requested_at = timezone.now()
        order.cancellation_reason = reason
        order.save()
        
        send_cancellation_request_email(order, request)
        logger.info(f"Cancellation requested for Order #{order.order_number}")
        return True


def approve_cancellation(order, refund_method, bank_details, notes, request):
    """Approve cancellation and initiate refund"""
    with transaction.atomic():
        old_status = order.status
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.save()
        
        # Update stock - add back the quantity
        restore_order_stock(order)
        
        # Initiate refund
        if order.payment_status == 'paid':
            success, message = initiate_refund(
                order, 
                order.total_amount, 
                refund_method, 
                bank_details, 
                f"Order cancelled. {notes}" if notes else "Order cancelled",
                request
            )
            if not success:
                logger.warning(f"Refund failed for cancelled order #{order.order_number}: {message}")
        
        send_cancellation_approved_email(order, refund_method, request)
        logger.info(f"Cancellation approved for Order #{order.order_number}")
        return True


def reject_cancellation(order, reason, request):
    """Reject cancellation request"""
    with transaction.atomic():
        order.cancellation_requested = False
        order.cancellation_reason = reason
        order.save()
        
        send_cancellation_rejected_email(order, reason, request)
        logger.info(f"Cancellation rejected for Order #{order.order_number}")
        return True


# ============================================
# RETURN LOGIC (Full Order)
# ============================================

# utils.py - Updated process_return_request

def process_return_request(order, reason, description, bank_details, images, request):
    """Process return request for full order with bank details"""
    with transaction.atomic():
        order.return_requested = True
        order.return_requested_at = timezone.now()
        order.return_reason = reason
        order.return_description = description
        order.return_bank_details = bank_details  # Save to return_bank_details
        
        # Save images
        if images:
            image_urls = save_return_images(images, order.order_number)
            order.return_images = image_urls
        
        order.save()
        
        # Send email to customer
        send_return_request_email(order, request)
        logger.info(f"Return requested for Order #{order.order_number} with bank details")
        return True
    
def approve_return(order, request):
    """Approve return request"""
    with transaction.atomic():
        order.return_approved = True
        order.return_approved_at = timezone.now()
        order.save()
        
        send_return_approved_email(order, request)
        logger.info(f"Return approved for Order #{order.order_number}")
        return True


def reject_return(order, reason, request):
    """Reject return request"""
    with transaction.atomic():
        order.return_requested = False
        order.return_rejected = True
        order.return_rejected_at = timezone.now()
        order.return_rejection_reason = reason
        order.save()
        
        send_return_rejected_email(order, reason, request)
        logger.info(f"Return rejected for Order #{order.order_number}")
        return True


def mark_return_items_received(order, request):
    """Mark return items as received"""
    with transaction.atomic():
        order.return_items_received = True
        order.return_items_received_at = timezone.now()
        order.save()
        
        # Restore stock when items are received
        restore_order_stock(order)
        
        send_return_received_email(order, request)
        logger.info(f"Return items received for Order #{order.order_number}")
        return True


def complete_return(order, request):
    """Complete the return process"""
    with transaction.atomic():
        order.return_completed = True
        order.return_completed_at = timezone.now()
        order.status='returned'
        order.save()
        
        send_return_completed_email(order, request)
        logger.info(f"Return completed for Order #{order.order_number}")
        return True


# ============================================
# REPLACEMENT LOGIC (Full Order)
# ============================================

def process_replacement_request(order, reason, description, images, request):
    """Process replacement request for full order"""
    with transaction.atomic():
        order.replacement_requested = True
        order.replacement_requested_at = timezone.now()
        order.replacement_reason = reason
        order.replacement_description = description
        
        if images:
            image_urls = save_return_images(images, order.order_number)
            order.replacement_images = image_urls
        
        order.save()
        
        send_replacement_request_email(order, request)
        logger.info(f"Replacement requested for Order #{order.order_number}")
        return True


def approve_replacement(order, request):
    """Approve replacement and create new order"""
    with transaction.atomic():
        order.replacement_approved = True
        order.replacement_approved_at = timezone.now()
        order.save()
        
        # Create replacement order
        replacement_order = create_replacement_order(order, request)
        order.replacement_order = replacement_order
        order.save()
        
        send_replacement_approved_email(order, replacement_order, request)
        logger.info(f"Replacement approved for Order #{order.order_number}")
        return replacement_order


def reject_replacement(order, reason, request):
    """Reject replacement request"""
    with transaction.atomic():
        order.replacement_requested = False
        order.replacement_rejected = True
        order.replacement_rejected_at = timezone.now()
        order.replacement_rejection_reason = reason
        order.save()
        
        send_replacement_rejected_email(order, reason, request)
        logger.info(f"Replacement rejected for Order #{order.order_number}")
        return True


def create_replacement_order(original_order, request):
    """Create a new order for replacement (free)"""
    new_order = Order.objects.create(
        user=original_order.user,
        order_number=f"REP-{original_order.order_number}",
        subtotal=original_order.subtotal,
        total_amount=Decimal('0'),  # Free replacement
        shipping_address=original_order.shipping_address,
        billing_address=original_order.billing_address,
        status='processing',
        payment_status='paid',  # Already paid
        notes=f"Replacement order for Order #{original_order.order_number}"
    )
    
    # Copy order items with zero cost
    for item in original_order.items.all():
        OrderItem.objects.create(
            order=new_order,
            product=item.product,
            variant=item.variant,
            product_name=item.product_name,
            sku=item.sku,
            quantity=item.quantity,
            original_price=item.original_price,
            final_price=Decimal('0'),  # Free replacement
            total=Decimal('0'),
            product_discount=Decimal('0'),
            offer_discount=Decimal('0'),
        )
    
    send_replacement_order_created_email(new_order, original_order, request)
    return new_order


def complete_replacement(order, request):
    """Complete replacement process"""
    with transaction.atomic():
        order.replacement_completed = True
        order.replacement_completed_at = timezone.now()
        order.status = 'replaced'
        order.save()
        
        if order.replacement_order:
            order.replacement_order.status = 'delivered'
            order.replacement_order.delivery_date = timezone.now()
            order.replacement_order.save()
        
        send_replacement_completed_email(order, request)
        logger.info(f"Replacement completed for Order #{order.order_number}")
        return True


# ============================================
# REFUND LOGIC
# ============================================
# utils.py - Fixed initiate_refund function

def initiate_refund(order, amount, refund_method, bank_details=None, notes=None, request=None):
    """
    Initiate refund via Razorpay or Manual Bank Transfer
    
    Args:
        order: Order object
        amount: Refund amount (if None, uses order.total_amount)
        refund_method: 'razorpay' or 'manual'
        bank_details: Bank details for manual transfer
        notes: Additional notes
        request: HttpRequest object for email generation
    """
    
    # CRITICAL FIX: If amount is None or 0, use order.total_amount
    if amount is None or amount <= 0:
        amount = order.total_amount
        logger.info(f"Using order total amount ₹{amount} for refund of Order #{order.order_number}")
    
    # Ensure amount is a valid Decimal
    try:
        amount = Decimal(str(amount))
    except (ValueError, TypeError):
        amount = order.total_amount
        logger.warning(f"Invalid refund amount, using order total ₹{amount}")
    
    if amount <= 0:
        return False, "Refund amount must be greater than 0"
    
    if refund_method == 'razorpay':
        return initiate_razorpay_refund(order, amount, notes, request)
    elif refund_method == 'manual':
        return initiate_manual_refund(order, amount, bank_details, notes, request)
    return False, "Invalid refund method"

# utils.py - Updated initiate_refund function
# utils.py - Fixed initiate_razorpay_refund function

def initiate_razorpay_refund(order, amount, notes=None, request=None):
    """
    Initiate auto-refund via Razorpay
    
    Args:
        order: Order object
        amount: Refund amount (should be Decimal)
        notes: Additional notes
        request: HttpRequest object for email generation
    """
    # Check if payment ID exists
    if not order.razorpay_payment_id:
        return False, "No payment ID found for this order"
    
    # Ensure amount is not None
    if amount is None:
        amount = order.total_amount
        logger.info(f"Using order total amount ₹{amount} for Razorpay refund")
    
    # Ensure amount is Decimal
    if not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            amount = order.total_amount
    
    if amount <= 0:
        return False, "Refund amount must be greater than 0"
    
    try:
        # Convert to paise (Razorpay expects amount in paise)
        amount_float = float(amount)
        amount_paise = int(amount_float * 100)
        
        if amount_paise <= 0:
            return False, "Refund amount must be greater than 0"
        
        # Initialize Razorpay client
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        
        # Call Razorpay refund API
        refund = razorpay_client.payment.refund(
            order.razorpay_payment_id,
            {
                'amount': amount_paise,
                'speed': 'normal',
                'notes': {
                    'order_number': order.order_number,
                    'reason': notes or 'Return/Refund',
                    'user_email': order.user.email
                }
            }
        )
        
        # Update order with refund details
        with transaction.atomic():
            order.refund_requested = True
            order.refund_requested_at = timezone.now()
            order.refund_approved = True
            order.refund_approved_at = timezone.now()
            order.refund_amount = amount
            order.refund_transaction_id = refund.get('id')
            order.refund_method = 'razorpay'
            order.refund_notes = notes or ''
            
            # If customer provided bank details, store them in refund_bank_details
            if hasattr(order, 'return_bank_details') and order.return_bank_details:
                order.refund_bank_details = order.return_bank_details
            
            order.payment_status = 'refunded'
            order.save()
            
            # Create transaction record
            Transaction.objects.create(
                order=order,
                transaction_type='refund',
                razorpay_transaction_id=refund.get('id'),
                razorpay_payment_id=order.razorpay_payment_id,
                razorpay_refund_id=refund.get('id'),
                amount=amount,
                status='success',
                response_data=refund,
                notes=f'Razorpay refund initiated: {notes}'
            )
        
        # Send email notification
        send_refund_confirmation_email(order, amount, 'razorpay', request)
        
        return True, f"Refund of ₹{amount:.2f} initiated via Razorpay"
        
    except Exception as e:
        logger.error(f"Razorpay refund failed for Order #{order.order_number}: {str(e)}")
        return False, f"Refund failed: {str(e)}"
    
# utils.py - Fixed initiate_manual_refund function

def initiate_manual_refund(order, amount, bank_details, notes=None, request=None):
    """
    Initiate manual bank transfer refund
    
    Args:
        order: Order object
        amount: Refund amount (should be Decimal)
        bank_details: Bank details for manual transfer
        notes: Additional notes
        request: HttpRequest object for email generation
    """
    # Ensure amount is not None
    if amount is None:
        amount = order.total_amount
        logger.info(f"Using order total amount ₹{amount} for manual refund")
    
    # Ensure amount is Decimal
    if not isinstance(amount, Decimal):
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            amount = order.total_amount
    
    if amount <= 0:
        return False, "Refund amount must be greater than 0"
    
    with transaction.atomic():
        order.refund_requested = True
        order.refund_requested_at = timezone.now()
        order.refund_approved = True
        order.refund_approved_at = timezone.now()
        order.refund_amount = amount
        order.refund_method = 'manual'
        order.refund_bank_details = bank_details or order.return_bank_details
        order.refund_notes = notes or ''
        order.payment_status = 'refunded'
        order.save()
        
        # Create transaction record
        Transaction.objects.create(
            order=order,
            transaction_type='refund',
            amount=amount,
            status='success',
            notes=f'Manual refund initiated. Bank details provided.'
        )
    
    # Send manual refund instructions email
    send_manual_refund_instructions(order, amount, bank_details or order.return_bank_details, request)
    
    return True, f"Manual refund of ₹{amount:.2f} initiated. Please process bank transfer."

def mark_refund_completed(order, request):
    """Mark refund as completed"""
    with transaction.atomic():
        order.refund_completed = True
        order.refund_completed_at = timezone.now()
        order.save()
        
        send_refund_completed_email(order, request)
        logger.info(f"Refund completed for Order #{order.order_number}")
        return True


# ============================================
# STOCK MANAGEMENT
# ============================================

def restore_order_stock(order):
    """Restore stock for all items in the order"""
    from .models import Product, ProductVariant, InventoryLog
    
    for item in order.items.all():
        try:
            if item.variant:
                # Update variant stock
                variant = ProductVariant.objects.select_for_update().get(id=item.variant.id)
                old_stock = variant.stock_quantity
                variant.stock_quantity += item.quantity
                variant.save()
                
                # Update parent product stock
                if variant.product:
                    product = Product.objects.select_for_update().get(id=variant.product.id)
                    product.stock_quantity += item.quantity
                    product.save()
                    
                    InventoryLog.objects.create(
                        product=product,
                        variant=variant,
                        quantity_change=item.quantity,
                        previous_quantity=old_stock,
                        new_quantity=variant.stock_quantity,
                        action='return',
                        note=f'Stock restored from Order #{order.order_number}',
                        created_by=None
                    )
            elif item.product:
                product = Product.objects.select_for_update().get(id=item.product.id)
                old_stock = product.stock_quantity
                product.stock_quantity += item.quantity
                product.save()
                
                InventoryLog.objects.create(
                    product=product,
                    quantity_change=item.quantity,
                    previous_quantity=old_stock,
                    new_quantity=product.stock_quantity,
                    action='return',
                    note=f'Stock restored from Order #{order.order_number}',
                    created_by=None
                )
        except Exception as e:
            logger.error(f"Failed to restore stock for item {item.id}: {str(e)}")
            raise


# ============================================
# EMAIL FUNCTIONS
# ============================================

def send_cancellation_request_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Cancellation Request Received - Order #{order.order_number}',
        'emails/cancellation_requested.html',
        context,
        [order.user.email],
        request
    )


def send_cancellation_approved_email(order, refund_method, request):
    context = {
        'order': order, 
        'user': order.user,
        'refund_method': refund_method
    }
    send_email_template(
        f'Order Cancelled - Order #{order.order_number}',
        'emails/cancellation_approved.html',
        context,
        [order.user.email],
        request
    )


def send_cancellation_rejected_email(order, reason, request):
    context = {'order': order, 'user': order.user, 'reason': reason}
    send_email_template(
        f'Cancellation Request Rejected - Order #{order.order_number}',
        'emails/cancellation_rejected.html',
        context,
        [order.user.email],
        request
    )


def send_return_request_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Return Request Received - Order #{order.order_number}',
        'emails/return_requested.html',
        context,
        [order.user.email],
        request
    )


def send_return_approved_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Return Approved - Order #{order.order_number}',
        'emails/return_approved.html',
        context,
        [order.user.email],
        request
    )


def send_return_rejected_email(order, reason, request):
    context = {'order': order, 'user': order.user, 'reason': reason}
    send_email_template(
        f'Return Request Rejected - Order #{order.order_number}',
        'emails/return_rejected.html',
        context,
        [order.user.email],
        request
    )


def send_return_received_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Return Items Received - Order #{order.order_number}',
        'emails/return_received.html',
        context,
        [order.user.email],
        request
    )


def send_return_completed_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Return Completed - Order #{order.order_number}',
        'emails/return_completed.html',
        context,
        [order.user.email],
        request
    )


def send_replacement_request_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Replacement Request Received - Order #{order.order_number}',
        'emails/replacement_requested.html',
        context,
        [order.user.email],
        request
    )


def send_replacement_approved_email(order, replacement_order, request):
    context = {
        'order': order, 
        'user': order.user,
        'replacement_order': replacement_order
    }
    send_email_template(
        f'Replacement Approved - Order #{order.order_number}',
        'emails/replacement_approved.html',
        context,
        [order.user.email],
        request
    )


def send_replacement_rejected_email(order, reason, request):
    context = {'order': order, 'user': order.user, 'reason': reason}
    send_email_template(
        f'Replacement Request Rejected - Order #{order.order_number}',
        'emails/replacement_rejected.html',
        context,
        [order.user.email],
        request
    )


def send_replacement_order_created_email(new_order, original_order, request):
    context = {
        'new_order': new_order,
        'original_order': original_order,
        'user': original_order.user
    }
    send_email_template(
        f'Replacement Order Created - Order #{new_order.order_number}',
        'emails/replacement_order_created.html',
        context,
        [original_order.user.email],
        request
    )


def send_replacement_completed_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Replacement Completed - Order #{order.order_number}',
        'emails/replacement_completed.html',
        context,
        [order.user.email],
        request
    )


def send_refund_confirmation_email(order, amount, method, request):
    context = {
        'order': order, 
        'user': order.user,
        'amount': amount,
        'method': method
    }
    send_email_template(
        f'Refund Initiated - Order #{order.order_number}',
        'emails/refund_initiated.html',
        context,
        [order.user.email],
        request
    )


def send_manual_refund_instructions(order, amount, bank_details, request):
    context = {
        'order': order, 
        'user': order.user,
        'amount': amount,
        'bank_details': bank_details
    }
    send_email_template(
        f'Manual Refund Instructions - Order #{order.order_number}',
        'emails/manual_refund_instructions.html',
        context,
        [order.user.email],
        request
    )


def send_refund_completed_email(order, request):
    context = {'order': order, 'user': order.user}
    send_email_template(
        f'Refund Completed - Order #{order.order_number}',
        'emails/refund_completed.html',
        context,
        [order.user.email],
        request
    )


def send_email_template(subject, template, context, to_emails, request):
    """Generic email sender"""
    try:
        context.update({
            'site_name': 'MyStore',
            'site_url': request.build_absolute_uri('/') if request else '',
            'support_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@mystore.com')
        })
        
        html_content = render_to_string(template, context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_emails,
            reply_to=[settings.DEFAULT_FROM_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False
    

# utils.py - Helper function for filtering active requests

def get_active_orders(model, request_type, exclude_statuses=None):
    """
    Get active orders for admin views
    
    Args:
        model: Order model
        request_type: 'cancellation', 'return', or 'replacement'
        exclude_statuses: List of statuses to exclude (default: ['cancelled'])
    
    Returns:
        QuerySet of active orders
    """
    if exclude_statuses is None:
        exclude_statuses = ['cancelled']
    
    # Base filter
    if request_type == 'cancellation':
        queryset = model.objects.filter(
            cancellation_requested=True,
            cancelled_at__isnull=True,
            refund_completed=False,
        )
    elif request_type == 'return':
        queryset = model.objects.filter(
            return_requested=True,
            return_completed=False,
        )
    elif request_type == 'replacement':
        queryset = model.objects.filter(
            replacement_requested=True,
            replacement_completed=False,
        )
    else:
        return model.objects.none()
    
    # Exclude statuses
    for status in exclude_statuses:
        if status == 'cancelled':
            queryset = queryset.exclude(status='cancelled')
    
    return queryset