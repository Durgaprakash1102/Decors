# Ecom/decorators.py

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from functools import wraps

def staff_or_employee_required(function=None, redirect_field_name=None, login_url=None):
    """
    Decorator for views that checks that the user is either staff (admin) or employee.
    """
    def check_permission(user):
        return user.is_authenticated and (user.is_staff or user.is_employee)
    
    actual_decorator = user_passes_test(
        check_permission,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator


def employee_required(function=None, redirect_field_name=None, login_url=None):
    """
    Decorator for views that checks that the user is an employee.
    """
    def check_permission(user):
        return user.is_authenticated and user.is_employee
    
    actual_decorator = user_passes_test(
        check_permission,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator


def admin_required(function=None, redirect_field_name=None, login_url=None):
    """
    Decorator for views that checks that the user is an admin.
    """
    def check_permission(user):
        return user.is_authenticated and user.is_admin
    
    actual_decorator = user_passes_test(
        check_permission,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator