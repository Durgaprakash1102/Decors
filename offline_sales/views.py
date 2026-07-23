# offline_sales/views.py

import json
import logging
from django.db import models
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.urls import reverse
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from Ecom.models import Product, ProductVariant, User, Offer, InventoryLog

from .models import (
    StoreSettings, ProductBarcode, OfflineCustomer, 
    OfflineOrder, OfflineOrderItem
)
from .forms import (
    StoreSettingsForm, OfflineCustomerForm, OfflineSalePaymentForm
)
from .utils import (
    generate_product_barcode, generate_variant_barcode, generate_all_barcodes,
    calculate_offer_discount, generate_invoice_html, send_invoice_email
)

logger = logging.getLogger(__name__)


# ============================================
# STORE SETTINGS
# ============================================

@staff_member_required
def store_settings_list(request):
    """List store settings"""
    store_settings = StoreSettings.objects.first()
    return render(request, 'offline_sales/admin/store_settings_list.html', {
        'store_settings': store_settings
    })


@staff_member_required
def store_settings_edit(request):
    """Edit store settings"""
    store_settings = StoreSettings.objects.first()
    
    if request.method == 'POST':
        form = StoreSettingsForm(request.POST, request.FILES, instance=store_settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Store settings updated successfully!')
            return redirect('offline_sales:store_settings_list')
    else:
        form = StoreSettingsForm(instance=store_settings)
    
    return render(request, 'offline_sales/admin/store_settings_form.html', {
        'form': form,
        'store_settings': store_settings,
        'action': 'Edit'
    })


# ============================================
# BARCODE VIEWS
# ============================================

@staff_member_required
def barcode_list_view(request):
    """List all barcodes with pending count"""
    from Ecom.models import Product, ProductVariant
    
    barcodes = ProductBarcode.objects.select_related('product', 'variant').all()
    
    # Calculate counts
    total_barcodes = barcodes.count()
    product_barcodes = barcodes.filter(barcode_type='product').count()
    variant_barcodes = barcodes.filter(barcode_type='variant').count()
    
    # Find products without barcodes
    products_without_barcode = Product.objects.filter(
        is_active=True,
        barcodes__isnull=True
    ).values('id', 'name', 'sku')
    
    # Find variants without barcodes
    variants_without_barcode = ProductVariant.objects.filter(
        is_active=True,
        barcodes__isnull=True
    ).select_related('product').values('id', 'product__name', 'sku')
    
    # Prepare pending items list
    pending_products = []
    
    for product in products_without_barcode:
        pending_products.append({
            'id': product['id'],
            'name': product['name'],
            'sku': product['sku'],
            'type': 'product'
        })
    
    for variant in variants_without_barcode:
        pending_products.append({
            'id': variant['id'],
            'name': f"{variant['product__name']} - {variant['sku']}",
            'sku': variant['sku'],
            'type': 'variant'
        })
    
    pending_count = len(pending_products)
    
    # Pagination for barcodes
    paginator = Paginator(barcodes, 20)
    page = request.GET.get('page')
    barcodes_page = paginator.get_page(page)
    
    context = {
        'barcodes': barcodes_page,
        'total_barcodes': total_barcodes,
        'product_barcodes': product_barcodes,
        'variant_barcodes': variant_barcodes,
        'pending_count': pending_count,
        'pending_products': pending_products[:10],
    }
    return render(request, 'offline_sales/admin/barcode_list.html', context)


@staff_member_required
def generate_barcode_view(request, product_id=None, variant_id=None):
    """Generate barcode for a product or variant"""
    try:
        from Ecom.models import Product, ProductVariant
        
        if product_id:
            product = get_object_or_404(Product, id=product_id)
            barcode = generate_product_barcode(product)
            if barcode:
                messages.success(request, f'Barcode generated for {product.name}')
            else:
                messages.error(request, f'Failed to generate barcode for {product.name}')
        elif variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id)
            barcode = generate_variant_barcode(variant)
            if barcode:
                messages.success(request, f'Barcode generated for {variant.sku}')
            else:
                messages.error(request, f'Failed to generate barcode for {variant.sku}')
        else:
            # Generate for all
            result = generate_all_barcodes()
            messages.success(
                request, 
                f'Barcodes generated: {result["products"]} products, {result["variants"]} variants'
            )
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('offline_sales:barcode_list')


