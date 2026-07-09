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
]