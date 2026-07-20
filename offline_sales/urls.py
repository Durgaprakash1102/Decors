# offline_sales/urls.py

from django.urls import path
from . import views

app_name = 'offline_sales'

urlpatterns = [
    # Store Settings
    path('store-settings/', views.store_settings_list, name='store_settings_list'),
    path('store-settings/edit/', views.store_settings_edit, name='store_settings_edit'),
    
    # Barcode Management
    path('barcodes/', views.barcode_list_view, name='barcode_list'),
    path('barcodes/generate/', views.generate_barcode_view, name='generate_barcode'),
    path('barcodes/generate/product/<int:product_id>/', views.generate_barcode_view, name='generate_product_barcode'),
    path('barcodes/generate/variant/<int:variant_id>/', views.generate_barcode_view, name='generate_variant_barcode'),
    path('barcodes/download/<int:barcode_id>/', views.download_barcode_view, name='download_barcode'),
    path('barcodes/delete/<int:barcode_id>/', views.delete_barcode_view, name='delete_barcode'),
    
    # Barcode Scanning
    path('scan-barcode/', views.scan_barcode_view, name='scan_barcode'),
    
    # Offline Sale
    path('sale/', views.offline_sale_view, name='offline_sale'),
    path('sale/add-product/', views.offline_sale_add_product, name='add_product'),
    path('sale/remove-product/', views.offline_sale_remove_product, name='remove_product'),
    path('sale/update-quantity/', views.offline_sale_update_quantity, name='update_quantity'),
    path('sale/clear-cart/', views.offline_sale_clear_cart, name='clear_cart'),
    path('sale/complete/', views.offline_sale_complete, name='complete_sale'),
    
    # Customer Management
     path('customers/', views.customer_list_view, name='customer_list'),
    path('customer/create/', views.customer_create_view, name='customers_create'),
    path('customer/edit/<int:customer_id>/', views.customer_edit_view, name='customers_edit'),
    path('customers/create/', views.offline_customer_create, name='customer_create'),
    path('customers/edit/<int:customer_id>/', views.customer_edit_view, name='customer_edit'),
    path('customers/delete/<int:customer_id>/', views.customer_delete_view, name='customer_delete'),
    path('customers/search/', views.offline_customer_search, name='customer_search'),
    
    # Orders
    path('orders/', views.orders_list_view, name='orders_list'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail'),
    
    # Invoice
    path('invoice/download/<int:order_id>/', views.download_invoice_view, name='download_invoice'),
    path('sale/search/', views.product_search_view, name='product_search'),
]