@staff_member_required
def download_barcode_view(request, barcode_id):
    """Download barcode image"""
    barcode = get_object_or_404(ProductBarcode, id=barcode_id)
    
    if barcode.barcode_image and barcode.barcode_image.storage.exists(barcode.barcode_image.name):
        response = HttpResponse(barcode.barcode_image.read(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="{barcode.barcode_text}.png"'
        return response
    
    messages.error(request, 'Barcode image not found.')
    return redirect('offline_sales:barcode_list')


@staff_member_required
def delete_barcode_view(request, barcode_id):
    """Delete a barcode"""
    barcode = get_object_or_404(ProductBarcode, id=barcode_id)
    barcode.delete()
    messages.success(request, 'Barcode deleted successfully.')
    return redirect('offline_sales:barcode_list')


# ============================================
# SCAN BARCODE VIEW (AJAX)
# ============================================

@csrf_exempt
@staff_member_required
def scan_barcode_view(request):
    """AJAX view to scan barcode and return product details"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            barcode_text = data.get('barcode_text', '').strip()
            
            if not barcode_text:
                return JsonResponse({'success': False, 'error': 'No barcode provided'})
            
            barcode = ProductBarcode.objects.filter(barcode_text=barcode_text).first()
            
            if not barcode:
                return JsonResponse({'success': False, 'error': 'Product not found'})
            
            product_data = {}
            
            if barcode.product:
                product = barcode.product
                product_data = {
                    'id': product.id,
                    'name': product.name,
                    'sku': product.sku,
                    'price': str(product.final_price),
                    'original_price': str(product.price),
                    'discount_percentage': str(product.discount_percentage),
                    'stock': product.stock_quantity,
                    'image': product.main_image,
                    'type': 'product',
                    'barcode_text': barcode.barcode_text,
                    'has_variants': product.variants.filter(is_active=True).exists()
                }
            elif barcode.variant:
                variant = barcode.variant
                product_data = {
                    'id': variant.id,
                    'name': f"{variant.product.name} - {variant.name or variant.sku}",
                    'sku': variant.sku,
                    'price': str(variant.final_price),
                    'original_price': str(variant.price),
                    'discount_percentage': str(variant.discount_percentage),
                    'stock': variant.stock_quantity,
                    'image': variant.main_image or variant.product.main_image,
                    'type': 'variant',
                    'product_id': variant.product.id,
                    'barcode_text': barcode.barcode_text,
                    'color': variant.color,
                    'size': variant.size,
                }
            
            return JsonResponse({
                'success': True, 
                'product': product_data,
                'message': 'Product found successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ============================================
# PRODUCT SEARCH
# ============================================

@staff_member_required
def product_search_view(request):
    """
    Search for products for offline sale (AJAX)
    Supports searching by name, SKU, description, and barcode
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    results = []
    
    # 1. SEARCH BY BARCODE FIRST (Exact match)
    barcode = ProductBarcode.objects.filter(barcode_text__icontains=query).first()
    if barcode:
        if barcode.product:
            product = barcode.product
            results.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'price': str(product.final_price),
                'original_price': str(product.price),
                'discount_percentage': str(product.discount_percentage),
                'image': product.main_image,
                'type': 'product',
                'barcode_text': barcode.barcode_text,
                'stock': product.stock_quantity,
                'has_variants': product.variants.filter(is_active=True).exists()
            })
        elif barcode.variant:
            variant = barcode.variant
            results.append({
                'id': variant.id,
                'name': f"{variant.product.name} - {variant.name or variant.sku}",
                'sku': variant.sku,
                'price': str(variant.final_price),
                'original_price': str(variant.price),
                'discount_percentage': str(variant.discount_percentage),
                'image': variant.main_image or variant.product.main_image,
                'type': 'variant',
                'barcode_text': barcode.barcode_text,
                'stock': variant.stock_quantity,
                'product_id': variant.product.id,
                'color': variant.color,
                'size': variant.size,
            })
    
    # 2. SEARCH PRODUCTS
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(sku__icontains=query) |
        Q(description__icontains=query) |
        Q(short_description__icontains=query) |
        Q(brand__icontains=query)
    ).filter(is_active=True).exclude(
        id__in=[r['id'] for r in results if r.get('type') == 'product']
    )[:10]
    
    for product in products:
        barcode = ProductBarcode.objects.filter(product=product).first()
        results.append({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': str(product.final_price),
            'original_price': str(product.price),
            'discount_percentage': str(product.discount_percentage),
            'image': product.main_image,
            'type': 'product',
            'barcode_text': barcode.barcode_text if barcode else None,
            'stock': product.stock_quantity,
            'has_variants': product.variants.filter(is_active=True).exists()
        })
    
    # 3. SEARCH VARIANTS
    variants = ProductVariant.objects.filter(
        Q(sku__icontains=query) |
        Q(name__icontains=query) |
        Q(color__icontains=query) |
        Q(size__icontains=query) |
        Q(material__icontains=query) |
        Q(product__name__icontains=query)
    ).filter(is_active=True).exclude(
        id__in=[r['id'] for r in results if r.get('type') == 'variant']
    )[:10]
    
    for variant in variants:
        barcode = ProductBarcode.objects.filter(variant=variant).first()
        results.append({
            'id': variant.id,
            'name': f"{variant.product.name} - {variant.name or variant.sku}",
            'sku': variant.sku,
            'price': str(variant.final_price),
            'original_price': str(variant.price),
            'discount_percentage': str(variant.discount_percentage),
            'image': variant.main_image or variant.product.main_image,
            'type': 'variant',
            'barcode_text': barcode.barcode_text if barcode else None,
            'stock': variant.stock_quantity,
            'product_id': variant.product.id,
            'color': variant.color,
            'size': variant.size,
            'material': variant.material,
        })
    
    # 4. REMOVE DUPLICATES
    seen = set()
    unique_results = []
    for item in results:
        key = (item['type'], item['id'])
        if key not in seen:
            seen.add(key)
            unique_results.append(item)
    
    return JsonResponse({'results': unique_results})


