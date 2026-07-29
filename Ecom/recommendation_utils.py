# Ecom/recommendation_utils.py

from django.db.models import Q, Count, Avg, F, Exists, OuterRef, Value, IntegerField
from django.db.models.functions import Coalesce
from .models import Product, Category, SubCategory, RecentlyViewed, CartItem, WishlistItem, OrderItem
from decimal import Decimal
import random
from collections import defaultdict

def get_user_recommendations(user, limit=10, exclude_product_ids=None):
    """
    Get personalized product recommendations for a user based on their activity.
    Returns a list of product objects.
    """
    if not user.is_authenticated:
        return get_popular_products(limit)
    
    if exclude_product_ids is None:
        exclude_product_ids = []
    
    # Get user's activity data
    viewed_products = get_viewed_products(user)
    cart_products = get_cart_products(user)
    wishlist_products = get_wishlist_products(user)
    ordered_products = get_ordered_products(user)
    
    # Combine all interacted product IDs
    interacted_product_ids = set(
        list(viewed_products.values_list('id', flat=True)) +
        list(cart_products.values_list('id', flat=True)) +
        list(wishlist_products.values_list('id', flat=True)) +
        list(ordered_products.values_list('id', flat=True))
    )
    
    # Exclude products already interacted with
    exclude_ids = set(exclude_product_ids) | interacted_product_ids
    
    # Get recommendation scores from different strategies
    scores = defaultdict(float)
    
    # 1. Content-based: Similar to viewed products
    if viewed_products:
        similar_from_viewed = get_similar_products(viewed_products, exclude_ids, limit=20)
        for product in similar_from_viewed:
            scores[product.id] += 1.5
    
    # 2. Content-based: Similar to cart products (higher weight)
    if cart_products:
        similar_from_cart = get_similar_products(cart_products, exclude_ids, limit=15)
        for product in similar_from_cart:
            scores[product.id] += 2.0
    
    # 3. Content-based: Similar to wishlist products
    if wishlist_products:
        similar_from_wishlist = get_similar_products(wishlist_products, exclude_ids, limit=15)
        for product in similar_from_wishlist:
            scores[product.id] += 1.8
    
    # 4. Content-based: Similar to ordered products
    if ordered_products:
        similar_from_orders = get_similar_products(ordered_products, exclude_ids, limit=15)
        for product in similar_from_orders:
            scores[product.id] += 1.5
    
    # 5. Category preference - products from categories user interacts with most
    category_scores = get_category_preference(user)
    if category_scores:
        # Get products from preferred categories
        preferred_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        category_products = Product.objects.filter(
            is_active=True,
            category__in=[cat_id for cat_id, _ in preferred_categories]
        ).exclude(id__in=exclude_ids).order_by('-created_at')[:10]
        
        for product in category_products:
            scores[product.id] += 1.0
    
    # 6. Collaborative filtering - users with similar purchase patterns
    collaborative_products = get_collaborative_recommendations(user, exclude_ids)
    for product in collaborative_products:
        scores[product.id] += 1.2
    
    # 7. Popular products (fallback)
    popular_products = get_popular_products(limit=10, exclude_ids=exclude_ids)
    for product in popular_products:
        scores[product.id] += 0.5
    
    # Sort by score and get top products
    sorted_products = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Get product objects
    recommended_ids = [p_id for p_id, _ in sorted_products[:limit]]
    
    # If not enough recommendations, fill with popular products
    if len(recommended_ids) < limit:
        remaining = limit - len(recommended_ids)
        fallback_products = get_popular_products(
            limit=remaining + 5, 
            exclude_ids=set(recommended_ids) | exclude_ids
        )
        for product in fallback_products[:remaining]:
            if product.id not in recommended_ids:
                recommended_ids.append(product.id)
    
    # Fetch products with annotations
    recommended_products = Product.objects.filter(
        id__in=recommended_ids,
        is_active=True
    ).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    )
    
    # Preserve order
    product_dict = {p.id: p for p in recommended_products}
    ordered_products_list = [product_dict[p_id] for p_id in recommended_ids if p_id in product_dict]
    
    return ordered_products_list[:limit]


