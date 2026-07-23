from django.db.models import F
from .models import Product, ProductVariant, ProductReview, Order


def low_stock_context(request):
    if not request.user.is_authenticated:
        return {}

    # ==========================================
    # Low Stock Counts
    # ==========================================

    out_of_stock_products = Product.objects.filter(
        is_active=True,
        stock_quantity=0
    ).count()

    low_stock_products = Product.objects.filter(
        is_active=True,
        stock_quantity__gt=0,
        stock_quantity__lte=F("low_stock_threshold")
    ).count()

    out_of_stock_variants = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity=0
    ).count()

    low_stock_variants = ProductVariant.objects.filter(
        is_active=True,
        stock_quantity__gt=0,
        stock_quantity__lte=F("low_stock_threshold")
    ).count()

    # ==========================================
    # Pending Reviews
    # ==========================================

    pending_review_count = ProductReview.objects.filter(
        is_approved=False
    ).count()

    # ==========================================
    # Incoming Orders
    # ==========================================

    incoming_orders_count = Order.objects.filter(
        status='processing'
    ).count()

    # ==========================================
    # Pending Replacement Requests
    # ==========================================

    replacement_requests_count = Order.objects.filter(
        replacement_requested=True,
        replacement_approved=False,
        replacement_rejected=False,
        replacement_completed=False
    ).count()

    # ==========================================
    # Pending Return Requests
    # ==========================================

    return_requests_count = Order.objects.filter(
        return_requested=True,
        return_approved=False,
        return_rejected=False,
        return_completed=False
    ).count()

    # ==========================================
    # Pending Cancellation Requests
    # ==========================================

    cancellation_requests_count = Order.objects.filter(
        cancellation_requested=True,
        cancelled_at__isnull=True
    ).count()

    return {
        # Inventory
        "out_of_stock_products_count": out_of_stock_products,
        "low_stock_products_count": low_stock_products,
        "out_of_stock_variants_count": out_of_stock_variants,
        "low_stock_variants_count": low_stock_variants,
        "total_low_stock_count": (
            out_of_stock_products +
            low_stock_products +
            out_of_stock_variants +
            low_stock_variants
        ),

        # Reviews
        "pending_review_count": pending_review_count,

        # Orders
        "incoming_orders_count": incoming_orders_count,
        "replacement_requests_count": replacement_requests_count,
        "return_requests_count": return_requests_count,
        "cancellation_requests_count": cancellation_requests_count,
    }