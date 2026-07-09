from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Profile, Address
from .utils import delete_file_if_exists

User = get_user_model()

@receiver(pre_delete, sender=User)
def delete_user_related_files(sender, instance, **kwargs):
    """Delete profile picture when user is deleted"""
    if hasattr(instance, 'profile') and instance.profile.profile_picture:
        delete_file_if_exists(instance.profile.profile_picture.name)

@receiver(pre_delete, sender=Profile)
def delete_profile_picture(sender, instance, **kwargs):
    """Delete profile picture when profile is deleted"""
    if instance.profile_picture:
        delete_file_if_exists(instance.profile_picture.name)

@receiver(pre_delete, sender=Address)
def delete_address_related_files(sender, instance, **kwargs):
    """Delete any associated files when address is deleted"""
    pass