# ============================================
# OFFLINE SALE VIEWS
# ============================================

# offline_sales/views.py - Update cart calculation

@staff_member_required
def offline_sale_view(request):
    """Main offline sale page"""

    store_settings = StoreSettings.objects.first()
    if not store_settings:
        messages.warning(request, 'Please configure store settings first.')
        return redirect('offline_sales:store_settings_edit')

    cart = request.session.get('offline_cart', [])

    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_product_discount = Decimal('0.00')
    total_offer_discount = Decimal('0.00')
    grand_total = Decimal('0.00')

    cart_items = []

    for item in cart:
        price = Decimal(str(item.get('price', 0)))
        original_price = Decimal(str(item.get('original_price', 0)))
        quantity = Decimal(str(item.get('quantity', 1)))
        discount = Decimal(str(item.get('discount', 0)))
        offer_discount = Decimal(str(item.get('offer_discount', 0)))
        product_discount = Decimal(str(item.get('product_discount', 0)))

        item_total = price * quantity

        # Totals
        subtotal += original_price * quantity
        total_product_discount += product_discount * quantity
        total_offer_discount += offer_discount * quantity
        total_discount += discount * quantity
        grand_total += item_total

        cart_items.append({
            'id': item.get('id'),
            'product_id': item.get('product_id'),
            'variant_id': item.get('variant_id'),
            'name': item.get('name'),
            'sku': item.get('sku'),
            'price': float(price),
            'original_price': float(original_price),
            'quantity': int(quantity),
            'total': float(item_total),
            'discount': float(discount * quantity),
            'offer_discount': float(offer_discount * quantity),
            'product_discount': float(product_discount * quantity),
            'image': item.get('image'),
            'type': item.get('type', 'product'),
            'stock': item.get('stock', 0),
            'barcode_text': item.get('barcode_text', ''),
            'color': item.get('color', ''),
            'size': item.get('size', ''),
        })

    recent_customers = OfflineCustomer.objects.filter(
        is_active=True
    ).order_by('-last_purchase_at')[:20]

    context = {
        'store_settings': store_settings,
        'cart_items': cart_items,
        'subtotal': float(subtotal),
        'total_discount': float(total_discount),
        'total_product_discount': float(total_product_discount),
        'total_offer_discount': float(total_offer_discount),
        'grand_total': float(grand_total),
        'cart_count': len(cart_items),
        'recent_customers': recent_customers,
    }

    return render(
        request,
        'offline_sales/admin/offline_sale.html',
        context
    )