def get_viewed_products(user):
    """Get products user has viewed recently"""
    return Product.objects.filter(
        recentlyviewed__user=user,
        is_active=True
    ).order_by('-recentlyviewed__viewed_at')[:20]


def get_cart_products(user):
    """Get products in user's cart"""
    return Product.objects.filter(
        cartitem__cart__user=user,
        is_active=True
    ).distinct()


def get_wishlist_products(user):
    """Get products in user's wishlist"""
    return Product.objects.filter(
        wishlistitem__wishlist__user=user,
        is_active=True
    ).distinct()


def get_ordered_products(user):
    """Get products user has ordered"""
    return Product.objects.filter(
        orderitem__order__user=user,
        is_active=True
    ).distinct().order_by('-orderitem__order__created_at')[:20]


def get_similar_products(products, exclude_ids=None, limit=10):
    """
    Get products similar to a given list of products based on category and subcategory.
    """
    if exclude_ids is None:
        exclude_ids = set()
    
    if not products:
        return []
    
    # Get category and subcategory IDs from the given products
    category_ids = set(products.values_list('category_id', flat=True))
    subcategory_ids = set(products.values_list('subcategory_id', flat=True))
    
    # Find products with same categories or subcategories
    similar = Product.objects.filter(
        is_active=True
    ).filter(
        Q(category_id__in=category_ids) | Q(subcategory_id__in=subcategory_ids)
    ).exclude(
        id__in=exclude_ids
    ).order_by('-created_at')[:limit]
    
    return similar


def get_category_preference(user):
    """
    Analyze user's activity to determine category preferences.
    Returns dict {category_id: score}
    """
    scores = defaultdict(float)
    
    # From orders (highest weight)
    order_categories = OrderItem.objects.filter(
        order__user=user,
        product__is_active=True,
        product__category__isnull=False
    ).values('product__category_id').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for item in order_categories:
        scores[item['product__category_id']] += item['count'] * 2.0
    
    # From cart
    cart_categories = CartItem.objects.filter(
        cart__user=user,
        product__is_active=True,
        product__category__isnull=False
    ).values('product__category_id').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for item in cart_categories:
        scores[item['product__category_id']] += item['count'] * 1.5
    
    # From wishlist
    wishlist_categories = WishlistItem.objects.filter(
        wishlist__user=user,
        product__is_active=True,
        product__category__isnull=False
    ).values('product__category_id').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for item in wishlist_categories:
        scores[item['product__category_id']] += item['count'] * 1.2
    
    # From recently viewed
    viewed_categories = RecentlyViewed.objects.filter(
        user=user,
        product__is_active=True,
        product__category__isnull=False
    ).values('product__category_id').annotate(
        count=Count('id')
    ).order_by('-count')
    
    for item in viewed_categories:
        scores[item['product__category_id']] += item['count'] * 0.8
    
    return dict(scores)


def get_collaborative_recommendations(user, exclude_ids=None):
    """
    Find products that users with similar purchase patterns have bought.
    Simple collaborative filtering based on order history.
    """
    if exclude_ids is None:
        exclude_ids = set()
    
    # Get products the user has ordered
    user_products = set(
        OrderItem.objects.filter(
            order__user=user
        ).values_list('product_id', flat=True)
    )
    
    if not user_products:
        return []
    
    # Find other users who bought similar products
    similar_users = User.objects.filter(
        orders__items__product_id__in=user_products,
        is_active=True
    ).exclude(id=user.id).distinct()
    
    # Get products these similar users bought, but our user hasn't
    collaborative_products = Product.objects.filter(
        orderitem__order__user__in=similar_users,
        is_active=True
    ).exclude(
        id__in=user_products
    ).exclude(
        id__in=exclude_ids
    ).annotate(
        purchase_count=Count('orderitem')
    ).order_by('-purchase_count', '-created_at')[:10]
    
    return collaborative_products


