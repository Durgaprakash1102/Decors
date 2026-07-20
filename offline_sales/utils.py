# offline_sales/utils.py - Fixed barcode generation
from django.db import models
import uuid
import os
import logging
from io import BytesIO
from decimal import Decimal
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    barcode = None

logger = logging.getLogger(__name__)


def generate_barcode_image(product_or_variant, barcode_text=None):
    """
    Generate barcode image for product or variant
    """
    if not BARCODE_AVAILABLE:
        logger.error("python-barcode not installed. Install with: pip install python-barcode pillow")
        return None
    
    from .models import ProductBarcode
    from Ecom.models import Product, ProductVariant
    
    # Determine type
    is_product = isinstance(product_or_variant, Product)
    is_variant = isinstance(product_or_variant, ProductVariant)
    
    if not barcode_text:
        if is_product:
            prefix = "PR"
            barcode_text = f"{prefix}-{product_or_variant.id:06d}-{uuid.uuid4().hex[:6].upper()}"
        elif is_variant:
            prefix = "VR"
            barcode_text = f"{prefix}-{product_or_variant.id:06d}-{uuid.uuid4().hex[:6].upper()}"
        else:
            return None
    
    try:
        # Generate Code128 barcode
        code128 = barcode.get_barcode_class('code128')
        barcode_obj = code128(barcode_text, writer=ImageWriter())
        
        # Save to BytesIO
        buffer = BytesIO()
        barcode_obj.write(buffer, {
            'format': 'PNG',
            'dpi': 300,
            'module_width': 0.2,
            'module_height': 10,
            'font_size': 10,
            'text_distance': 5,
        })
        buffer.seek(0)
        
        # Create filename
        filename = f"barcode_{uuid.uuid4().hex[:8]}.png"
        folder_path = f"barcodes/"
        
        # Ensure directory exists
        if not os.path.exists(os.path.join(settings.MEDIA_ROOT, folder_path)):
            os.makedirs(os.path.join(settings.MEDIA_ROOT, folder_path))
        
        # Save file
        file_path = os.path.join(folder_path, filename)
        saved_path = default_storage.save(file_path, ContentFile(buffer.getvalue()))
        
        # Save to model
        barcode_model = ProductBarcode.objects.create(
            product=product_or_variant if is_product else None,
            variant=product_or_variant if is_variant else None,
            barcode_type='product' if is_product else 'variant',
            barcode_text=barcode_text,
            barcode_image=saved_path
        )
        
        return barcode_model
        
    except Exception as e:
        logger.error(f"Barcode generation failed: {str(e)}")
        return None


def generate_product_barcode(product):
    """Generate barcode for a product"""
    from .models import ProductBarcode
    
    # Check if barcode already exists
    existing = ProductBarcode.objects.filter(product=product).first()
    if existing:
        return existing
    
    return generate_barcode_image(product)


def generate_variant_barcode(variant):
    """Generate barcode for a variant"""
    from .models import ProductBarcode
    
    # Check if barcode already exists
    existing = ProductBarcode.objects.filter(variant=variant).first()
    if existing:
        return existing
    
    return generate_barcode_image(variant)


def generate_all_barcodes():
    """Generate barcodes for all products and variants"""
    from Ecom.models import Product, ProductVariant
    
    generated = {'products': 0, 'variants': 0, 'errors': 0}
    
    # Generate for all active products
    for product in Product.objects.filter(is_active=True):
        try:
            if generate_product_barcode(product):
                generated['products'] += 1
            else:
                generated['errors'] += 1
        except Exception as e:
            logger.error(f"Error generating barcode for product {product.id}: {str(e)}")
            generated['errors'] += 1
    
    # Generate for all active variants
    for variant in ProductVariant.objects.filter(is_active=True):
        try:
            if generate_variant_barcode(variant):
                generated['variants'] += 1
            else:
                generated['errors'] += 1
        except Exception as e:
            logger.error(f"Error generating barcode for variant {variant.id}: {str(e)}")
            generated['errors'] += 1
    
    return generated
# ============================================
# OFFER DISCOUNT CALCULATION
# ============================================

def calculate_offer_discount(product, price, variant=None):
    """
    Calculate if any offer applies to this product or variant
    """
    from decimal import Decimal
    from django.utils import timezone
    from Ecom.models import Offer
    
    offers = Offer.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now(),
        valid_to__gte=timezone.now()
    ).order_by('-priority')
    
    best_offer_discount = Decimal('0')
    best_offer_name = None
    
    original_price = Decimal(str(product.price))
    if variant:
        original_price = Decimal(str(variant.price))
    
    if not isinstance(price, Decimal):
        price = Decimal(str(price))
    
    product_discount_amount = original_price - price
    
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
    
    if product_discount_amount == 0 and best_offer_discount == 0:
        return price, None, Decimal('0')
    
    if product_discount_amount > 0 and best_offer_discount == 0:
        return price, "Product Discount", Decimal('0')
    
    if product_discount_amount == 0 and best_offer_discount > 0:
        final_price = original_price - best_offer_discount
        return final_price, best_offer_name, best_offer_discount
    
    if product_discount_amount > 0 and best_offer_discount > 0:
        product_final_price = original_price - product_discount_amount
        offer_final_price = original_price - best_offer_discount
        
        if offer_final_price < product_final_price:
            return offer_final_price, best_offer_name, best_offer_discount
        else:
            return product_final_price, "Product Discount", Decimal('0')
    
    return price, None, Decimal('0')


# ============================================
# INVOICE GENERATION
# ============================================

def generate_invoice_html(order, store_settings):
    """Generate invoice HTML for offline order"""
    items = order.items.all()
    
    context = {
        'order': order,
        'items': items,
        'store': store_settings,
        'subtotal': order.subtotal,
        'discount': order.total_discount,
        'total': order.total_amount,
        'date': order.created_at.strftime('%d %B, %Y %I:%M %p'),
    }
    
    return render_to_string('offline_sales/invoice.html', context)


# ============================================
# EMAIL FUNCTIONS
# ============================================

def send_invoice_email(order, store_settings, request):
    """Send invoice email to customer"""
    try:
        context = {
            'order': order,
            'store': store_settings,
            'items': order.items.all(),
            'subtotal': order.subtotal,
            'discount': order.total_discount,
            'total': order.total_amount,
            'date': order.created_at.strftime('%d %B, %Y %I:%M %p'),
        }
        
        subject = f"Invoice #{order.invoice_number or order.order_number} - {store_settings.store_name}"
        html_content = render_to_string('offline_sales/email/invoice_email.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer_email] if order.customer_email else [],
            reply_to=[settings.DEFAULT_FROM_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False