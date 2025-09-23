from django.core.cache import cache
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from task.models import Task, TaskCluster, TaskLabel


@receiver([post_save, post_delete], sender=Task)
def invalidate_task_cache(sender, instance, **kwargs):
    """Invalidate all cache data for the task"""
    try:
        if hasattr(instance, 'user') and instance.user:
            cache.delete_pattern(f"*task_completion_stats_{instance.user.id}*")
    except Exception:
        pass
    
@receiver([post_save, post_delete], sender=TaskCluster)
def invalidate_task_cluster_cache(sender, instance, **kwargs):
    """Invalidate all cache data for the task cluster"""
    try:
        if getattr(instance, "created_by", None) and instance.created_by_id:
            cache.delete_pattern(f"*task_completion_stats_{instance.created_by_id}*")
            cache.delete_pattern(f"*created_clusters_{instance.created_by_id}*")

        cache.delete_pattern("*available_clusters*")
    except Exception:
        pass


@receiver([post_save, post_delete], sender=TaskLabel)
def invalidate_task_label_cache(sender, instance, **kwargs):
    """Invalidate all cache data for the task label"""
    try:
        # Check if the task and cluster still exist before accessing them
        if hasattr(instance, 'task') and instance.task and hasattr(instance.task, 'cluster') and instance.task.cluster:
            cache.delete_pattern(f"*cluster_annotation_progress_{instance.labeller.id}_GET_/api/v1/tasks/cluster/{instance.task.cluster.id}/progress/*")
    except Exception:
        # This prevents errors during bulk delete operations
        pass
    
    
    
    