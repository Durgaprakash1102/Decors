# Ecom/custom_context.py

from .models import Cart, Wishlist

def get_nav_counts(request):
    """
    Context processor for navigation header counts.
    """
    cart_qty = 0
    wishlist_qty = 0
    
    if request.user.is_authenticated:
        # Get cart
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_qty = cart.total_items if cart else 0
        
        # Get wishlist
        try:
            wishlist = Wishlist.objects.get(user=request.user)
            wishlist_qty = wishlist.total_items if wishlist else 0
        except Wishlist.DoesNotExist:
            wishlist_qty = 0
    else:
        # Guest user
        session_id = request.session.session_key
        if session_id:
            try:
                cart = Cart.objects.get(session_id=session_id, user=None)
                cart_qty = cart.total_items if cart else 0
            except Cart.DoesNotExist:
                cart_qty = 0
    
    return {
        'nav_cart_qty': cart_qty,
        'nav_wishlist_qty': wishlist_qty,
    }