def get_popular_products(limit=10, exclude_ids=None):
    """
    Get popular products based on order count and rating.
    """
    if exclude_ids is None:
        exclude_ids = set()
    
    return Product.objects.filter(
        is_active=True
    ).exclude(
        id__in=exclude_ids
    ).annotate(
        order_count=Count('orderitem'),
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    ).order_by(
        '-order_count', '-avg_rating', '-created_at'
    )[:limit]


def get_hybrid_recommendations(user, limit=10, exclude_product_ids=None):
    """
    Hybrid recommendation combining multiple strategies with weights.
    """
    if exclude_product_ids is None:
        exclude_product_ids = []
    
    # Get recommendations from different strategies
    viewed_recs = get_similar_from_viewed(user, exclude_product_ids)
    cart_recs = get_similar_from_cart(user, exclude_product_ids)
    wishlist_recs = get_similar_from_wishlist(user, exclude_product_ids)
    order_recs = get_similar_from_orders(user, exclude_product_ids)
    category_recs = get_category_based_recommendations(user, exclude_product_ids)
    popular_recs = get_popular_products(limit=10, exclude_ids=set(exclude_product_ids))
    
    # Score each product
    scores = defaultdict(float)
    
    # Weighted scoring
    for product in viewed_recs:
        scores[product.id] += 1.0
    for product in cart_recs:
        scores[product.id] += 2.0  # Cart has higher intent
    for product in wishlist_recs:
        scores[product.id] += 1.8  # Wishlist shows interest
    for product in order_recs:
        scores[product.id] += 1.5  # Past purchases
    for product in category_recs:
        scores[product.id] += 1.2
    for product in popular_recs:
        if product.id not in scores:
            scores[product.id] += 0.5
        else:
            scores[product.id] += 0.3
    
    # Sort by score
    sorted_products = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    recommended_ids = [p_id for p_id, _ in sorted_products[:limit]]
    
    # Fetch product objects with annotations
    recommended_products = Product.objects.filter(
        id__in=recommended_ids,
        is_active=True
    ).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
        order_count=Count('orderitem')
    )
    
    # Preserve order
    product_dict = {p.id: p for p in recommended_products}
    ordered_list = [product_dict[p_id] for p_id in recommended_ids if p_id in product_dict]
    
    return ordered_list


def get_similar_from_viewed(user, exclude_ids=None):
    """Get similar products based on viewed products"""
    if exclude_ids is None:
        exclude_ids = []
    viewed_products = get_viewed_products(user)
    if viewed_products:
        return get_similar_products(viewed_products, set(exclude_ids), limit=15)
    return []


def get_similar_from_cart(user, exclude_ids=None):
    """Get similar products based on cart products"""
    if exclude_ids is None:
        exclude_ids = []
    cart_products = get_cart_products(user)
    if cart_products:
        return get_similar_products(cart_products, set(exclude_ids), limit=12)
    return []


def get_similar_from_wishlist(user, exclude_ids=None):
    """Get similar products based on wishlist products"""
    if exclude_ids is None:
        exclude_ids = []
    wishlist_products = get_wishlist_products(user)
    if wishlist_products:
        return get_similar_products(wishlist_products, set(exclude_ids), limit=12)
    return []


def get_similar_from_orders(user, exclude_ids=None):
    """Get similar products based on ordered products"""
    if exclude_ids is None:
        exclude_ids = []
    ordered_products = get_ordered_products(user)
    if ordered_products:
        return get_similar_products(ordered_products, set(exclude_ids), limit=12)
    return []


def get_category_based_recommendations(user, exclude_ids=None):
    """Get recommendations based on category preference"""
    if exclude_ids is None:
        exclude_ids = []
    
    category_scores = get_category_preference(user)
    if not category_scores:
        return []
    
    # Get top 2 categories
    top_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)[:2]
    category_ids = [cat_id for cat_id, _ in top_categories]
    
    # Get products from these categories
    recommendations = Product.objects.filter(
        is_active=True,
        category_id__in=category_ids
    ).exclude(
        id__in=exclude_ids
    ).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    ).order_by('-avg_rating', '-created_at')[:10]
    
    return recommendations