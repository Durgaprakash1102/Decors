from django.db.models import F
from .models import Product, ProductVariant, ProductReview


def low_stock_context(request):
    if not request.user.is_authenticated:
        return {}

    # Low Stock Counts
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

    # Pending Reviews
    pending_review_count = ProductReview.objects.filter(
        is_approved=False
    ).count()

    return {
        "out_of_stock_products_count": out_of_stock_products,
        "low_stock_products_count": low_stock_products,
        "out_of_stock_variants_count": out_of_stock_variants,
        "low_stock_variants_count": low_stock_variants,
        "total_low_stock_count": (
            out_of_stock_products
            + low_stock_products
            + out_of_stock_variants
            + low_stock_variants
        ),

        # Reviews
        "pending_review_count": pending_review_count,
    }