@csrf_exempt
@staff_member_required
def offline_sale_add_product(request):
    """Add product to offline sale cart (AJAX)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            variant_id = data.get('variant_id')
            quantity = int(data.get('quantity', 1))
            barcode_text = data.get('barcode_text', '')
            
            product = None
            variant = None
            
            if variant_id:
                variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
                product = variant.product
                stock = variant.stock_quantity
                name = f"{variant.product.name} - {variant.name or variant.sku}"
                sku = variant.sku
                image = variant.main_image or variant.product.main_image
                price = float(variant.final_price)
                original_price = float(variant.price)
                discount_percentage = float(variant.discount_percentage)
                product_id = variant.product.id
            elif product_id:
                product = get_object_or_404(Product, id=product_id, is_active=True)
                stock = product.stock_quantity
                name = product.name
                sku = product.sku
                image = product.main_image
                price = float(product.final_price)
                original_price = float(product.price)
                discount_percentage = float(product.discount_percentage)
            else:
                return JsonResponse({'success': False, 'error': 'Product not found'})
            
            if stock < quantity:
                return JsonResponse({
                    'success': False, 
                    'error': f'Only {stock} items available in stock'
                })
            
            cart = request.session.get('offline_cart', [])
            
            found = False
            for item in cart:
                if (variant_id and item.get('variant_id') == variant_id) or \
                   (product_id and not variant_id and item.get('product_id') == product_id and not item.get('variant_id')):
                    new_quantity = int(item.get('quantity', 0)) + quantity
                    if new_quantity > stock:
                        return JsonResponse({
                            'success': False, 
                            'error': f'Only {stock} items available in stock'
                        })
                    item['quantity'] = new_quantity
                    found = True
                    break
            
            product_discount = original_price - price
            final_price, offer_name, offer_discount = calculate_offer_discount(
                product, 
                Decimal(str(price)),
                variant=variant
            )
            offer_discount = float(offer_discount)
            final_price = float(final_price)
            total_discount = product_discount + offer_discount
            
            if not found:
                cart.append({
                    'id': variant_id or product_id,
                    'product_id': product_id,
                    'variant_id': variant_id,
                    'name': name,
                    'sku': sku,
                    'price': final_price,
                    'original_price': original_price,
                    'product_discount': product_discount,
                    'offer_discount': offer_discount,
                    'discount': total_discount,
                    'discount_percentage': discount_percentage,
                    'quantity': quantity,
                    'image': image,
                    'type': 'variant' if variant_id else 'product',
                    'stock': stock,
                    'barcode_text': barcode_text or None,
                })
            
            request.session['offline_cart'] = cart
            request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'message': f'"{name}" added to cart',
                'cart_count': len(cart)
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
@staff_member_required
def offline_sale_remove_product(request):
    """Remove product from offline sale cart (AJAX)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            index = data.get('index')
            
            cart = request.session.get('offline_cart', [])
            if 0 <= index < len(cart):
                removed = cart.pop(index)
                request.session['offline_cart'] = cart
                request.session.modified = True
                return JsonResponse({
                    'success': True,
                    'message': f'"{removed.get("name")}" removed from cart',
                    'cart_count': len(cart)
                })
            
            return JsonResponse({'success': False, 'error': 'Item not found'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
@staff_member_required
def offline_sale_update_quantity(request):
    """Update product quantity in offline sale cart (AJAX)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            index = data.get('index')
            quantity = int(data.get('quantity', 1))
            
            cart = request.session.get('offline_cart', [])
            if 0 <= index < len(cart):
                item = cart[index]
                stock = item.get('stock', 0)
                
                if quantity <= 0:
                    cart.pop(index)
                elif quantity > stock:
                    return JsonResponse({'success': False, 'error': f'Only {stock} items available'})
                else:
                    item['quantity'] = quantity
                
                request.session['offline_cart'] = cart
                request.session.modified = True
                
                subtotal = 0
                total_discount = 0
                for i in cart:
                    subtotal += float(i.get('price', 0)) * int(i.get('quantity', 1))
                    total_discount += float(i.get('discount', 0)) * int(i.get('quantity', 1))
                
                return JsonResponse({
                    'success': True,
                    'cart_count': len(cart),
                    'subtotal': subtotal,
                    'total_discount': total_discount,
                    'grand_total': subtotal - total_discount
                })
            
            return JsonResponse({'success': False, 'error': 'Item not found'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
@staff_member_required
def offline_sale_clear_cart(request):
    """Clear offline sale cart (AJAX)"""
    if request.method == 'POST':
        request.session['offline_cart'] = []
        request.session.modified = True
        return JsonResponse({'success': True, 'message': 'Cart cleared'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


# ============================================
# CUSTOMER MANAGEMENT
# ============================================

@staff_member_required
def customer_list_view(request):
    """List all offline customers"""
    customers = OfflineCustomer.objects.filter(is_active=True)
    
    search_query = request.GET.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    paginator = Paginator(customers, 20)
    page = request.GET.get('page')
    customers_page = paginator.get_page(page)
    
    context = {
        'customers': customers_page,
        'total_customers': customers.count(),
        'search_query': search_query,
    }
    return render(request, 'offline_sales/admin/customer_list.html', context)


@staff_member_required
def customer_create_view(request):
    """Create a new customer"""
    if request.method == 'POST':
        form = OfflineCustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer created successfully!')
            return redirect('offline_sales:customer_list')
    else:
        form = OfflineCustomerForm()
    
    return render(request, 'offline_sales/admin/customer_form.html', {
        'form': form,
        'action': 'Create',
        'customer': None
    })


@staff_member_required
def customer_edit_view(request, customer_id):
    """Edit an existing customer"""
    customer = get_object_or_404(OfflineCustomer, id=customer_id)
    
    if request.method == 'POST':
        form = OfflineCustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Customer updated successfully!')
            return redirect('offline_sales:customer_list')
    else:
        form = OfflineCustomerForm(instance=customer)
    
    return render(request, 'offline_sales/admin/customer_form.html', {
        'form': form,
        'action': 'Edit',
        'customer': customer
    })


@staff_member_required
def customer_delete_view(request, customer_id):
    """Delete a customer"""
    customer = get_object_or_404(OfflineCustomer, id=customer_id)
    
    if request.method == 'POST':
        customer.is_active = False
        customer.save()
        messages.success(request, 'Customer deleted successfully!')
        return redirect('offline_sales:customer_list')
    
    return render(request, 'offline_sales/admin/customer_delete.html', {
        'customer': customer
    })


@csrf_exempt
@staff_member_required
def offline_customer_search(request):
    """Search for offline customer (AJAX)"""
    if request.method == 'GET':
        query = request.GET.get('q', '').strip()
        
        if not query:
            return JsonResponse({'customers': []})
        
        customers = OfflineCustomer.objects.filter(
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).filter(is_active=True)[:10]
        
        results = []
        for customer in customers:
            results.append({
                'id': customer.id,
                'name': customer.full_name,
                'phone': customer.phone,
                'email': customer.email,
                'type': 'offline'
            })
        
        # Also search in online users
        users = User.objects.filter(
            Q(phone__icontains=query) |
            Q(email__icontains=query) |
            Q(full_name__icontains=query)
        ).filter(is_active=True)[:5]
        
        for user in users:
            results.append({
                'id': user.id,
                'name': user.full_name,
                'phone': user.phone or '',
                'email': user.email,
                'type': 'online'
            })
        
        return JsonResponse({'customers': results})
    
    return JsonResponse({'error': 'Invalid request'})


# offline_sales/views.py - Complete offline_customer_create

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@staff_member_required
def offline_customer_create(request):
    """Create new offline customer (AJAX)"""
    if request.method == 'POST':
        try:
            # Check if user is authenticated
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Please login first'
                }, status=401)
            
            # Handle both JSON and FormData
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
            
            # Debug log
            logger.info(f"Received customer data: {data}")
            
            # Validate required fields
            first_name = data.get('first_name', '').strip()
            if not first_name:
                return JsonResponse({
                    'success': False,
                    'error': 'First Name is required'
                })
            
            phone_raw = data.get('phone', '').strip()
            if not phone_raw:
                return JsonResponse({
                    'success': False,
                    'error': 'Phone number is required'
                })
            
            # Clean phone number (remove non-digits)
            phone = ''.join(filter(str.isdigit, phone_raw))
            if len(phone) < 10:
                return JsonResponse({
                    'success': False,
                    'error': 'Phone number must be at least 10 digits'
                })
            
            # Check duplicate phone
            if OfflineCustomer.objects.filter(phone=phone).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Customer with this phone number already exists'
                })
            
            # Check duplicate email (if provided)
            email = data.get('email', '').strip()
            if email and OfflineCustomer.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Customer with this email already exists'
                })
            
            # Create customer
            customer = OfflineCustomer.objects.create(
                first_name=first_name,
                last_name=data.get('last_name', '').strip(),
                phone=phone,
                email=email,
                address=data.get('address', '').strip(),
                notes=data.get('notes', '').strip()
            )
            
            return JsonResponse({
                'success': True,
                'customer': {
                    'id': customer.id,
                    'name': customer.full_name,
                    'phone': customer.phone,
                    'email': customer.email,
                    'type': 'offline'
                },
                'message': 'Customer created successfully'
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data format'
            }, status=400)
            
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)
# ============================================
# ORDER MANAGEMENT
# ============================================

@staff_member_required
def orders_list_view(request):
    """List all offline orders"""
    orders = OfflineOrder.objects.all().order_by('-created_at')
    
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_status', '')
    search_query = request.GET.get('search', '')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(invoice_number__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(customer_email__icontains=search_query)
        )
    
    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    stats = {
        'total': OfflineOrder.objects.count(),
        'completed': OfflineOrder.objects.filter(status='completed').count(),
        'pending': OfflineOrder.objects.filter(status='pending').count(),
        'paid': OfflineOrder.objects.filter(payment_status='paid').count(),
        'pending_payment': OfflineOrder.objects.filter(payment_status='pending').count(),
    }
    
    context = {
        'orders': orders_page,
        'stats': stats,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'search_query': search_query,
        'status_choices': OfflineOrder.ORDER_STATUS,
        'payment_status_choices': OfflineOrder.PAYMENT_STATUS,
    }
    return render(request, 'offline_sales/admin/order_list.html', context)


@staff_member_required
def order_detail_view(request, order_id):
    """View order details"""
    order = get_object_or_404(OfflineOrder, id=order_id)
    items = order.items.all()
    store_settings = StoreSettings.objects.first()
    
    has_offline_customer = order.offline_customer is not None
    has_online_customer = order.customer is not None
    
    context = {
        'order': order,
        'items': items,
        'store_settings': store_settings,
        'has_offline_customer': has_offline_customer,
        'has_online_customer': has_online_customer,
    }
    return render(request, 'offline_sales/admin/order_detail.html', context)


# ============================================
# OFFLINE ORDER COMPLETION
# ============================================

# offline_sales/views.py - Complete fixed offline_sale_complete

from decimal import Decimal

@csrf_exempt
@staff_member_required
def offline_sale_complete(request):
    """Complete offline sale and create order"""
    if request.method == 'POST':
        try:
            form = OfflineSalePaymentForm(request.POST)
            
            if not form.is_valid():
                return JsonResponse({'success': False, 'errors': form.errors})
            
            cart = request.session.get('offline_cart', [])
            if not cart:
                return JsonResponse({'success': False, 'error': 'Cart is empty'})
            
            customer_id = request.POST.get('customer_id')
            customer_type = request.POST.get('customer_type', 'offline')
            
            customer = None
            offline_customer = None
            customer_name = ''
            customer_email = ''
            customer_phone = ''
            customer_address = ''
            
            if customer_type == 'online':
                customer = get_object_or_404(User, id=customer_id)
                customer_name = customer.full_name
                customer_email = customer.email
                customer_phone = customer.phone or ''
                default_address = customer.addresses.filter(is_default=True).first()
                if default_address:
                    customer_address = f"{default_address.address_line1}\n{default_address.city}, {default_address.state} - {default_address.pincode}"
            else:
                offline_customer = get_object_or_404(OfflineCustomer, id=customer_id)
                customer_name = offline_customer.full_name
                customer_email = offline_customer.email or ''
                customer_phone = offline_customer.phone
                customer_address = offline_customer.address
            
            # Calculate totals - Use Decimal for all calculations
            subtotal = Decimal('0')
            product_discount_total = Decimal('0')
            offer_discount_total = Decimal('0')
            total_amount = Decimal('0')
            
            for item in cart:
                # Convert all values to Decimal
                price = Decimal(str(item.get('price', 0)))
                original_price = Decimal(str(item.get('original_price', 0)))
                quantity = Decimal(str(item.get('quantity', 1)))
                product_discount = Decimal(str(item.get('product_discount', 0)))
                offer_discount = Decimal(str(item.get('offer_discount', 0)))
                
                item_total = price * quantity
                product_discount_total += product_discount * quantity
                offer_discount_total += offer_discount * quantity
                subtotal += original_price * quantity
                total_amount += item_total
            
            store_settings = StoreSettings.objects.first()
            
            with transaction.atomic():
                order = OfflineOrder.objects.create(
                    customer=customer,
                    offline_customer=offline_customer,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    customer_address=customer_address,
                    subtotal=subtotal,
                    product_discount_total=product_discount_total,
                    offer_discount=offer_discount_total,
                    coupon_discount=Decimal('0'),
                    total_amount=total_amount,
                    payment_method=form.cleaned_data['payment_method'],
                    payment_status='paid',
                    payment_reference=form.cleaned_data.get('payment_reference', ''),
                    paid_at=timezone.now(),
                    status='completed',
                    created_by=request.user,
                    invoice_number=store_settings.get_next_invoice_number() if store_settings else None
                )
                
                for item in cart:
                    product = None
                    variant = None
                    
                    if item.get('variant_id'):
                        variant = get_object_or_404(ProductVariant, id=item.get('variant_id'))
                        product = variant.product
                    elif item.get('product_id'):
                        product = get_object_or_404(Product, id=item.get('product_id'))
                    
                    quantity = int(item.get('quantity', 1))
                    
                    if variant:
                        if variant.stock_quantity < quantity:
                            raise ValidationError(f'Not enough stock for {variant.sku}')
                        
                        old_variant_stock = variant.stock_quantity
                        variant.stock_quantity -= quantity
                        variant.save()
                        
                        if variant.product:
                            old_product_stock = variant.product.stock_quantity
                            variant.product.stock_quantity -= quantity
                            variant.product.save()
                            
                            InventoryLog.objects.create(
                                product=variant.product,
                                variant=variant,
                                quantity_change=-quantity,
                                previous_quantity=old_product_stock,
                                new_quantity=variant.product.stock_quantity,
                                action='sale',
                                note=f'Offline sale - Order #{order.order_number}',
                                created_by=request.user
                            )
                        
                        InventoryLog.objects.create(
                            variant=variant,
                            quantity_change=-quantity,
                            previous_quantity=old_variant_stock,
                            new_quantity=variant.stock_quantity,
                            action='sale',
                            note=f'Offline sale - Order #{order.order_number}',
                            created_by=request.user
                        )
                        
                    elif product:
                        if product.stock_quantity < quantity:
                            raise ValidationError(f'Not enough stock for {product.name}')
                        
                        old_stock = product.stock_quantity
                        product.stock_quantity -= quantity
                        product.save()
                        
                        InventoryLog.objects.create(
                            product=product,
                            quantity_change=-quantity,
                            previous_quantity=old_stock,
                            new_quantity=product.stock_quantity,
                            action='sale',
                            note=f'Offline sale - Order #{order.order_number}',
                            created_by=request.user
                        )
                    
                    # Convert all values to Decimal for storage
                    OfflineOrderItem.objects.create(
                        order=order,
                        product=product,
                        variant=variant,
                        product_name=item.get('name', ''),
                        sku=item.get('sku', ''),
                        barcode_text=item.get('barcode_text', ''),
                        quantity=quantity,
                        original_price=Decimal(str(item.get('original_price', 0))),
                        final_price=Decimal(str(item.get('price', 0))),
                        total=Decimal(str(item.get('price', 0))) * quantity,
                        discount=Decimal(str(item.get('discount', 0))) * quantity
                    )
                
                if offline_customer:
                    offline_customer.total_purchases += total_amount
                    offline_customer.total_orders += 1
                    offline_customer.last_purchase_at = timezone.now()
                    offline_customer.save()
                
                request.session['offline_cart'] = []
                request.session.modified = True
            
            # Send invoice email
            if order.customer_email:
                send_invoice_email(order, store_settings, request)
            
            invoice_html = generate_invoice_html(order, store_settings)
            
            return JsonResponse({
                'success': True,
                'order_id': order.id,
                'order_number': order.order_number,
                'invoice_number': order.invoice_number,
                'message': 'Order completed successfully!',
                'invoice_html': invoice_html
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)})
        except Exception as e:
            logger.error(f"Order completion error: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# ============================================
# INVOICE VIEWS
# ============================================

@staff_member_required
def download_invoice_view(request, order_id):
    """Download invoice as PDF"""
    order = get_object_or_404(OfflineOrder, id=order_id)
    store_settings = StoreSettings.objects.first()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.invoice_number or order.order_number}.pdf"'
    
    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    # Store Logo
    if store_settings and store_settings.store_logo:
        try:
            logo_path = store_settings.store_logo.path
            pdf.drawImage(logo_path, 50, height - 100, width=100, height=50)
        except:
            pass
    
    # Store Name
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, height - 80, store_settings.store_name if store_settings else "My Store")
    
    # Store Address
    pdf.setFont("Helvetica", 10)
    y = height - 100
    if store_settings:
        lines = store_settings.store_address.split('\n')
        for line in lines:
            y -= 15
            pdf.drawString(50, y, line)
        pdf.drawString(50, y - 15, f"Phone: {store_settings.store_phone}")
        pdf.drawString(50, y - 30, f"Email: {store_settings.store_email}")
        if store_settings.gst_number:
            pdf.drawString(50, y - 45, f"GST: {store_settings.gst_number}")
    
    # Invoice Title
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(400, height - 80, "INVOICE")
    
    # Invoice Details
    pdf.setFont("Helvetica", 10)
    pdf.drawString(400, height - 100, f"Invoice #: {order.invoice_number or order.order_number}")
    pdf.drawString(400, height - 115, f"Date: {order.created_at.strftime('%d %B, %Y')}")
    pdf.drawString(400, height - 130, f"Order #: {order.order_number}")
    
    # Customer Details
    y = height - 180
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Bill To:")
    pdf.setFont("Helvetica", 10)
    y -= 20
    pdf.drawString(50, y, order.customer_name)
    y -= 15
    if order.customer_phone:
        pdf.drawString(50, y, f"Phone: {order.customer_phone}")
        y -= 15
    if order.customer_email:
        pdf.drawString(50, y, f"Email: {order.customer_email}")
        y -= 15
    if order.customer_address:
        lines = order.customer_address.split('\n')
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 15
    
    # Items Table
    y = height - 350
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Item")
    pdf.drawString(250, y, "Quantity")
    pdf.drawString(320, y, "Price")
    pdf.drawString(400, y, "Discount")
    pdf.drawString(480, y, "Total")
    
    pdf.line(50, y - 5, 530, y - 5)
    y -= 20
    
    pdf.setFont("Helvetica", 9)
    total = 0
    for item in order.items.all():
        pdf.drawString(50, y, item.product_name[:30])
        pdf.drawString(250, y, str(item.quantity))
        pdf.drawString(320, y, f"₹{item.original_price:.2f}")
        pdf.drawString(400, y, f"₹{item.discount:.2f}")
        pdf.drawString(480, y, f"₹{item.total:.2f}")
        total += item.total
        y -= 20
        
        if y < 100:
            pdf.showPage()
            y = height - 50
    
    # Totals
    y -= 20
    pdf.line(50, y + 10, 530, y + 10)
    
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(350, y, "Subtotal:")
    pdf.drawString(480, y, f"₹{order.subtotal:.2f}")
    y -= 20
    
    if order.product_discount_total > 0:
        pdf.drawString(350, y, "Product Discount:")
        pdf.drawString(480, y, f"-₹{order.product_discount_total:.2f}")
        y -= 20
    
    if order.offer_discount > 0:
        pdf.drawString(350, y, "Offer Discount:")
        pdf.drawString(480, y, f"-₹{order.offer_discount:.2f}")
        y -= 20
    
    y -= 10
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(350, y, "Total:")
    pdf.drawString(480, y, f"₹{order.total_amount:.2f}")
    
    # Payment Details
    y -= 40
    pdf.setFont("Helvetica", 9)
    pdf.drawString(50, y, f"Payment Method: {order.get_payment_method_display()}")
    y -= 15
    pdf.drawString(50, y, f"Payment Status: {order.get_payment_status_display()}")
    y -= 15
    if order.payment_reference:
        pdf.drawString(50, y, f"Payment Reference: {order.payment_reference}")
    
    # Terms & Conditions
    if store_settings and store_settings.terms_conditions:
        y -= 40
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y, "Terms & Conditions:")
        y -= 15
        pdf.setFont("Helvetica", 8)
        lines = store_settings.terms_conditions.split('\n')
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 12
    
    # Footer
    if store_settings and store_settings.footer_text:
        pdf.setFont("Helvetica", 8)
        pdf.drawString(50, 30, store_settings.footer_text)
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 50, "Thank you for your purchase!")
    
    pdf.save()
    return response


