# offline_sales/signals.py
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OfflineOrder


@receiver(post_save, sender=OfflineOrder)
def update_offline_customer_stats(sender, instance, created, **kwargs):
    """Update offline customer stats when order is created"""
    if created and instance.offline_customer:
        customer = instance.offline_customer
        customer.total_orders = OfflineOrder.objects.filter(offline_customer=customer).count()
        customer.total_purchases = OfflineOrder.objects.filter(
            offline_customer=customer, 
            payment_status='paid'
        ).aggregate(total=models.Sum('total_amount'))['total'] or 0
        customer.last_purchase_at = OfflineOrder.objects.filter(
            offline_customer=customer
        ).order_by('-created_at').first().created_at
        customer.save()