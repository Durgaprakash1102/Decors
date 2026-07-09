from django.urls import path
from . import views

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
    
    # ========== AJAX URLs ==========
    path('ajax/get-subcategories/', views.get_subcategories_ajax, name='get_subcategories'),
]