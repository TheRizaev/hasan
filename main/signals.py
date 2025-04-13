from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Create a UserProfile for each new User."""
    if created:
        # Create the profile
        UserProfile.objects.create(user=instance)
        logger.info(f"Profile created for user {instance.username}")

@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is updated."""
    if hasattr(instance, 'profile'):
        instance.profile.save()