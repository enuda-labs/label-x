from django.core.cache import cache
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from task.models import Task, TaskCluster


@receiver([post_save, post_delete], sender=Task)
def invalidate_task_cache(sender, instance, **kwargs):
    """Invalidate all cache data for the task"""    
    cache.delete_pattern(f"*task_completion_stats_{instance.user.id}*")
    
@receiver([post_save, post_delete], sender=TaskCluster)
def invalidate_task_cluster_cache(sender, instance, **kwargs):
    """Invalidate all cache data for the task cluster"""
    if instance.created_by:
        cache.delete_pattern(f"*task_completion_stats_{instance.created_by.id}*")
        cache.delete_pattern(f"*created_clusters_{instance.created_by.id}*")

    cache.delete_pattern("*available_clusters*")
    print('invalidated task cluster cache 5')