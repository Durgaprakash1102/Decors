from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import *
from .utils import delete_file_if_exists

User = get_user_model()

@receiver(pre_delete, sender=User)
def delete_user_related_files(sender, instance, **kwargs):
    """Delete profile picture when user is deleted"""
    if hasattr(instance, 'profile') and instance.profile.profile_picture:
        delete_file_if_exists(instance.profile.profile_picture.name)

@receiver(pre_delete, sender=Profile)
def delete_profile_picture(sender, instance, **kwargs):
    """Delete profile picture when profile is deleted"""
    if instance.profile_picture:
        delete_file_if_exists(instance.profile_picture.name)

@receiver(pre_delete, sender=Address)
def delete_address_related_files(sender, instance, **kwargs):
    """Delete any associated files when address is deleted"""
    pass

from django.db.models.signals import pre_save, post_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.db import models
from .models import Order, Coupon, Offer, Cart, CartItem
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# ============================================
# HELPER FUNCTIONS
# ============================================

def cleanup_expired_pending_orders(user=None):
    """
    Delete pending orders older than 30 minutes
    """
    expiry_time = timezone.now() - timedelta(minutes=30)
    
    queryset = Order.objects.filter(
        payment_status='pending',
        created_at__lt=expiry_time
    )
    
    if user:
        queryset = queryset.filter(user=user)
    
    count = queryset.count()
    if count > 0:
        # Delete orders and their related items (cascade)
        queryset.delete()
        logger.info(f"Deleted {count} expired pending orders" + (f" for user {user.email}" if user else ""))
    
    return count


def deactivate_expired_coupons():
    """
    Deactivate coupons that have expired or reached usage limit
    """
    now = timezone.now()
    
    # Deactivate expired coupons
    expired_count = Coupon.objects.filter(
        is_active=True,
        valid_to__lt=now
    ).update(is_active=False)
    
    # Deactivate coupons that reached usage limit
    limit_reached_count = Coupon.objects.filter(
        is_active=True,
        usage_limit__isnull=False,
        used_count__gte=models.F('usage_limit')
    ).update(is_active=False)
    
    total = expired_count + limit_reached_count
    if total > 0:
        logger.info(f"Deactivated {expired_count} expired coupons and {limit_reached_count} coupons that reached usage limit")
    
    return total


def deactivate_expired_offers():
    """
    Deactivate offers that have expired
    """
    now = timezone.now()
    
    count = Offer.objects.filter(
        is_active=True,
        valid_to__lt=now
    ).update(is_active=False)
    
    if count > 0:
        logger.info(f"Deactivated {count} expired offers")
    
    return count


def cleanup_user_cart(user):
    """
    Clean up cart items that are out of stock or inactive
    """
    cart = Cart.objects.filter(user=user).first()
    if cart:
        # Remove items that are out of stock or inactive
        for item in cart.items.all():
            if item.product and (not item.product.is_active or item.product.is_out_of_stock):
                item.delete()
                logger.info(f"Removed inactive/out-of-stock item {item.product.name} from cart")
            elif item.variant and (not item.variant.is_active or item.variant.is_out_of_stock):
                item.delete()
                logger.info(f"Removed inactive/out-of-stock variant {item.variant.sku} from cart")


def full_cleanup(user=None):
    """
    Run all cleanup operations
    """
    results = {
        'orders_deleted': cleanup_expired_pending_orders(user),
        'coupons_deactivated': deactivate_expired_coupons(),
        'offers_deactivated': deactivate_expired_offers(),
    }
    
    if user:
        cleanup_user_cart(user)
    
    return results


# ============================================
# USER LOGIN SIGNAL
# ============================================

@receiver(user_logged_in)
def cleanup_on_login(sender, request, user, **kwargs):
    """
    Clean up expired orders, coupons, offers when user logs in
    """
    full_cleanup(user)
    logger.info(f"Cleanup completed for user {user.email} after login")


# ============================================
# USER LOGOUT SIGNAL
# ============================================

@receiver(user_logged_out)
def cleanup_on_logout(sender, request, user, **kwargs):
    """
    Clean up when user logs out (if user exists)
    """
    if user:
        # Only cleanup orders for this user
        cleanup_expired_pending_orders(user)
        logger.info(f"Cleanup completed for user {user.email} after logout")


