from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import LabelerDomain

@receiver([post_save, post_delete], sender=LabelerDomain)
def invalidate_labeler_domain_cache(sender, instance, **kwargs):
    cache.delete_pattern("*labeler_domains*")