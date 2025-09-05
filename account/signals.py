from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from account.models import Project

@receiver([post_save, post_delete], sender=Project)
def invalidate_project_cache(sender, instance, **kwargs):
    cache.delete_pattern(f"*task_completion_stats_{instance.created_by.id}*")