# ============================================
# ORDER SIGNALS
# ============================================

@receiver(pre_save, sender=Order)
def cleanup_before_order_creation(sender, instance, **kwargs):
    """
    Clean up before creating a new order
    """
    if instance.pk is None:  # New order being created
        # Clean up expired orders for this user
        cleanup_expired_pending_orders(instance.user)
        # Clean up expired coupons and offers globally
        deactivate_expired_coupons()
        deactivate_expired_offers()
        logger.info(f"Cleanup completed before order creation for user {instance.user.email}")


@receiver(post_save, sender=Order)
def check_order_expiry(sender, instance, created, **kwargs):
    """
    Check if order is pending and set expiry check
    """
    if instance.payment_status == 'pending':
        # If order is pending, schedule for cleanup if not paid within 30 mins
        # This is handled by the cleanup_expired_pending_orders function
        pass


# ============================================
# COUPON SIGNALS
# ============================================

@receiver(pre_save, sender=Coupon)
def check_coupon_expiry(sender, instance, **kwargs):
    """
    Auto-deactivate expired coupons before saving
    """
    now = timezone.now()
    
    # Check if coupon is expired
    if instance.valid_to and instance.valid_to < now:
        instance.is_active = False
        logger.info(f"Coupon {instance.code} expired and deactivated")
    
    # Check if coupon reached usage limit
    if instance.usage_limit and instance.used_count >= instance.usage_limit:
        instance.is_active = False
        logger.info(f"Coupon {instance.code} reached usage limit and deactivated")


@receiver(post_save, sender=Coupon)
def coupon_usage_updated(sender, instance, created, **kwargs):
    """
    Check coupon status after usage count updates
    """
    if not created:
        # If used_count changed, check if limit reached
        if instance.usage_limit and instance.used_count >= instance.usage_limit:
            if instance.is_active:
                instance.is_active = False
                instance.save(update_fields=['is_active'])
                logger.info(f"Coupon {instance.code} deactivated after reaching usage limit")


# ============================================
# OFFER SIGNALS
# ============================================

@receiver(pre_save, sender=Offer)
def check_offer_expiry(sender, instance, **kwargs):
    """
    Auto-deactivate expired offers before saving
    """
    now = timezone.now()
    
    # Check if offer is expired
    if instance.valid_to and instance.valid_to < now:
        instance.is_active = False
        logger.info(f"Offer {instance.name} expired and deactivated")


# ============================================
# PRODUCT SIGNALS (Cleanup cart when product changes)
# ============================================

@receiver(post_save, sender=Product)
def cleanup_cart_on_product_change(sender, instance, **kwargs):
    """
    Remove product from carts if it becomes inactive or out of stock
    """
    if not instance.is_active or instance.is_out_of_stock:
        # Find all cart items with this product
        cart_items = CartItem.objects.filter(product=instance)
        count = cart_items.count()
        if count > 0:
            cart_items.delete()
            logger.info(f"Removed {count} cart items for product {instance.name} (inactive/out of stock)")


@receiver(post_save, sender=ProductVariant)
def cleanup_cart_on_variant_change(sender, instance, **kwargs):
    """
    Remove variant from carts if it becomes inactive or out of stock
    """
    if not instance.is_active or instance.is_out_of_stock:
        cart_items = CartItem.objects.filter(variant=instance)
        count = cart_items.count()
        if count > 0:
            cart_items.delete()
            logger.info(f"Removed {count} cart items for variant {instance.sku} (inactive/out of stock)")


# ============================================
# PERIODIC CLEANUP (Triggered on page visits)
# ============================================

# You can also add a middleware or context processor to trigger cleanup
# on specific pages. Here's a function you can call from anywhere:

def trigger_cleanup_on_request(request):
    """
    Call this from middleware or context processor
    to trigger cleanup on page visits
    """
    if request.user.is_authenticated:
        # Only run cleanup once per session to reduce overhead
        if not request.session.get('cleanup_done_today'):
            results = full_cleanup(request.user)
            request.session['cleanup_done_today'] = True
            # Set expiry to 1 hour to run again later
            request.session.set_expiry(3600)
            return results
    return None