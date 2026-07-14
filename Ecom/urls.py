from django.urls import path
from . import views
from . views import *

app_name = 'Ecom'

urlpatterns = [
    path("", views.home, name="home"),
    path('signup/customer/', views.customer_signup_view, name='customer_signup'),
    path('signup/admin/', views.admin_signup_view, name='admin_signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # OTP Verification URLs
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('verify-otp-login/', views.verify_otp_login_view, name='verify_otp_login'),
    path('resend-otp/<str:otp_type>/', views.resend_otp_view, name='resend_otp'),
    
    # Password Management URLs
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('verify-forgot-password/', views.verify_forgot_password_view, name='verify_forgot_password'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('verify-change-password/', views.verify_change_password_view, name='verify_change_password'),
    
    # Profile URLs
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile_view, name='update_profile'),
    
    # Address URLs
    path('address/add/', views.add_address_view, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address_view, name='edit_address'),
    path('address/delete/<int:address_id>/', views.delete_address_view, name='delete_address'),
    path('address/set-default/<int:address_id>/', views.set_default_address_view, name='set_default_address'),
    
    # Admin URLs
    path('admin_dashboard/', views.admin_dashboard_view, name='admin_dashboard'),

        # ========== CATEGORY URLs ==========
    path('admin_categories/', views.category_list_view, name='category_list'),
    path('admin_category/create/', views.category_create_view, name='category_create'),
    path('admin_category/edit/<int:category_id>/', views.category_edit_view, name='category_edit'),
    path('admin_category/delete/<int:category_id>/', views.category_delete_view, name='category_delete'),
    
    # ========== SUBCATEGORY URLs ==========
    path('admin_subcategories/', views.subcategory_list_view, name='subcategory_list'),
    path('admin_subcategory/create/', views.subcategory_create_view, name='subcategory_create'),
    path('admin_subcategory/edit/<int:subcategory_id>/', views.subcategory_edit_view, name='subcategory_edit'),
    path('admin_subcategory/delete/<int:subcategory_id>/', views.subcategory_delete_view, name='subcategory_delete'),
    
    # ========== PRODUCT URLs (Smart Unified) ==========
    path('admin_products/', views.product_list_view, name='product_list'),
    path('admin_product/create/', views.product_smart_create_view, name='product_smart_create'),
    path('admin_product/edit/<int:product_id>/', views.product_smart_edit_view, name='product_smart_edit'),
    path('admin_product/detail/<int:product_id>/', views.product_admin_detail_view, name='product_admin_detail'),
    path('admin_product/delete/<int:product_id>/', views.product_delete_view, name='product_delete'),
    path('admin/product/image/delete/<int:image_id>/', views.delete_product_image_ajax, name='delete_product_image'),
    path('admin/variant/image/delete/<int:image_id>/', views.delete_variant_image_ajax, name='delete_variant_image'),
    # ========== PUBLIC PRODUCT URLs ==========
    path('product/<int:product_id>/', views.product_detail_view, name='product_detail'),
    
    # ========== REVIEW URLs ==========
    path('admin_reviews/', views.review_list_view, name='review_list'),
    path('admin_review/approve/<int:review_id>/', views.review_approve_view, name='review_approve'),
    path('admin_review/delete/<int:review_id>/', views.review_delete_view, name='review_delete'),
    path('product/<int:product_id>/add-review/', views.add_review_view, name='add_review'),
    
    
    # ========== INVENTORY LOG URLs ==========
    path('admin_inventory-log/', views.inventory_log_view, name='inventory_log'),
    
    # ========== LOW STOCK ALERT URLs ==========
    path('admin_low-stock-alerts/', views.low_stock_alert_view, name='low_stock_alerts'),
    
    # ========== RECENTLY VIEWED URLs ==========
    path('recently-viewed/', views.recently_viewed_view, name='recently_viewed'),

     path('shop/', views.shop_view, name='shop'),
    path('shop/category/<slug:category_slug>/', views.category_shop_view, name='category_shop'),
    path('shop/subcategory/<slug:subcategory_slug>/', views.subcategory_shop_view, name='subcategory_shop'),
    
    # ========== GLOBAL SEARCH URL ==========
    path('api/search/', views.global_search_view, name='global_search'),
    
    # ========== AJAX URLs ==========
    path('ajax/get-subcategories/', views.get_subcategories_ajax, name='get_subcategories'),

        # ========== CART URLs ==========
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('cart/remove-coupon/', views.remove_coupon, name='remove_coupon'),
    path('cart/count/', views.get_cart_count, name='cart_count'),
    
    # ========== WISHLIST URLs ==========
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('wishlist/move-to-cart/<int:item_id>/', views.move_to_cart, name='move_to_cart'),
    
    # ========== CHECKOUT & PAYMENT URLs ==========
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('order/success/<int:order_id>/', views.order_success_view, name='order_success'),
    path('orders/', views.orders_view, name='orders'),
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('address/add-ajax/', views.add_address_ajax, name='add_address'),
    # ========== COUPON MANAGEMENT URLs ==========
path('admin/coupons/', views.coupon_list_view, name='coupon_list'),
path('admin/coupon/create/', views.coupon_create_view, name='coupon_create'),
path('admin/coupon/edit/<int:coupon_id>/', views.coupon_edit_view, name='coupon_edit'),
path('admin/coupon/delete/<int:coupon_id>/', views.coupon_delete_view, name='coupon_delete'),
path('admin/coupon/toggle/<int:coupon_id>/', views.coupon_toggle_status_view, name='coupon_toggle'),

# ========== OFFER MANAGEMENT URLs ==========
path('admin/offers/', views.offer_list_view, name='offer_list'),
path('admin/offer/create/', views.offer_create_view, name='offer_create'),
path('admin/offer/edit/<int:offer_id>/', views.offer_edit_view, name='offer_edit'),
path('admin/offer/delete/<int:offer_id>/', views.offer_delete_view, name='offer_delete'),
path('admin/offer/toggle/<int:offer_id>/', views.offer_toggle_status_view, name='offer_toggle'),
path('get-subcategories-ajax/', views.get_subcategories_ajax, name='get_subcategories_ajax'),
path('get-all-subcategories-ajax/', views.get_all_subcategories_ajax, name='get_all_subcategories_ajax'),

path('admin/orders/', admin_order_list_view, name='admin_order_list'),
    path('admin/orders/<int:order_id>/', admin_order_detail_view, name='admin_order_detail'),
    path('admin/orders/<int:order_id>/update/', admin_order_update_view, name='admin_order_update'),
    path('admin/orders/bulk-update/', admin_order_bulk_update_view, name='admin_order_bulk_update'),
    path('admin/orders/status-update-ajax/', admin_order_status_update_ajax, name='admin_order_status_update_ajax'),
 path('admin/banners/', banner_list_view, name='banner_list'),
    path('admin/banners/create/', banner_create_view, name='banner_create'),
    path('admin/banners/<int:banner_id>/edit/', banner_edit_view, name='banner_edit'),
    path('admin/banners/<int:banner_id>/delete/', banner_delete_view, name='banner_delete'),
    path('admin/banners/<int:banner_id>/toggle/', banner_toggle_status_view, name='banner_toggle'),
]