from .models import Category, SubCategory

def header_categories(request):
    """
    Context processor to provide categories and subcategories 
    for the header navigation across all pages.
    """
    # Get all active categories with their subcategories
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    # Get all active subcategories grouped by category
    subcategories = SubCategory.objects.filter(
        is_active=True,
        category__is_active=True
    ).select_related('category').order_by('category__name', 'name')
    
    return {
        'categories': categories,
        'subcategories': subcategories,
        'total_categories': categories.count(),
    }

